from http import HTTPStatus

import pytest
import requests
from utils import (
    COMPRESSABLE_OPDS_ENDPOINTS,
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
    assert get_response_headers(path, method="GET").get("Content-Encoding") == "gzip"


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
