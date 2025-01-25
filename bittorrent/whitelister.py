#!/usr/bin/env python3

""" forever-tunning script whitelisting Kiwix Catalog ZIM torrents in the Tracker

    - Connects to torrust-based Tracker API
    - Downloads OPDS Catalog
    - Gets BT Info Hash for all entries via mirrorbrain endpoint
    - Adds BTIH to the tracker whitelist using the API
    - Sleeps until next iteration
"""

import datetime
import io
import logging
import os
import pathlib
import re
import sys
import time
from typing import ClassVar
from urllib.parse import urlparse
from uuid import UUID

# humanfriendly==10.0 requests==2.32.3 xmltodict==0.14.2 urllib3==2.3.0
import humanfriendly
import requests
import requests.adapters
import xmltodict
from urllib3.util.retry import Retry

API_URL = os.environ["API_URL"]
API_STARTUP_DURATION = humanfriendly.parse_timespan(
    os.getenv("API_STARTUP_DURATION") or "30s"
)
CACHE_DIR = pathlib.Path(os.getenv("CACHE_DIR") or os.getenv("TMPDIR") or "/tmp")
CATALOG_ETAG_FILE = CACHE_DIR / "catalog.etag"
CATALOG_URL = os.getenv("CATALOG_URL", "") or "https://library.kiwix.org/catalog/v2"
DEBUG = bool(os.getenv("DEBUG") or "")
DOWNLOAD_URL = os.getenv("DOWNLOAD_URL", "") or "https://download.kiwix.org"
BTIH_MAP_FOLDER = CACHE_DIR / "btih.map"
REFRESH_INTERVAL = humanfriendly.parse_timespan(os.getenv("REFRESH_INTERVAL") or "1h")
TOKEN = os.environ["TOKEN"]
TIMEOUT = int(os.getenv("TIMEOUT") or "30")

logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)
logger = logging.getLogger("whitelister")
should_top: bool = False
session: requests.Session = requests.Session()
# basic urllib retry mechanism.
# Sleep (seconds): {backoff factor} * (2 ** ({number of total retries} - 1))
# https://docs.descarteslabs.com/_modules/urllib3/util/retry.html
retries = Retry(
    total=10,  # Total number of retries to allow. Takes precedence over other counts.
    connect=5,  # How many connection-related errors to retry on
    read=5,  # How many times to retry on read errors
    redirect=20,  # How many redirects to perform. (to avoid infinite redirect loops)
    status=3,  # How many times to retry on bad status codes
    other=0,  # How many times to retry on other errors
    allowed_methods=None,  # Set of HTTP verbs that we should retry on (False is all)
    status_forcelist=[
        413,
        429,
        500,
        502,
        503,
        504,
    ],  # Set of integer HTTP status we should force a retry on
    backoff_factor=30,  # backoff factor to apply between attempts after the second try,
    backoff_max=1800.0,  # allow up-to 30mn backoff (default 2mn)
    raise_on_redirect=False,  # raise MaxRetryError instead of 3xx response
    raise_on_status=False,  # raise on Bad Status or response
    respect_retry_after_header=True,  # respect Retry-After header (status_forcelist)
)
session.mount("http", requests.adapters.HTTPAdapter(max_retries=retries))


class EtagCache:
    """Simple fs-based cache for the Catalog's ETAG"""

    fpath: pathlib.Path = CATALOG_ETAG_FILE

    @classmethod
    def get(cls) -> str:
        cls.fpath.parent.mkdir(parents=True, exist_ok=True)
        try:
            return cls.fpath.read_text().strip()
        except Exception:
            return ""

    @classmethod
    def set(cls, value: str):
        cls.fpath.parent.mkdir(parents=True, exist_ok=True)
        cls.fpath.write_text(value)


def query_catalog_etag() -> str:
    """Current ETAG of the remote catalog"""
    try:
        resp = session.head(
            f"{CATALOG_URL}/entries", params={"count": "-1"}, timeout=TIMEOUT
        )
        return resp.headers.get("etag") or ""
    except Exception:
        ...
    return ""


