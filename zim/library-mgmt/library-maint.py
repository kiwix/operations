#!/usr/bin/env python3

"""
    apt install -y libmagic1
    pip install unidecode requests lxml zimscraperlib
"""

import argparse
import base64
import datetime
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unidecode
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Generator, Tuple, List

import mwclient
import requests
from lxml import etree
from humanfriendly import format_size as human_size

from zimscraperlib.i18n import get_language_details
from zimscraperlib.zim import Archive

logger = logging.getLogger("gen-lib")

# in-ZIM metadata to in-library XML attributes
NAMES_MAP: Dict[str, str] = {
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

COPIED_KEYS = ["id", "size", "url", "mediaCount", "articleCount", "favicon"] + list(
    NAMES_MAP.values()
)

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

    WIKI_DOMAIN = "wiki.kiwix.org"
    WIKI_USERNAME = "bot"
    WIKI_PASSWORD = "notset"
    WIKI_PAGE = "notset"

    OFFSPOT_LIBRARY = "/data/download/library/ideascube.yml"
    MIRRORBRAIN_URL = "http://mirrorbrain-web-service"

    DELETE_TO = "/data/download/.deleted-zim"


def pathlib_relpath(data: Any) -> Any:
    """json.load hook to cast `relpath` attribute"""
    if isinstance(data, dict):
        if "relpath" in data:
            data["relpath"] = pathlib.Path(data["relpath"])

    return data


def get_tmp(fpath: pathlib.Path) -> pathlib.Path:
    """path to use to write fpath temporarily"""
    return pathlib.Path(
        tempfile.NamedTemporaryFile(
            prefix=fpath.stem, suffix=fpath.suffix, delete=False
        ).name
    )


def swap(tmp: pathlib.Path, final: pathlib.Path):
    """moves* tmp to its final dest via copy + rm to prevent cross-fs errors"""
    shutil.copy2(tmp, final)
    tmp.unlink()


def without_period(text: str) -> str:
    """text or filename without its ending _YYYY-MM period suffix"""
    return re.sub(r"_\d{4}-\d{2}$", "", re.sub(r"\.zim$", "", text))


def period_from(text: str) -> str:
    """extracted period from a ZIM filename or stem"""
    return re.search(
        r"_(?P<period>\d{4}-\d{2})$", re.sub(r"\.zim$", "", text)
    ).groupdict()["period"]


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


def to_std_dict(obj: Any) -> Dict:
    """Specific values we use to compare previous/current libraries"""
    return {key: obj.get(key, "") for key in COPIED_KEYS}


def human_sort(entry: Dict) -> str:
    """human-sort-frienldy string to compare ZIM entries"""
    return (
        str(PROJECTS_PRIO.get(entry["project"], len(PROJECTS_PRIO) + 1)).zfill(2)
        + entry["lang"]
        + entry["year"]
        + entry["month"]
    )


def sort_filenames_for_recent(filenames: List[pathlib.Path]) -> List[pathlib.Path]:
    """Sorted copy of a list of ZIM filenames with ASC names but DESC periods"""

    def split_filename(filename):
        return re.split(r"_(?P<period>\d{4}-\d{2})$", filename.stem)

    def get_core(filename):
        return split_filename(filename)[0]

    def get_period(filename):
        return split_filename(filename)[1]

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
    root: pathlib.Path, with_hidden: bool = False
) -> Generator[pathlib.Path, None, None]:
    """ZIM (*.zim) file paths from a root folder, recursively.

    Optionnaly includes hidden (.-prefixed) ZIM files or ZIM in hidden folders"""

    if with_hidden:  # faster than os.walk in this case
        yield from root.rglob("*.zim")
        return

    for folder, dirnames, filenames in os.walk(root):
        if not with_hidden:
            _ = [dirnames.remove(name) for name in dirnames if name.startswith(".")]
            _ = [filenames.remove(name) for name in filenames if name.startswith(".")]
        _ = [filenames.remove(name) for name in filenames if not name.endswith(".zim")]

        for filename in filenames:
            yield pathlib.Path(folder).joinpath(filename)


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
    tree = etree.parse(str(pub_library_dest))

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
    etree.parse(str(int_library_tmp))
    logger.info("[LIBS] XML is well formed. Swaping files…")
    swap(int_library_tmp, internal_library_dest)
    logger.info("[LIBS] > done.")


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, pathlib.Path):
            return str(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


class PreviousLib:
    def __init__(self, fpath: pathlib.Path):
        self.books: Dict[str, Dict] = {}  # core: entry
        self.aliases: Dict[str, str] = {}  # human: id
        self.read = False

        try:
            self.date = datetime.datetime.fromtimestamp(fpath.stat().st_mtime)
            tree = etree.parse(str(fpath))
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
    ACTIONS = [
        "read",
        "delete-zim",
        "write-redirects",
        "write-libraries",
        "write-offspot",
        "purge-varnish",
        "update-wiki",
    ]

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
        wiki_domain: str,
        wiki_username: str,
        wiki_password: str,
        wiki_page: str,
        offspot_library_dest: str,
        mirrorbrain_url: str,
        log_to: str,
        delete_to: str,
        dump_fs: bool,
        load_fs: bool,
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
        self.wiki_domain = wiki_domain
        self.wiki_username = wiki_username
        self.wiki_password = wiki_password
        self.wiki_page = wiki_page

        self.offspot_library_dest = pathlib.Path(offspot_library_dest)
        self.mirrorbrain_url = mirrorbrain_url

        self.log_to = pathlib.Path(log_to) if log_to else False
        self.delete_to = pathlib.Path(delete_to) if delete_to else False
        self.dump_fs = pathlib.Path(dump_fs) if dump_fs else False
        self.load_fs = pathlib.Path(load_fs) if load_fs else False

        # mapping of <core>: [<entry>, ] for ZIMs (entry is Dict)
        self.all_zims = {}

        self.previous_lib: PreviousLib = None
        self.updated_zims: Dict[str, Tuple(str, str)] = {}  # alias: (uuid, core)

    @property
    def exposed_zims(self) -> Dict[str, Dict]:
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

    def read_zimfile_info(self, fpath: pathlib.Path, read_zim: bool) -> Dict[str, Any]:
        """All infor read from ZIM file/name"""
        entry = {}
        relpath = fpath.relative_to(self.zim_root)

        try:
            values = self.filename_fmt.match(fpath.stem).groupdict()
        except AttributeError:
            try:
                values = self.old_filename_fmt.match(fpath.stem).groupdict()
            except Exception:
                logger.error(
                    f"[READ] Non-standard ZIM filename: {fpath.name}. Skipping"
                )
                raise ValueError("Non-standard ZIM filename")

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
                "mediaCount": str(zim.media_counter),
                "articleCount": str(zim.article_counter),
            }
        )

        for meta_name in NAMES_MAP.keys():
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

    def readfs(self):
        """walk filesystem for ZIM files to build self.all_zims

        Optionnaly reads from load_fs JSON file.
        Optionnaly dumps it to dump_fs JSON file."""

        if self.load_fs:
            logger.info(f"[READ] Attempting reload from {self.load_fs}")
            try:
                with open(self.load_fs, "r") as fh:
                    self.all_zims = json.load(fh, object_hook=pathlib_relpath)
                    return
            except Exception as exc:
                logger.warning(
                    f"Unable to load fs data from {self.load_fs}. Reading filesystem"
                    f" -- {exc}"
                )

        all_zim_files = get_zim_files(self.zim_root, self.with_hidden)
        for index, zim_path in enumerate(sort_filenames_for_recent(all_zim_files)):
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
            shutil.move(fpath, self.delete_to / f"{fpath.parent.name}__{fpath.name}")

        logger.info(f"[DELETE] moving obsolete ZIMs to {self.delete_to}")
        nb_deleted = deleted_size = 0
        for fpath in self.obsolete_zim_files:
            size = fpath.stat().st_size
            logger.info(f"[DELETE] moving {fpath} ({human_size(size)})")

            delete_file(fpath)

            nb_deleted += 1
            deleted_size += size
        logger.info(
            f"[DELETE] moved {nb_deleted} files, saving {human_size(deleted_size)}"
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
                fh.write(etree.tostring(elem, encoding="UTF-8"))
                fh.write(b"\n")
            fh.write(b"</library>\n")

        logger.info("[LIBS] Public Library successfuly generated. Verifying XML…")
        etree.parse(str(pub_library_tmp))
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

    def write_offspot_library(self):
        logger.info("[LIBS] Generating Offspot YAML Library")
        env = dict(os.environ)
        if self.mirrorbrain_url:
            env.update({"MIRRORBRAIN_URL": self.mirrorbrain_url})
        subprocess.run(
            ["library-to-offspot", self.pub_library_dest, self.offspot_library_dest],
            check=True,
        )

    def purge_varnish(self):
        """Request varnish cache to expire updated Books and Paths"""
        if not self.updated_zims:
            logger.info("[PURGE] No updated ZIM in Library, not purging.")
            return

        # purge library (once)
        logger.info(f"[PURGE] Requesting Library purge from {self.varnish_url}")
        resp = requests.request(
            method="PURGE", url=self.varnish_url, headers={"X-Purge-Type": "library"}
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
            )
            if not resp.ok:
                logger.error(f"[PURGE] >> HTTP {resp.status_code}/{resp.reason}")

        # no mandate to purge kiwix-serve
        # resp = requests.request(
        #     method="PURGE",
        #     url=self.varnish_url,
        #     headers={"X-Purge-Type": "kiwix-serve"},
        # )

    def update_wiki(self):

        logger.info(
            f"[WIKI] Updating {self.wiki_username}@{self.wiki_domain}::{self.wiki_page}"
        )

        download_dir = self.zim_root.relative_to(self.redirects_root)
        content = "<!-- PAGE IS GENERATED AUTOMATICALLY, DO NOT EDIT MANUALLY -->\n"
        for entry in sorted(self.exposed_zims.values(), key=human_sort):
            ident = without_period(entry["relpath"].stem)
            try:
                lang_name = get_language_details(entry["lang"])["native"]
            except Exception:
                lang_name = entry["lang"]
            options = " ".join(
                [opt.strip() for opt in entry["option"].split("_") if opt.strip()]
            )
            content += (
                r"{{ZIMdumps/row|{{{2|}}}|{{{3|}}}|"
                f"{entry['project']} ({lang_name}) | {entry['lang']} | "
                f"{human_size(entry['rsize'])} | {entry['year']}-{entry['month']} "
                f"| {options} |"
                r"8={{DownloadLink|"
                f"{ident}|"
                r"{{{1}}}|"
                f"{download_dir}"
                "/}} }}\n"
            )

        logger.info(f"[WIKI] > OK. generated {len(content.splitlines()) -1 } links")

        site = mwclient.Site(self.wiki_domain)
        site.login(self.wiki_username, self.wiki_password)
        page = site.pages[self.wiki_page]
        page.save(content, summary="Auto update following library refresh")
        logger.info(f"[WIKI] {self.wiki_page} updated")

    def run(self):
        if "all" in self.actions:
            self.actions = self.ACTIONS
        else:
            for action in self.actions:
                if action not in self.ACTIONS:
                    logger.error(f"{action} is not a valid action")
                    return 1

        logger.info(f"Starting library-maint for {', '.join(self.actions)}")

        self.load_previous_library()

        # always read source data
        self.readfs()
        if not len(self.all_zims):
            return 1

        if "delete-zim" in self.actions:
            self.delete_outdated()

        if "write-redirects" in self.actions:
            self.write_zim_redirects_map()

        if "write-libraries" in self.actions:
            self.write_public_library()
            self.write_internal_library()

        if "write-offspot" in self.actions:
            self.write_offspot_library()

        if "purge-varnish" in self.actions:
            self.purge_varnish()

        if "update-wiki" in self.actions:
            self.update_wiki()


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
        "--wiki-domain",
        default=os.getenv("WIKI_DOMAIN", Defaults.WIKI_DOMAIN),
        help="Domain-name of the Mediawiki instance for Wiki Page update. Defaults to "
        f"`WIKI_DOMAIN` environ or {Defaults.WIKI_DOMAIN}",
        dest="wiki_domain",
    )
    parser.add_argument(
        "--wiki-username",
        default=os.getenv("WIKI_USERNAME", Defaults.WIKI_USERNAME),
        help="Username to authenticate with on the Wiki to update the page. "
        f"`Defaults to WIKI_USERNAME` environ or {Defaults.WIKI_USERNAME}",
        dest="wiki_username",
    )
    parser.add_argument(
        "--wiki-password",
        default=os.getenv("WIKI_PASSWORD", Defaults.WIKI_PASSWORD),
        help="Domain-name of the Mediawiki instance for Wiki Page update. Defaults to "
        f"`WIKI_PASSWORD` environ or {Defaults.WIKI_PASSWORD}",
        dest="wiki_password",
    )
    parser.add_argument(
        "--wiki-page",
        default=os.getenv("WIKI_PAGE", Defaults.WIKI_PAGE),
        help="Password to authenticate with on the Wiki to update the page. "
        f"`Defaults to WIKI_PAGE` environ or {Defaults.WIKI_PAGE}",
        dest="wiki_page",
    )
    parser.add_argument(
        "--offspot-library",
        default=os.getenv("OFFSPOT_LIBRARY", Defaults.OFFSPOT_LIBRARY),
        help="Path to (over)write Offspot's YAML Library to. "
        f"`Defaults to OFFSPOT_LIBRARY` environ or {Defaults.OFFSPOT_LIBRARY}",
        dest="offspot_library_dest",
    )
    parser.add_argument(
        "--mirrorbrain-url",
        default=os.getenv("MIRRORBRAIN_URL", Defaults.MIRRORBRAIN_URL),
        help="URL to use to access mirrorbrain instead of default public on. "
        f"`Defaults to MIRRORBRAIN_URL` environ or {Defaults.MIRRORBRAIN_URL}",
        dest="mirrorbrain_url",
    )

    parser.add_argument(
        "--log-to",
        help="Save log output to to file in addition to stdout",
        default="",
        dest="log_to",
    )

    parser.add_argument(
        "--delete-to",
        help="Where to move files to instead of deleting them. "
        f"`Defaults to DELETE_TO` environ or {Defaults.DELETE_TO}",
        default=os.getenv("DELETE_TO", Defaults.DELETE_TO),
        dest="delete_to",
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
        pathlib.Path(args.log_to).unlink(missing_ok=True)
        handlers.append(logging.FileHandler(pathlib.Path(args.log_to)))
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
        raise SystemExit(1)


if __name__ == "__main__":
    entrypoint()
