#!/usr/bin/env python3

"""
apt install -y libmagic1
pip install unidecode requests lxml zimscraperlib psycopg2-binary
"""

import argparse
import base64
import datetime
import json
import logging
import os
import pathlib
import re
import sys
import time
import urllib.parse
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg2  # pyright: ignore [reportMissingModuleSource]
import psycopg2._psycopg  # pyright: ignore [reportMissingModuleSource]
import requests
import unidecode
from humanfriendly import format_size as human_size
from lxml import etree  # pyright: ignore [reportAttributeAccessIssue]
from zimscraperlib.zim import Archive

MIRRORBRAIN_DB_DSN = os.getenv("MIRRORBRAIN_DB_DSN") or "notset"
MIRRORBRAIN_BATCH_SIZE = int(os.getenv("MIRRORBRAIN_BATCH_SIZE") or "100")

VARNISH_PURGE_HTTP_TIMEOUT = 50


# in-ZIM metadata to in-library XML attributes
NAMES_MAP: dict[str, str] = {
    "Title": "title",
    "Description": "description",
    "Language": "language",
    "Creator": "creator",
    "Publisher": "publisher",
    "Name": "name",
    "Flavour": "flavour",
    "Tags": "tags",
    "Date": "date",
}

COPIED_KEYS = [
    "id",
    "size",
    "url",
    "mediaCount",
    "articleCount",
    "favicon",
    *list(NAMES_MAP.values()),
]

PROJECTS_PRIO = {
    "wikipedia": 1,
    "wiktionary": 2,
    "wikivoyage": 3,
    "wikiversity": 4,
    "wikibooks": 5,
    "wikisource": 6,
    "wikiquote": 7,
    "wikinews": 8,
    "wikispecies": 9,
    "ted": 10,
    "phet": 11,
}

logger = logging.getLogger("gen-lib")


class Mirrorbrain:

    @classmethod
    def get_connection(cls) -> psycopg2._psycopg.connection:
        return psycopg2.connect(dsn=MIRRORBRAIN_DB_DSN)

    @classmethod
    def ensure_connected(cls):
        with cls.get_connection() as connection:
            if not connection.server_version:
                raise OSError("Not connected to mirrorbrain DB")

    @classmethod
    def has_hashes_for(cls, relpath: str) -> bool:
        """whether a single path has hashes on mirrorbrain"""
        with cls.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    r"SELECT COUNT(f.id) FROM filearr f, hash h "
                    r"WHERE f.id=h.file_id and f.path = %s;",
                    (relpath,),
                )
                row = cursor.fetchone()
                if row:
                    return bool(row[0])
            return False

    @classmethod
    def get_not_ready_from(
        cls, all_zims: list[pathlib.Path], relative_to: pathlib.Path
    ) -> list[pathlib.Path]:
        """list of path from supplied list that dont have hashes on mirrorbrain

        list of path is resolved to relative_to but returned as supplied
        ---

        We cant query MB for all the existing ones without specifying
        because the DB has like 130K entries (and counting).

        We cant make an enormous query with an IN/ANY parameter containing
        4,000 items neither.

        We're left with two choices:
        - make 4K individual requests
          - quick requests as those match on equality of path
          - output is only a boolean for each
        - make batch requests with ANY operator
          - way less requests (40 for batches of 100)
          - output is a lot more verbose as we then need the path for each
        """

        if not all_zims:
            return []

        nb_zims = len(all_zims)
        batch_size = MIRRORBRAIN_BATCH_SIZE
        nb_batches = nb_zims // batch_size
        remaining = nb_zims % batch_size
        missing = list(all_zims)

        def get_prefix(zim_path: pathlib.Path) -> pathlib.Path:
            relpath = zim_path.relative_to(relative_to)
            return pathlib.Path(*zim_path.parts[: -len(relpath.parts)])

        # record the source values prefix so we can apply that back when we receive
        # the results from MB DB as those are relative to MB root (so no prefix)
        prefix = get_prefix(all_zims[0])

        def query_for(zim_paths: list[pathlib.Path]):
            if not zim_paths:
                return
            stmt = (
                r"SELECT f.path FROM filearr f, hash h "
                r"WHERE f.id=h.file_id and f.path = ANY(%s);"
            )
            values = [str(zim_path.relative_to(relative_to)) for zim_path in zim_paths]
            cursor.execute(stmt, (values,))
            for row in cursor.fetchall():
                zim_path = prefix.joinpath(pathlib.Path(row[0]))
                missing.remove(zim_path)

        with cls.get_connection() as connection:
            with connection.cursor() as cursor:
                for batch_index in range(nb_batches):
                    query_for(
                        all_zims[
                            (batch_index * batch_size) : (batch_index * batch_size)
                            + batch_size
                        ]
                    )
                if remaining:
                    query_for(all_zims[-remaining:])
        return missing


