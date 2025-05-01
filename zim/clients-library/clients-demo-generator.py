#!/usr/bin/env python3

import datetime
import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import requests
import yaml
from humanfriendly import format_size as human_size
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from lxml import etree
from pydantic import BaseModel
from zimscraperlib.logging import getLogger  # pyright: ignore [reportMissingTypeStubs]
from zimscraperlib.zim import Archive  # pyright: ignore [reportMissingTypeStubs]

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

COPIED_KEYS = ["id", "size", "url", "mediaCount", "articleCount", "path"] + list(
    NAMES_MAP.values()
)


FILENAME_FMT = re.compile(
    r"^(?P<project>.+?_)(?P<lang>[a-z\-]{2,10}?_|)"
    r"(?P<option>.+_|)(?P<year>[\d]{4}|)\-(?P<month>[\d]{2})(?P<version>[a-z]{0,2})$",
    re.IGNORECASE,
)

REQUESTS_TIMEOUT = 10


# Define Pydantic models
class Demo(BaseModel):
    name: str
    zims: list[str]
    expired_on: datetime.date


class Config(BaseModel):
    demos: list[Demo]


class ZimInfo(BaseModel):
    path: Path
    infos: dict[str, Any] = {}


def binary_human_size(size: float):
    return human_size(size, binary=True)


def install_demo(demo: Demo, demo_tmpl: Template):
    demo_path = demos_path / demo.name
    demo_path.mkdir(exist_ok=True)
    (demo_path / "index.html").write_text(
        demo_tmpl.render(
            {"zims": [zims[zim_archive].infos for zim_archive in demo.zims]}
        )
    )


# constants
demos_path = Path("/data/demo")
normal_zim_path = Path("/data/zim")
hidden_zim_path = Path("/data/hidden-zim")
demo_library = demos_path / "demo_library.xml"
demo_config = demos_path / "demos.yaml"
demo_dead_html = demos_path / "dead.html"
demo_favicon = demos_path / "favicon.ico"
demo_dead_kiwix_png = demos_path / "dead-kiwix.png"
demo_home_tmpl_path = demos_path / "demo-home.jinja2"
favicons_path = demos_path / "favicons"
favicons_path.mkdir(exist_ok=True)
logger = getLogger("demo-generator")
assets_base_url = (
    "https://raw.githubusercontent.com/kiwix/operations/main/zim/clients-library/"
)
logger.info(f"Assets will be downloaded from {assets_base_url}")
varnish_cache_url = "http://clients-library-webcache-service"


def zim_date_key(zim_filename: str) -> tuple[str, int, str, str]:
    """Function to be used as sorting criteria for ZIM names.

    Function properly sort by name then date, including versions suffix in the date

    E.g. sorted(
        [
            "tests_eng_test_2024-01aa.zim",
            "tests_eng_test_2024-01b.zim",
            "tests_eng_test_2024-01.zim",
            "tests_eng_test_2023-01.zim",
        ],
        key=zim_date_key,
    ) == [
        "tests_eng_test_2023-01.zim",
        "tests_eng_test_2024-01.zim",
        "tests_eng_test_2024-01b.zim",
        "tests_eng_test_2024-01aa.zim",
    ]

    The "trick" is to return first up to the xxxx-xx part, then the length of optional
    ll suffix, then the suffix itself. Python takes care of the rest (first compare the
    prefix, then the lenght of the suffix, then the suffix itself)
    """
    fm = re.match(
        r"^(?P<name_with_date>.+_\d{4}-\d{2})(?P<ll>[a-z]*)\.(?P<ext>.*?)$",
        zim_filename,
    )
    if not fm:
        return (zim_filename, 0, "", "")  # Just in case ...
    return (
        fm.group("name_with_date"),
        len(fm.group("ll")),
        fm.group("ll"),
        fm.group("ext"),
    )


class BadZimNameError(Exception):
    """ZIM matching passed name has not been found on the storage"""

    pass


class ZimNotFoundError(Exception):
    """ZIM has not been found on the storage"""

    pass