def get_payload_from(url: str, no_more_than: int = 4096) -> bytes:
    """Retrieved content from an URL

    Limited in order to prevent download bomb.

    Parameters:
        url: URL to retrieve payload from (follows redirects)
        no_more_than: number of bytes to consider too much and fail at

    Raises:
        OSError: Should declared or retrieved size exceed no_more_than
        RequestException: HTTP or other error in requests
        ConnectionError: connection issues
        Timeout: ReadTimeout or request timeout"""

    resp = session.get(url, stream=True, allow_redirects=True, timeout=TIMEOUT)
    resp.raise_for_status()
    downloaded = 0
    payload = io.BytesIO()
    for data in resp.iter_content(2**30):
        downloaded += len(data)
        if no_more_than and downloaded > no_more_than:
            raise OSError(f"URL content is larger than {no_more_than!s}")
        payload.write(data)
    payload.seek(0)
    return payload.getvalue()


def read_mirrorbrain_hash_from(url: str) -> str:
    """hashes from mirrorbrain-like (or raw) URL (checksums, btih)

        Format can be the raw digest or digest and filename:
            9e92449ce93115e8d85e29e8e584dece  wikipedia_ab_all_maxi_2024-02.zim

    Parameters:
        url: URL to read from. eg: download.kiwix.org/x/y/z.zim.sha1

    Raises:
        OSError: Should declared or retrieved size exceed no_more_than
        RequestException: HTTP or other error in requests
        ConnectionError: connection issues
        Timeout: ReadTimeout or request timeout
        UnicodeDecodeError: content cannot be decoded into ASCII
        UnicodeEncodeError: content  cannot be encoded into UTF-8
        IndexError: content is empty or malformed
    """
    return (
        get_payload_from(url, no_more_than=4 * 2**10)
        .decode("UTF-8")
        .strip()
        .split(maxsplit=1)[0]
        .encode("UTF-8")
        .decode("ASCII")
    )


def read_btih_url(url: str) -> str:
    uri = urlparse(url)
    if uri.netloc != urlparse(DOWNLOAD_URL).netloc:
        raise ValueError(f"btih from URL is reserved to {DOWNLOAD_URL}: {url}")
    if not uri.path.endswith(".btih"):
        raise ValueError(f"btih from URL is only for {DOWNLOAD_URL}'s .btih endpoint")
    # btih is 40-len but endpoint sends filename as well
    return read_mirrorbrain_hash_from(url)


