import os
import requests

SCHEMES = ([] if os.getenv("HTTP_ONLY") else ["https"]) + ["http"]
DEFAULT_SCHEME = SCHEMES[0]
LIBRARY_HOST = os.getenv("LIBRARY_HOST", "library.kiwix.org")
OPDS_NAV_MIMETYPE = "application/atom+xml;profile=opds-catalog;kind=navigation"
OPDS_ENDPOINTS = {
    "/catalog/root.xml": "application/atom+xml; profile=opds-catalog; "
    "kind=acquisition; charset=utf-8",
    "/catalog/v2/root.xml": OPDS_NAV_MIMETYPE,
    "/catalog/v2/searchdescription.xml": "application/opensearchdescription+xml",
    "/catalog/v2/entries": "application/atom+xml;profile=opds-catalog;kind=acquisition",
    "/catalog/v2/categories": OPDS_NAV_MIMETYPE,
    "/catalog/v2/languages": OPDS_NAV_MIMETYPE,
}


def get_url(
    path="/",
    scheme=DEFAULT_SCHEME,
    host=LIBRARY_HOST,
):
    return f"{scheme}://{host}{path}"


def get_response_headers(path, method="HEAD", scheme=DEFAULT_SCHEME):
    return requests.request(
        method=method, url=get_url(path=path, scheme=scheme)
    ).headers


def is_cached(path, method="HEAD", scheme=DEFAULT_SCHEME):
    for _ in range(2):
        ret = get_response_headers(path, method=method, scheme=scheme).get("X-Varnish")
    return len(ret.split(" ")) >= 2
