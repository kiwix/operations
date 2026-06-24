# pyright: reportImplicitStringConcatenation=false
import os
from http import HTTPStatus
from typing import NamedTuple

import requests

TIMEOUT = int(os.getenv("TIMEOUT") or "20")
NB_RANDOM_CATALOG_ENTRIES = int(os.getenv("NB_RANDOM_CATALOG_ENTRIES") or "5")
SCHEMES = os.getenv("SCHEMES", "https").split(",")
DEFAULT_SCHEME = SCHEMES[0]
LIBRARY_HOST = os.getenv("LIBRARY_HOST", "opds.library.kiwix.org")
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


def check_cors_headers_for(url, valid_statuses: tuple[int] = (HTTPStatus.OK,)) -> bool:
    assert (
        requests.options(url, timeout=TIMEOUT, allow_redirects=False).status_code
        == HTTPStatus.NO_CONTENT
    )
    resp = requests.get(url, timeout=TIMEOUT, stream=True, allow_redirects=False)
    assert resp.status_code in valid_statuses
    headers = resp.headers
    # multiple similar headers (proxies) would turn this into a comma-separated list
    assert headers.get("access-control-allow-origin") == "*"
    assert {"GET", "HEAD", "OPTIONS"}.issubset(
        [
            method.strip()
            for method in headers.get("access-control-allow-methods", "").split(",")
        ]
    )
    assert {"Content-Type", "Authorization", "User-Agent", "Range"}.issubset(
        [
            header.strip()
            for header in headers.get("access-control-allow-headers", "").split(",")
        ]
    )
    assert {"Content-Range", "Content-Length", "Accept-Ranges"}.issubset(
        [
            header.strip()
            for header in headers.get("access-control-expose-headers", "").split(",")
        ]
    )
    assert headers.get("access-control-allow-credentials") == "true"
    csp = headers.get("content-security-policy", "")
    assert csp.startswith("frame-ancestors 'self' ")
    assert {
        "https://browser-extension.kiwix.org",
        "https://pwa.kiwix.org",
        "https://kiwix.github.io",
        "http://localhost:*",
    }.issubset([item.strip() for item in csp.split("self", 1)[1].split(" ")])

    return True


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

    resp = requests.get(mirrors_list_url, timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    return [
        Mirror(
            hostname=mirror["identifier"],
            base_url=mirror["http_url"],
            country_code=mirror["country"],
        )
        for mirror in resp.json()["mirrors"]
        if mirror["enabled"]
    ]
