from http import HTTPStatus

import pytest
import requests
from utils import (
    COMPRESSABLE_OPDS_ENDPOINTS,
    KIWIX_MIN_CONTENT_SIZE_TO_COMPRESS,
    OPDS_ENDPOINTS,
    SCHEMES,
    TIMEOUT,
    get_response_headers,
    get_url,
    is_cached,
)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_reachable(scheme):
    assert (
        requests.head(get_url("/", scheme), timeout=TIMEOUT).status_code
        == HTTPStatus.OK
    )


@pytest.mark.parametrize("path, mimetype", OPDS_ENDPOINTS.items())
def test_opds_mimetypes(path, mimetype):
    assert get_response_headers(path).get("Content-Type") == mimetype


@pytest.mark.parametrize("path", COMPRESSABLE_OPDS_ENDPOINTS.keys())
def test_opds_is_gzipped(path):
    resp = requests.request(
        method="GET",
        url=get_url(path=path),
        headers={"Accept-Encoding": "gzip, deflate, br"},
        timeout=TIMEOUT,
    )
    encoding = resp.headers.get("Content-Encoding")
    content_len = int(resp.headers.get("Content-Length", ""))
    expected_encoding = "gzip"
    # compression is conditionnaly applied server-side based on the actual content
    # size which we dont know from the headers.
    # in case compressed-content (content-length) is smaller than server threshold
    # we download content to check if its size is actually lower and only in this
    # case there should be no compression
    if (
        content_len <= KIWIX_MIN_CONTENT_SIZE_TO_COMPRESS
        and len(resp.content) <= KIWIX_MIN_CONTENT_SIZE_TO_COMPRESS
    ):
        expected_encoding = None
    assert encoding == expected_encoding


@pytest.mark.varnish
@pytest.mark.parametrize("path", OPDS_ENDPOINTS.keys())
def test_opds_is_cached(path):
    assert is_cached(path)


def test_illus_mimetypes(illus_endpoint):
    assert get_response_headers(illus_endpoint).get("Content-Type") == "image/png"


def test_illus_is_not_gzipped(illus_endpoint):
    assert "Content-Encoding" not in get_response_headers(illus_endpoint)


@pytest.mark.varnish
def test_illus_is_cached(illus_endpoint):
    assert is_cached(illus_endpoint)


@pytest.mark.varnish
def test_random_is_not_cached():
    assert not is_cached("/random/")


@pytest.mark.varnish
def test_viewer_settings_is_cached():
    assert is_cached("/viewer_settings.js")