def get_ziminfo(zim_archive: str) -> ZimInfo:
    """Get informations about a given ZIM archive

    Supports either a full ZIM path (ted/ted_mul_all_2024-07.zim) or a incomplete path
    (ted/ted_mul_all) for which the latest version will be search for.

    Supports both prod and .hidden paths.
    """
    is_hidden = zim_archive.startswith(".hidden/")
    base_path = hidden_zim_path if is_hidden else normal_zim_path
    if is_hidden:
        zim_archive = zim_archive[8:]
    if zim_archive.endswith(".zim"):
        zim_path = base_path / zim_archive
        if not zim_path.exists():
            raise ZimNotFoundError()
    else:
        zim_book_versions = list(base_path.glob(zim_archive + "_*.zim"))
        bad_zim_book_versions = [
            zim_book
            for zim_book in zim_book_versions
            if not FILENAME_FMT.match(zim_book.stem)
        ]
        for bad_zim_book in bad_zim_book_versions:
            logger.warning(
                f"Ignoring {bad_zim_book}, does not match expected filename pattern"
            )
        zim_book_versions = [
            zim_book
            for zim_book in zim_book_versions
            if zim_book not in bad_zim_book_versions
        ]
        if len(zim_book_versions) == 0:
            raise ZimNotFoundError()
        zim_path = sorted(zim_book_versions, key=lambda path: zim_date_key(path.name))[
            -1
        ]

    zim_infos: dict[str, Any] = {"path": str(zim_path)}

    filename_match = FILENAME_FMT.match(zim_path.stem)
    if not filename_match:
        raise BadZimNameError()

    values = filename_match.groupdict()

    download_url = (
        f"https://mirror.download.kiwix.org/zim/.hidden/{zim_path.relative_to(base_path)}"
        if is_hidden
        else f"https://download.kiwix.org/zim/{zim_path.relative_to(base_path)}"
    )
    zim_infos.update(
        {
            "project": values["project"][:-1],
            "lang": values["lang"][:-1] if values.get("lang") else "en",
            "option": values["option"][:-1] if values.get("option") else "",
            "month": values["month"],
            "year": values["year"],
            "core": zim_path.stem,
            "rsize": zim_path.stat().st_size,
            "size": str(int(zim_path.stat().st_size / 1024)),
            "url": str(f"{download_url}.meta4"),
            "download_url": download_url,
        }
    )

    zim_archive = Archive(zim_path)

    zim_infos.update(
        {
            "id": str(
                zim_archive.uuid  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
            ),
            "mediaCount": str(
                zim_archive.media_count  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
            ),
            "articleCount": str(
                zim_archive.article_count  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
            ),
        }
    )

    for meta_name in NAMES_MAP.keys():
        try:
            if meta_name == "Tags":
                zim_infos[NAMES_MAP[meta_name]] = ";".join(
                    zim_archive.get_tags(libkiwix=True)
                )
                continue
            zim_infos[NAMES_MAP[meta_name]] = zim_archive.get_text_metadata(meta_name)
        except RuntimeError:
            if meta_name == "Title":
                zim_infos[NAMES_MAP[meta_name]] = zim_path.stem.replace("_", " ")
            continue
    if zim_archive.has_illustration(48):  # pyright: ignore [reportUnknownMemberType]
        (favicons_path / f"{zim_infos['id']}.png").write_bytes(
            zim_archive.get_illustration_item(  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
                48
            ).content
        )

    return ZimInfo(path=zim_path, infos=zim_infos)


def get_tmp(fpath: Path) -> Path:
    """path to use to write fpath temporarily"""
    return Path(
        tempfile.NamedTemporaryFile(
            prefix=fpath.stem, suffix=fpath.suffix, delete=False
        ).name
    )


def swap(tmp: Path, final: Path):
    """moves* tmp to its final dest via copy + rm to prevent cross-fs errors"""
    shutil.copy2(tmp, final)
    tmp.unlink()