def contact_api() -> int:
    """Nb of torrents in tracker. Serves as API test allowing it to fail for a bit

    Returns -1 if API could not be reached"""
    last_exc = None
    for _ in range(0, int(API_STARTUP_DURATION)):
        try:
            resp = session.get(
                f"{API_URL}/stats", params={"token": TOKEN}, timeout=TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()["torrents"]
        except Exception as exc:
            logger.warning(f"Failed to contact API: {exc!s}")
            last_exc = exc
            time.sleep(1)
            continue
    logger.error(f"Unable to contact API: {last_exc!s}")
    logger.exception(last_exc)
    return -1


def add_torrent(btih: str) -> bool:
    """whether the hash has been added to the whitelist"""
    try:
        resp = session.post(
            f"{API_URL}/whitelist/{btih}", params={"token": TOKEN}, timeout=TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()["status"] == "ok"
    except Exception as exc:
        logger.exception(exc)
        return False


class InfoHashMapper:
    """Disk-cached mapping of Book UUID to BT Info Hash

    Required since btih is not a Catalog metadata but necessary to reconcile
    torrents with books uniquely"""

    # maps {uuid: str} to {btih: str}
    data: ClassVar[dict[str, str]] = {}
    last_read: datetime.datetime = datetime.datetime(2000, 1, 1, tzinfo=datetime.UTC)

    @classmethod
    def load(cls, *, force: bool = False):
        now = datetime.datetime.now(tz=datetime.UTC)
        if not force and cls.last_read + datetime.timedelta(60) >= now:
            return
        BTIH_MAP_FOLDER.mkdir(parents=True, exist_ok=True)
        data = {
            fpath.name.split(":", 1)[0]: fpath.name.split(":", 1)[1]
            for fpath in BTIH_MAP_FOLDER.iterdir()
            if ":" in fpath.name
        }
        cls.last_read = now
        cls.data = data

    @classmethod
    def dump(cls):
        BTIH_MAP_FOLDER.mkdir(parents=True, exist_ok=True)
        for uuid, btih in cls.data:
            BTIH_MAP_FOLDER.joinpath(f"{uuid}:{btih}").touch()

    @classmethod
    def get(cls, uuid: UUID) -> str | None:
        cls.load()
        return cls.data.get(uuid.hex)

    @classmethod
    def add(cls, uuid: UUID, btih: str):
        uuids = uuid.hex
        if uuids in cls.data:
            return
        cls.data[uuids] = btih
        BTIH_MAP_FOLDER.mkdir(parents=True, exist_ok=True)
        BTIH_MAP_FOLDER.joinpath(f"{uuids}:{btih}").touch()

    @classmethod
    @property
    def count(cls) -> int:
        return len(cls.data)


def get_btih(uuid: UUID, btih_url: str) -> str:
    """BTIH for a ZIM UUID and .btih URL

    Returned from cache if in cache;
    otherwise fetched online from URL (and stored in cache) before returning"""
    if btih := InfoHashMapper.get(uuid):
        return btih

    btih = read_btih_url(btih_url)
    InfoHashMapper.add(uuid, btih)
    return btih


def do_refresh() -> str:
    """Actual, full catalog refresh using online OPDS call"""
    logger.info(f"Refreshing catalog via {CATALOG_URL}")

    resp = session.get(
        f"{CATALOG_URL}/entries", params={"count": "-1"}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    etag = resp.headers.get("etag") or ""
    catalog = xmltodict.parse(resp.content)

    if "feed" not in catalog:
        raise ValueError("Malformed OPDS response")
    if not int(catalog["feed"]["totalResults"]):
        raise OSError("Catalog has no entry; probably misbehaving")

    logger.info(f"> {len(catalog['feed']['entry'])} entries")

    for entry in catalog["feed"]["entry"]:
        if not entry.get("name"):
            logger.warning(f"Skipping entry without name: {entry}")
            continue

        uuid = UUID(entry["id"])
        links = {link["@type"]: link for link in entry["link"]}
        btih_url = re.sub(r".meta4$", ".btih", links["application/x-zim"]["@href"])
        btih = get_btih(uuid, btih_url)
        entry_repr = f"{uuid.hex}: {btih} – {entry['name']}"

        # we add the hash to the tracker withoiut regard to it being present or not
        # as the API is OK with this
        if add_torrent(btih):
            logger.debug(f"- {entry_repr}")
        else:
            logger.warning(f"Failed to add {entry_repr}")

    logger.debug(f"refreshed catalog")
    return etag


def refresh() -> bool:
    """whether we actually refreshed (content changed)"""
    previous_etag = EtagCache.get()
    etag = query_catalog_etag()
    if etag and previous_etag == etag:
        return False

    etag = do_refresh()
    EtagCache.set(etag)
    return True


def pause():
    """wait for next refresh iteration"""
    logger.debug(f"pausing for {humanfriendly.format_timespan(REFRESH_INTERVAL)}")
    # micro 1s pause to allow interrupt
    for _ in range(0, int(REFRESH_INTERVAL)):
        time.sleep(1)


def main() -> int:
    logger.info("Starting whitelister")
    logger.debug(f"- {API_URL=}")
    logger.debug(f"- {TOKEN=}")
    logger.debug(f"- CACHE_DIR={CACHE_DIR!s}")
    logger.debug(
        f"- REFRESH_INTERVAL={humanfriendly.format_timespan(REFRESH_INTERVAL)}"
    )
    logger.debug("Reading btih map from cache")
    InfoHashMapper.load()
    logger.debug(f"> {InfoHashMapper.count} entries")

    nb_torrents = contact_api()
    if nb_torrents < 0:
        logger.critical("Unable to contact API, exiting.")
        return 1
    logger.info(f"API Connection successful. {nb_torrents} torrents in the Tracker")

    while not should_top:
        try:
            if not refresh():
                logger.info("Catalog has not changed since last call")
        except Exception as exc:
            logger.error(f"Failed to refresh: {exc!s}")
            logger.exception(exc)
        pause()
    return 0


if __name__ == "__main__":
    sys.exit(main())