@dataclass
class Defaults:
    LIBRARY_MAINT_ACTION = ""

    ZIM_ROOT = "/data/download/zim"
    LIBRARY_PATH = "/data/download/library/library_zim.xml"
    DOWNLOAD_URL_ROOT = "https://download.kiwix.org/zim/"

    INTERNAL_ZIM_ROOT = "/data/"
    INTERNAL_LIBRARY_PATH = "/data/library/internal_library.xml"

    REDIRECTS_ROOT = "/data/download"
    ZIM_REDIRECTS_MAP = "/data/maps/zim.map"

    NB_ZIM_VERSIONS_TO_KEEP = 2
    NB_ZIM_VERSIONS_EXPOSED = 1

    VARNISH_URL = "http://localhost"


def pathlib_relpath(data: Any) -> Any:
    """json.load hook to cast `relpath` attribute"""
    if isinstance(data, dict):
        if "relpath" in data:
            data["relpath"] = pathlib.Path(data["relpath"])

    return data


def get_tmp(fpath: pathlib.Path) -> pathlib.Path:
    """path to use to write fpath temporarily"""
    return fpath.with_name(
        f"{fpath.name}.tmp_{datetime.datetime.now(datetime.UTC).timetz()}"
    )


def swap(tmp: pathlib.Path, final: pathlib.Path):
    r"""rename tmp to final on fs. /!\ doesnt work cross-fs"""
    tmp.rename(final)


def without_period(text: str) -> str:
    """text or filename without its ending _YYYY-MM period suffix"""
    return re.sub(r"_\d{4}-\d{2}$", "", re.sub(r"\.zim$", "", text))


def period_from(text: str) -> str:
    """extracted period from a ZIM filename or stem"""
    return re.search(
        r"_(?P<period>\d{4}-\d{2})$", re.sub(r"\.zim$", "", text)
    ).groupdict()[  # pyright: ignore [reportOptionalMemberAccess]
        "period"
    ]


def fname_from_url(url: str) -> pathlib.Path:
    return pathlib.Path(urllib.parse.urlparse(re.sub(r".meta4$", "", url)).path)


def to_human_id(fpath: pathlib.Path) -> str:
    """libkiwix-compat human ID (used in path-prefix) for a ZIM file"""
    return unidecode.unidecode(fpath.stem.replace(" ", "_").replace("+", "plus"))


def to_human_alias(fpath: pathlib.Path) -> str:
    """libkiwix --nodatealias equivalent from ZIM filename"""
    return without_period(to_human_id(fpath))


def to_core(fpath: pathlib.Path) -> str:
    """human identifier from ZIM filename"""
    return fpath.stem


def to_std_dict(obj: Any) -> dict:
    """Specific values we use to compare previous/current libraries"""
    return {key: obj.get(key, "") for key in COPIED_KEYS}


def human_sort(entry: dict) -> str:
    """human-sort-frienldy string to compare ZIM entries"""
    return (
        str(PROJECTS_PRIO.get(entry["project"], len(PROJECTS_PRIO) + 1)).zfill(2)
        + entry["lang"]
        + entry["year"]
        + entry["month"]
    )


def sort_filenames_for_recent(filenames: Iterable[pathlib.Path]) -> list[pathlib.Path]:
    """Sorted copy of a list of ZIM filenames with ASC names but DESC periods"""

    def split_filename(filename):
        return re.split(r"_(?P<period>\d{4}-\d{2})$", filename.stem)

    def get_core(filename):
        try:
            return split_filename(filename)[0]
        except IndexError:
            print(f"FAILED on {filename}")  # noqa: T201
            raise

    def get_period(filename):
        try:
            return split_filename(filename)[1]
        except IndexError:
            print(f"FAILED on {filename}")  # noqa: T201
            raise

    filenames_ = list(filenames)
    # sort by descending period
    filenames_.sort(key=get_period, reverse=True)
    # sort by core
    filenames_.sort(key=get_core, reverse=False)

    return filenames_