@contextmanager
def open_chmod(file: Path, mode: str = "r", chmod: int | None = None):
    """open a file and then chmod it after use"""
    with open(file, mode=mode) as fh:
        yield fh
    if chmod:
        file.chmod(chmod)


logger.info("Downloading demo configuration…")
resp = requests.get(
    assets_base_url + "demos.yaml",
    timeout=REQUESTS_TIMEOUT,
)
resp.raise_for_status()
demo_config.write_bytes(resp.content)

for static_file in [
    demo_dead_html,
    demo_favicon,
    demo_dead_kiwix_png,
    demo_home_tmpl_path,
]:
    logger.info(f"Downloading {static_file.name}…")
    resp = requests.get(
        assets_base_url + static_file.name,
        timeout=REQUESTS_TIMEOUT,
    )
    resp.raise_for_status()
    static_file.write_bytes(resp.content)

logger.info("Preparing…")
zims: dict[str, ZimInfo] = {}

jinja_env = Environment(
    autoescape=select_autoescape(), loader=FileSystemLoader(demos_path)
)

jinja_env.filters["human_size"] = (  # pyright: ignore [reportUnknownMemberType]
    binary_human_size
)
demo_tmpl = jinja_env.get_template(demo_home_tmpl_path.name)

logger.info("Parsing demo configuration…")
config = Config(**yaml.safe_load(demo_config.read_text()))

# Filter demos based on expired datetime
now = datetime.date.today()
config.demos = [demo for demo in config.demos if demo.expired_on > now]

logger.info("Searching for declared ZIMs and extracting infos…")
for demo in config.demos:
    for zim_archive in demo.zims:
        logger.info(f"- {zim_archive}")
        try:
            zims[zim_archive] = get_ziminfo(zim_archive)
        except ZimNotFoundError:
            logger.warning(f"No ZIM found for {zim_archive}")
        except BadZimNameError:
            logger.warning(
                f"Ignoring {zim_archive}, does not match expected filename pattern"
            )

logger.info("Generating Demo Library XML…")
demo_library_tmp = get_tmp(demo_library)
# chmod is not mandatory but still usefull since this file is not private at all
with open_chmod(demo_library_tmp, "wb", chmod=0o644) as fh:
    fh.write(
        b'<?xml version="1.0" encoding="UTF-8" ?>\n' b'<library version="20110515">\n'
    )
    for zim_infos in zims.values():
        elem = etree.Element("book")
        for attr in COPIED_KEYS:
            if value := zim_infos.infos.get(attr):
                elem.set(attr, value)
        fh.write(etree.tostring(elem, encoding="UTF-8"))
        fh.write(b"\n")
    fh.write(b"</library>\n")

logger.info("Verifying Demo Library XML…")
etree.parse(str(demo_library_tmp))

logger.info("Swaping Demo Library files…")
swap(demo_library_tmp, demo_library)

logger.info("Cleaning unused favicons…")
active_favicons = [
    favicons_path / f"{zim_info.infos['id']}.png" for zim_info in zims.values()
]
for favicon in favicons_path.iterdir():
    if favicon.is_file() and not favicon in active_favicons:
        favicon.unlink()

logger.info("Generating demos homepage…")

for demo in config.demos:
    install_demo(demo, demo_tmpl)

logger.info("Cleaning-up old demos homepage…")
for file in demos_path.iterdir():
    if not file.is_dir():
        continue
    if file.name in [demo.name for demo in config.demos] + ["favicons"]:
        continue
    shutil.rmtree(demos_path / file.name)

logger.info("Requesting cache purge…")
try:
    resp = requests.request(
        method="PURGE",
        url=varnish_cache_url,
        headers={"X-Purge-Type": "all"},
        timeout=REQUESTS_TIMEOUT,
    )
    if not resp.ok:
        logger.error(
            f"Error while purging cache: HTTP {resp.status_code}/{resp.reason}"
        )
except Exception as exc:
    logger.error("Error while purging cache", exc_info=exc)

logger.info("Done.")
