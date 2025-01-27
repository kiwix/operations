# pyright: reportImplicitStringConcatenation=false
import os
from typing import Any, NamedTuple
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup, NavigableString
from bs4.element import Tag

TIMEOUT = int(os.getenv("TIMEOUT") or "20")
SCHEMES = os.getenv("SCHEMES", "https").split(",")
DEFAULT_SCHEME = SCHEMES[0]
LIBRARY_HOST = os.getenv("LIBRARY_HOST", "library.kiwix.org")
OPDS_NAV_MIMETYPE = (
    "application/atom+xml;profile=opds-catalog;kind=navigation;charset=utf-8"
)
OPDS_ENDPOINTS = {
    "/catalog/root.xml": "application/atom+xml;profile=opds-catalog;"
    "kind=acquisition;charset=utf-8",
    "/catalog/v2/root.xml": OPDS_NAV_MIMETYPE,
    "/catalog/v2/searchdescription.xml": "application/opensearchdescription+xml",
    "/catalog/v2/entries": "application/atom+xml;profile=opds-catalog;"
    "kind=acquisition;charset=utf-8",
    "/catalog/v2/categories": OPDS_NAV_MIMETYPE,
    "/catalog/v2/languages": OPDS_NAV_MIMETYPE,
}
# searchdescription is so small compression would be counter-productive
COMPRESSABLE_OPDS_ENDPOINTS = {
    endpoint: mime
    for endpoint, mime in OPDS_ENDPOINTS.items()
    if mime != "application/opensearchdescription+xml"
}
# https://github.com/kiwix/libkiwix/blob/main/src/server/response.cpp#L47
KIWIX_MIN_CONTENT_SIZE_TO_COMPRESS = 1400



def get_url(
    path="/",
    scheme=DEFAULT_SCHEME,
    host=LIBRARY_HOST,
):
    return f"{scheme}://{host}{path}"


def get_response_headers(path, method="HEAD", scheme=DEFAULT_SCHEME):
    return requests.request(
        method=method,
        url=get_url(path=path, scheme=scheme),
        headers={"Accept-Encoding": "gzip, deflate, br"},
        timeout=TIMEOUT,
    ).headers


def is_cached(path, method="GET", scheme=DEFAULT_SCHEME):
    for _ in range(2):
        ret = get_response_headers(path, method=method, scheme=scheme).get("X-Varnish")
    return len(ret.split(" ")) >= 2


class Mirror(NamedTuple):
    hostname: str
    base_url: str
    country_code: str

    @property
    def is_load_balancer(self) -> bool:
        return self.hostname in ("mirror.accum.se")


def get_current_mirrors(
    mirrors_list_url: str, excluded_mirrors: list[str]
) -> list[Mirror]:
    """Current mirrors from the mirrors url."""

    def is_country_row(tag: Tag) -> bool:
        """Filters out table rows that do not contain mirror data."""
        return tag.name == "tr" and tag.findChild("td", class_="newregion") is None

    resp = requests.get(mirrors_list_url, timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, features="html.parser")
    body = soup.find("tbody")

    if body is None or isinstance(body, NavigableString | int):
        raise ValueError(f"unable to parse mirrors information from {mirrors_list_url}")

    mirrors: list[Mirror] = []

    for row in body.find_all(is_country_row):
        base_url = row.find("a", string="HTTP")["href"]
        hostname: Any = urlsplit(
            base_url
        ).netloc  # pyright: ignore [reportUnknownMemberType]
        country_code = row.find("img")["alt"].lower()
        if hostname in excluded_mirrors:
            continue
        mirrors.append(
            Mirror(
                hostname=hostname,
                base_url=base_url,
                country_code=country_code,
            )
        )
    return mirrors