@contextmanager
def open_chmod(file: pathlib.Path, *args, **kwargs):
    chmod = kwargs.pop("chmod", None)
    with open(file, *args, **kwargs) as fh:
        yield fh
    if chmod:
        file.chmod(chmod)


def get_zim_files(
    root: pathlib.Path, *, with_hidden: bool = False
) -> Generator[pathlib.Path, None, None]:
    """ZIM (*.zim) file paths from a root folder, recursively.

    Optionnaly includes ZIM files in hidden folders (not hidden ZIMs!)"""

    def excluded_filter(fp: pathlib.Path) -> bool:
        """excludes files not to consider

        - special patterns
        - hidden files
        - files marked for deletion with .delete suffix
        """
        return (
            not fp.name.startswith("speedtest_")
            and (not fp.name.startswith(".") or fp.name == ".")
            and (len(fp.name) == 0 or not fp.with_suffix(".delete").exists())
        )

    if with_hidden:  # faster than os.walk in this case
        filter_ = excluded_filter
    else:

        def filter_(fp: pathlib.Path) -> bool:
            return all(
                [excluded_filter(parent) for parent in fp.relative_to(root).parents]
                + [excluded_filter(fp)]
            )

    yield from filter(filter_, root.rglob("*.zim"))


def is_latest(fpath: pathlib.Path) -> bool:
    """whether latest version of a Title, based on filename"""
    version = period_from(fpath.stem)
    for filename in fpath.parent.glob(f"{without_period(fpath.stem)}_*.zim"):
        if period_from(filename.name) > version:
            return False
    return True


def convert_pub_library_to_internal(
    pub_library_dest: pathlib.Path,
    internal_library_dest: pathlib.Path,
    download_url_root: str,
    internal_zim_root: pathlib.Path,
):
    logger.info(f"[LIBS] Preparing internal Library for {internal_library_dest}")

    int_library_tmp = get_tmp(internal_library_dest)
    tree = etree.parse(str(pub_library_dest))  # noqa: S320

    with open_chmod(int_library_tmp, "wb", chmod=0o644) as fh:
        fh.write(
            (
                f'<?xml version="{tree.docinfo.xml_version}" '
                f'encoding="{tree.docinfo.encoding}" ?>\n'
                f"<{tree.docinfo.root_name} "
                f'version="{tree.getroot().attrib.get("version")}">\n'
            ).encode(tree.docinfo.encoding)
        )
        for elem in tree.iter():
            if elem.tag == tree.docinfo.root_name:
                continue

            # internal library path is constructed from relative download path
            # in URL and prefix with internal_zim_root
            elem.set(
                "path",
                re.sub(
                    r"^" + download_url_root + r"(.+).meta4$",
                    str(internal_zim_root) + r"/\1",
                    elem.attrib["url"],
                ),
            )
            fh.write(etree.tostring(elem, encoding=tree.docinfo.encoding))
        fh.write(f"</{tree.docinfo.root_name}>\n".encode(tree.docinfo.encoding))

    logger.info("[LIBS] Internal Library successfuly generated. Verifying XML…")
    etree.parse(str(int_library_tmp))  # noqa: S320
    logger.info("[LIBS] XML is well formed. Swaping files…")
    swap(int_library_tmp, internal_library_dest)
    logger.info("[LIBS] > done.")


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, pathlib.Path):
            return str(o)
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


class PreviousLib:
    def __init__(self, fpath: pathlib.Path):
        self.books: dict[str, dict] = {}  # core: entry
        self.aliases: dict[str, str] = {}  # human: id
        self.read = False

        try:
            self.date = datetime.datetime.fromtimestamp(
                fpath.stat().st_mtime, datetime.UTC
            )
            tree = etree.parse(str(fpath))  # noqa: S320
        except Exception:
            logger.warning("[READ] Unbale to read previous library. Purging disabled.")
            return

        for book in tree.findall("book"):
            purl = fname_from_url(book.attrib["url"])
            self.books[to_core(purl)] = to_std_dict(book.attrib)
            if to_human_alias(purl) not in self.aliases:
                self.aliases[to_human_alias(purl)] = book.attrib["id"]

        self.read = True

    def has_book(self, book_core, book_human):
        return book_core in self.books.keys() or book_human in self.aliases.keys()

    def is_update(self, entry):
        if not self.has_book(entry["core"], to_human_alias(entry["relpath"])):
            return False
        return to_std_dict(entry) != self.books.get(entry["core"])


class LibraryMaintainer:

    # allowed actions for the script
    ACTIONS = (
        "read",
        "delete-zim",
        "write-redirects",
        "write-libraries",
        "purge-varnish",
    )

    # former (old) filename format for ZIMs (period was MM_YYYY)
    old_filename_fmt = re.compile(
        r"^(?P<project>.+?_)(?P<lang>[a-z\-]{2,10}?_|)"
        r"(?P<option>.+_|)(?P<month>[\d]{2}|)_(?P<year>[\d]{4})$",
        re.IGNORECASE,
    )
    # current filename format for ZIMs (period is YYYY-MM)
    filename_fmt = re.compile(
        r"^(?P<project>.+?_)(?P<lang>[a-z\-]{2,10}?_|)"
        r"(?P<option>.+_|)(?P<year>[\d]{4}|)\-(?P<month>[\d]{2})$",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        actions: str,
        zim_root: str,
        with_hidden: bool,
        pub_library_dest: str,
        download_url_root: str,
        internal_zim_root: str,
        internal_library_dest: str,
        redirects_root: str,
        zim_redirects_map: str,
        nb_zim_versions_to_keep: int,
        nb_zim_versions_exposed: int,
        varnish_url: str,
        log_to: str,
        dump_fs: str,
        load_fs: str,
    ):
        self.actions = [action.strip() for action in actions]

        self.zim_root = pathlib.Path(zim_root)
        self.with_hidden = with_hidden
        self.pub_library_dest = pathlib.Path(pub_library_dest)

        self.internal_zim_root = pathlib.Path(internal_zim_root)
        self.internal_library_dest = pathlib.Path(internal_library_dest)

        # path the ZIM-redirects webserver consideres root (/)
        self.download_url_root = download_url_root
        self.redirects_root = pathlib.Path(redirects_root)
        self.zim_redirects_map = pathlib.Path(zim_redirects_map)

        self.nb_zim_versions_to_keep = nb_zim_versions_to_keep
        self.nb_zim_versions_exposed = nb_zim_versions_exposed

        self.varnish_url = varnish_url

        self.log_to = pathlib.Path(log_to) if log_to else None
        self.dump_fs = pathlib.Path(dump_fs) if dump_fs else None
        self.load_fs = pathlib.Path(load_fs) if load_fs else None

        # mapping of <core>: [<entry>, ] for ZIMs (entry is dict)
        self.all_zims = {}

        self.previous_lib: PreviousLib
        self.updated_zims: dict[str, tuple[str, str]] = {}  # alias: (uuid, core)

    @property
    def exposed_zims(self) -> dict[str, dict]:
        """alias: Entry of just the last entries for an alias"""
        return {alias: entries[0] for alias, entries in self.all_zims.items()}

    def load_previous_library(self):
        """parse and keep previous public XML Library content for later comparison"""
        logger.info("[READ] Loading previous Public Library")
        self.previous_lib = PreviousLib(self.pub_library_dest)
        if self.previous_lib.read:
            logger.info(
                f"[READ] > Previous Library has {len(self.previous_lib.books)} books, "
                f"{len(self.previous_lib.aliases)} aliases"
            )

    def read_zimfile_info(
        self, fpath: pathlib.Path, *, read_zim: bool
    ) -> dict[str, Any]:
        """All infor read from ZIM file/name"""
        entry = {}
        relpath = fpath.relative_to(self.zim_root)

        try:
            values = self.filename_fmt.match(
                fpath.stem
            ).groupdict()  # pyright: ignore[reportOptionalMemberAccess]
        except AttributeError:
            try:
                values = self.old_filename_fmt.match(
                    fpath.stem
                ).groupdict()  # pyright: ignore[reportOptionalMemberAccess]
            except Exception as exc:
                logger.error(
                    f"[READ] Non-standard ZIM filename: {fpath.name}. Skipping"
                )
                raise ValueError("Non-standard ZIM filename") from exc

        entry.update(
            {
                "project": values["project"][:-1],
                "lang": values["lang"][:-1] if values.get("lang") else "en",
                "option": values["option"][:-1] if values.get("option") else "",
                "month": values["month"],
                "year": values["year"],
                "core": to_core(fpath),
                "rsize": fpath.stat().st_size,
                "relpath": relpath,
                "size": str(int(fpath.stat().st_size / 1024)),
                "url": str(f"{self.download_url_root}{relpath}.meta4"),
                "latest": is_latest(fpath),
            }
        )

        if not read_zim:
            return entry

        zim = Archive(fpath)

        entry.update(
            {
                "id": str(zim.uuid),
                "mediaCount": str(zim.media_count),
                "articleCount": str(zim.article_count),
            }
        )

        for meta_name in NAMES_MAP.keys():  # noqa: PLC0206
            try:
                if meta_name == "Tags":
                    entry[NAMES_MAP[meta_name]] = ";".join(zim.get_tags(libkiwix=True))
                    continue
                entry[NAMES_MAP[meta_name]] = zim.get_text_metadata(meta_name)
            except RuntimeError:
                if meta_name == "Title":
                    entry[NAMES_MAP[meta_name]] = fpath.stem.replace("_", " ")
                continue
        if zim.has_illustration(48):
            entry["favicon"] = base64.standard_b64encode(
                zim.get_illustration_item(48).content
            ).decode("ASCII")

        return entry

    def readfs(self, *, restrict_to_mirrorbrain: bool = False):
        """walk filesystem for ZIM files to build self.all_zims

        Optionnaly reads from load_fs JSON file.
        Optionnaly dumps it to dump_fs JSON file."""

        if self.load_fs:
            logger.info(f"[READ] Attempting reload from {self.load_fs}")
            try:
                with open(self.load_fs) as fh:
                    self.all_zims = json.load(fh, object_hook=pathlib_relpath)
                    return
            except Exception as exc:
                logger.warning(
                    f"Unable to load fs data from {self.load_fs}. Reading filesystem"
                    f" -- {exc}"
                )

        all_zim_files = get_zim_files(self.zim_root, with_hidden=self.with_hidden)
        all_zim_files = sort_filenames_for_recent(all_zim_files)  # consumes generator

        if restrict_to_mirrorbrain:
            not_mb_ready = Mirrorbrain.get_not_ready_from(
                all_zim_files,
                # mirrorbrain works off a non-zim root (as for the redirects)
                relative_to=self.redirects_root,
            )
            # reduce list to matching ones
            for path in not_mb_ready:
                logger.warning(f"[MB] Excluding {path} (not in Mirrorbrain)")
                all_zim_files.remove(path)

        for index, zim_path in enumerate(all_zim_files):
            relpath = zim_path.relative_to(self.zim_root)
            alias = to_human_alias(relpath)
            logger.debug(f"[READ] {str(index).zfill(4)} {relpath}")

            try:
                # only read in-zim data (slow) for the first n (1) files.
                # we want to track all files so we can delete obsolete but deletion
                # is only based on filename. ZIM-details only for latest comp.
                # /!\ depends on iterator being sorted
                entry = self.read_zimfile_info(
                    zim_path,
                    read_zim=len(self.all_zims.get(alias, []))
                    < self.nb_zim_versions_exposed,
                )
            except ValueError:
                continue

            if alias not in self.all_zims:
                self.all_zims[alias] = [entry]
            else:
                self.all_zims[alias].append(entry)
                self.all_zims[alias].sort(
                    key=lambda e: f'{e["year"]}{str(e["month"]).zfill(2)}', reverse=True
                )

            # we had this book in previous lib but some metadata differ. mark updated
            if entry["latest"] and self.previous_lib.is_update(entry):
                logger.debug(f">> is update {alias}: {entry['id']}")
                self.updated_zims[alias] = (entry["id"], entry["core"])

        logger.debug(f"[READ] > {len(self.all_zims)} ZIM files in {self.zim_root}")

        if self.dump_fs:
            logger.info(f"[READ] Dumping filesystem data to {self.dump_fs}")
            with open_chmod(self.dump_fs, "w", chmod=0o644) as fh:
                json.dump(self.all_zims, fh, indent=4, cls=JSONEncoder)

    @property
    def obsolete_zim_files(self):
        for entries in self.all_zims.values():
            for entry in entries[self.nb_zim_versions_to_keep :]:
                yield self.zim_root / entry["relpath"]

    def delete_outdated(self):
        """Delete non-last (see nb_zim_versions_to_keep) ZIM files from filesystem"""

        def delete_file(fpath):
            fpath.unlink()

        logger.info("[DELETE] removing obsolete ZIMs")
        nb_deleted = deleted_size = 0
        for fpath in self.obsolete_zim_files:
            size = fpath.stat().st_size
            logger.info(f"[DELETE] removing {fpath} ({human_size(size)})")

            delete_file(fpath)

            nb_deleted += 1
            deleted_size += size
        logger.info(
            f"[DELETE] removed {nb_deleted} files, saving {human_size(deleted_size)}"
        )

    def write_zim_redirects_map(self):
        """Writes map file of redirects for ZIM files (no-period to last, no folder)

        Writes a `source target` mapping file for non-existent no-period ZIM
        paths to point to the last matching ZIM file (and companion files)"""

        logger.info(f"[REDIR] Writting ZIM redirects to {self.zim_redirects_map}")
        # no-period redirects for content
        content = ""
        prefix = self.zim_root.relative_to(self.redirects_root)

        def add_entry(ident, relpath):
            nonlocal content, prefix
            for suffix in ("", ".torrent", ".meta4", ".magnet", ".md5", ".sha256"):
                content += f"/{prefix}/{ident}.zim{suffix} /{relpath}{suffix}\n"

        for entry in self.exposed_zims.values():
            relpath = self.zim_root.joinpath(entry["relpath"]).relative_to(
                self.redirects_root
            )
            ident = without_period(relpath.stem)
            add_entry(ident, relpath)

            # [BACKWARD COMPATIBILITY] Redirect _all to _all_maxi if _all does not exist
            all_ident = ident.replace("_maxi", "")
            if all_ident not in self.exposed_zims.keys():
                add_entry(all_ident, relpath)

            # [BACKWARD COMPATIBILITY] Redirect _novid to _maxi if _novid does not exist
            novid_ident = ident.replace("_maxi", "_novid")
            if novid_ident not in self.exposed_zims.keys():
                add_entry(novid_ident, relpath)

            # [BACKWARD COMPATIBILITY] Redirect _nodet to _mini if _nodet does not exist
            nodet_ident = ident.replace("_mini", "_nodet")
            if nodet_ident not in self.exposed_zims.keys():
                add_entry(nodet_ident, relpath)

        with open_chmod(self.zim_redirects_map, "w", chmod=0o644) as fh:
            fh.write(content)

        logger.info(f"[REDIR] > OK. Wrote {len(content.splitlines()) -1 } redirects")

    def write_public_library(self):
        """Writes the Public (without path attrib) XML Library from all_zims"""

        logger.info(f"[LIBS] Preparing Public library for {self.pub_library_dest}")

        pub_library_tmp = get_tmp(self.pub_library_dest)
        with open_chmod(pub_library_tmp, "wb", chmod=0o644) as fh:
            fh.write(
                b'<?xml version="1.0" encoding="UTF-8" ?>\n'
                b'<library version="20110515">\n'
            )
            for entry in self.exposed_zims.values():
                elem = etree.Element("book")
                for attr in COPIED_KEYS:
                    if entry.get(attr):
                        elem.set(attr, entry.get(attr))
                    elem.set("faviconMimeType", "image/png")
                assert elem.get("id")  # safeguard that we dont write entry without data
                fh.write(etree.tostring(elem, encoding="UTF-8"))
                fh.write(b"\n")
            fh.write(b"</library>\n")

        logger.info("[LIBS] Public Library successfuly generated. Verifying XML…")
        etree.parse(str(pub_library_tmp))  # noqa: S320
        logger.info("[LIBS] Public XML is well formed. Swaping files…")
        swap(pub_library_tmp, self.pub_library_dest)
        logger.info("[LIBS] > done.")

    def write_internal_library(self):
        """Writes Internal (with path attrib) XML Library from Public Library"""
        convert_pub_library_to_internal(
            pub_library_dest=self.pub_library_dest,
            internal_library_dest=self.internal_library_dest,
            download_url_root=self.download_url_root,
            internal_zim_root=self.internal_zim_root,
        )

    def purge_varnish(self):
        """Request varnish cache to expire updated Books and Paths"""
        if not self.updated_zims:
            logger.info("[PURGE] No updated ZIM in Library, not purging.")
            return

        # purge library (once)
        logger.info(f"[PURGE] Requesting Library purge from {self.varnish_url}")
        time.sleep(10)
        resp = requests.request(
            method="PURGE",
            url=self.varnish_url,
            headers={"X-Purge-Type": "library"},
            timeout=VARNISH_PURGE_HTTP_TIMEOUT,
        )
        if not resp.ok:
            logger.error(f"[PURGE] > HTTP {resp.status_code}/{resp.reason}")

        logger.info("[PURGE] Requesting Books purge for")
        for book_alias in self.updated_zims.keys():
            book_id, book_core = self.updated_zims[book_alias]
            logger.debug(f"[PURGE] > {book_alias} / {book_core} / {book_id}")
            resp = requests.request(
                method="PURGE",
                url=self.varnish_url,
                headers={
                    "X-Purge-Type": "book",
                    "X-Book-Id": book_id,
                    "X-Book-Name": book_core,
                    # only account for new-style book name fmt (yolo)
                    "X-Book-Name-Nodate": book_alias,
                },
                timeout=VARNISH_PURGE_HTTP_TIMEOUT,
            )
            if not resp.ok:
                logger.error(f"[PURGE] >> HTTP {resp.status_code}/{resp.reason}")

        # no mandate to purge kiwix-serve
        # resp = requests.request(
        #     method="PURGE",
        #     url=self.varnish_url,
        #     headers={"X-Purge-Type": "kiwix-serve"},
        # )

    def filter_zims_to_mirrorbrain_ready_only(self):
        not_ready = Mirrorbrain.get_not_ready_from(
            # all_zims is a sorted list with first being latest for an alias
            [
                self.zim_root.joinpath(entries[0]["relpath"])
                for entries in self.all_zims.values()
            ],
            # mirrorbrain works off a non-zim root (as for the redirects)
            relative_to=self.redirects_root,
        )
        for zim_path in not_ready:
            relpath = zim_path.relative_to(self.zim_root)
            alias = to_human_alias(relpath)
            logger.debug(f"[MB] Excluding {relpath} (not in Mirrorbrain)")
            # we only need to keep the alias if there are 2 or more ZIMs for it
            if len(self.all_zims.get(alias, [])) < 2:  # noqa: PLR2004
                try:
                    del self.all_zims[alias]
                except KeyError:
                    ...
            else:
                for entry in list(self.all_zims[alias]):
                    if entry["relpath"] == relpath:
                        self.all_zims[alias].remove(entry)

    def run(self):
        restrict_to_mirrorbrain = False

        if "all" in self.actions:
            self.actions = self.ACTIONS
            restrict_to_mirrorbrain = True
        else:
            for action in self.actions:
                if action not in self.ACTIONS:
                    logger.error(f"{action} is not a valid action")
                    return 1

        logger.info(f"Starting library-maint for {', '.join(self.actions)}")

        if restrict_to_mirrorbrain:
            Mirrorbrain.ensure_connected()

        self.load_previous_library()

        # always read source data
        self.readfs(restrict_to_mirrorbrain=restrict_to_mirrorbrain)
        if not len(self.all_zims):
            return 1

        if "delete-zim" in self.actions:
            self.delete_outdated()

        if "write-redirects" in self.actions:
            self.write_zim_redirects_map()

        if "write-libraries" in self.actions:
            self.write_public_library()
            self.write_internal_library()

        if "purge-varnish" in self.actions:
            self.purge_varnish()


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="library-maint",
        description="Library ZIM and XML maintenance script",
    )

    parser.add_argument(
        "actions",
        help="Actions to perform. Comma-separated list within: "
        f"{LibraryMaintainer.ACTIONS}. “all” shortcut runs them all. "
        "Defaults to `LIBRARY_MAINT_ACTION` environ or {Defaults.LIBRARY_MAINT_ACTION}",
        nargs="+",
        default=os.getenv("LIBRARY_MAINT_ACTION", Defaults.LIBRARY_MAINT_ACTION),
    )

    parser.add_argument(
        "--zim-root",
        default=os.getenv("ZIM_ROOT", Defaults.ZIM_ROOT),
        help="Root folder to walk into to find ZIM files (category folders). "
        f"Defaults to `ZIM_ROOT` environ or {Defaults.ZIM_ROOT}",
        dest="zim_root",
    )
    parser.add_argument(
        "--with-hidden",
        default=False,
        help="Include hidden (dot prefixed) ZIM files and files in hidden folders.",
        action="store_true",
        dest="with_hidden",
    )
    parser.add_argument(
        "--library-dest",
        default=os.getenv("LIBRARY_PATH", Defaults.LIBRARY_PATH),
        help="Path to (over)write XML **public** Library to "
        f"Defaults to `LIBRARY_PATH` environ or {Defaults.LIBRARY_PATH}",
        dest="pub_library_dest",
    )
    parser.add_argument(
        "--download-url-root",
        default=os.getenv("DOWNLOAD_URL_ROOT", Defaults.DOWNLOAD_URL_ROOT),
        help="URL-prefix to use for ZIM download links. URL-equivalent of ZIM_ROOT. "
        "Add trailing-slash unless you have reasons not to. "
        f"Defaults to `DOWNLOAD_URL_ROOT` environ or {Defaults.DOWNLOAD_URL_ROOT}",
        dest="download_url_root",
    )

    parser.add_argument(
        "--internal-zim-root",
        default=os.getenv("INTERNAL_ZIM_ROOT", Defaults.INTERNAL_ZIM_ROOT),
        help="Path-prefix for `path=` attribte in XML (for kiwix-serve access). "
        f"Defaults to `INTERNAL_ZIM_ROOT` environ or {Defaults.INTERNAL_ZIM_ROOT}",
        dest="internal_zim_root",
    )
    parser.add_argument(
        "--internal-library-dest",
        default=os.getenv("INTERNAL_LIBRARY_PATH", Defaults.INTERNAL_LIBRARY_PATH),
        help="Path to (over)write **internal** XML Library to. Defaults to "
        f"`INTERNAL_LIBRARY_PATH` environ or {Defaults.INTERNAL_LIBRARY_PATH}",
        dest="internal_library_dest",
    )

    parser.add_argument(
        "--redirects-root",
        default=os.getenv("REDIRECTS_ROOT", Defaults.REDIRECTS_ROOT),
        help="Path-prefix for `path=` attribte in XML (for kiwix-serve access). "
        f"Defaults to `REDIRECTS_ROOT` environ or {Defaults.REDIRECTS_ROOT}",
        dest="redirects_root",
    )
    parser.add_argument(
        "--zim-redirects-map",
        default=os.getenv("ZIM_REDIRECTS_MAP", Defaults.ZIM_REDIRECTS_MAP),
        help="Path-prefix for `path=` attribte in XML (for kiwix-serve access). "
        f"Defaults to `ZIM_REDIRECTS_MAP` environ or {Defaults.ZIM_REDIRECTS_MAP}",
        dest="zim_redirects_map",
    )
    parser.add_argument(
        "--nb-keep-zim",
        default=os.getenv("NB_ZIM_VERSIONS_TO_KEEP", Defaults.NB_ZIM_VERSIONS_TO_KEEP),
        help="Nb. of versions of a Book to keep on filesystem. Defaults to "
        f"`NB_ZIM_VERSIONS_TO_KEEP` environ or {Defaults.NB_ZIM_VERSIONS_TO_KEEP}",
        type=int,
        dest="nb_zim_versions_to_keep",
    )
    parser.add_argument(
        "--nb-exposed-zim",
        default=os.getenv("NB_ZIM_VERSIONS_EXPOSED", Defaults.NB_ZIM_VERSIONS_EXPOSED),
        help="Nb. of versions of a Book to include in Library. Defaults to "
        f"`NB_ZIM_VERSIONS_EXPOSED` environ or {Defaults.NB_ZIM_VERSIONS_EXPOSED}",
        type=int,
        dest="nb_zim_versions_exposed",
    )
    parser.add_argument(
        "--varnish-url",
        default=os.getenv("VARNISH_URL", Defaults.VARNISH_URL),
        help="URL of the varnish cache to query for purge. Defaults to "
        f"`VARNISH_URL` environ or {Defaults.VARNISH_URL}",
        dest="varnish_url",
    )

    parser.add_argument(
        "--log-to",
        help="Save log output to to file in addition to stdout",
        default="",
        dest="log_to",
    )

    parser.add_argument(
        "--dump-fs",
        help="Dump filesystem-read info to a JSON file",
        default="",
        dest="dump_fs",
    )

    parser.add_argument(
        "--load-fs",
        help="Read filesystem-read info from a JSON file (if it exists).",
        default="",
        dest="load_fs",
    )

    args = parser.parse_args()

    # enable log to file
    handlers = [logging.StreamHandler()]
    if args.log_to:
        log_fpath = pathlib.Path(args.log_to)
        os.truncate(log_fpath, 0)
        handlers.append(
            logging.FileHandler(log_fpath)  # pyright: ignore [reportArgumentType]
        )
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )

    try:
        maint = LibraryMaintainer(**dict(args._get_kwargs()))
        sys.exit(maint.run())
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        logger.exception(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    entrypoint()
