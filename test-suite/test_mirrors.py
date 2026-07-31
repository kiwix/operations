from http import HTTPStatus
from urllib.parse import urljoin, urlparse

import pytest
import requests
from conftest import (
    APK_MIRRORS,
    APK_MIRRORS_IDS,
    EXPECTED_APK_MIRRORS,
    PERMANENT_KIWIX_NIGHTLY_URL,
    PERMANENT_KIWIX_RELEASE_URL,
    PERMANENT_OPENZIM_NIGHTLY_URL,
    PERMANENT_OPENZIM_RELEASE_URL,
    PERMANENT_ZIM_URL,
    ZIM_MIRRORS,
    ZIM_MIRRORS_IDS,
)
from utils import TIMEOUT, USER_AGENT_HEADERS, Headers, Mirror


def no_http_transit_for(url: str) -> bool:
    resp = requests.head(
        url, allow_redirects=True, timeout=TIMEOUT, headers=USER_AGENT_HEADERS
    )
    if urlparse(resp.url).scheme != "https":
        return False
    for sub_resp in resp.history:
        if urlparse(sub_resp.url).scheme != "https":
            return False
    return True


def test_kiwix_release_map():
    assert no_http_transit_for(PERMANENT_KIWIX_RELEASE_URL)


def test_kiwix_nightly_map():
    assert no_http_transit_for(PERMANENT_KIWIX_NIGHTLY_URL)


def test_kiwix_zim_map():
    assert no_http_transit_for(PERMANENT_ZIM_URL)


def test_openzim_release_map():
    assert no_http_transit_for(PERMANENT_OPENZIM_RELEASE_URL)


def test_openzim_nightly_map():
    assert no_http_transit_for(PERMANENT_OPENZIM_NIGHTLY_URL)


def test_mirrors_list_reachable(mirrors_list_url, ua_headers: Headers):
    assert (
        requests.head(
            mirrors_list_url, allow_redirects=True, headers=ua_headers
        ).status_code
        == HTTPStatus.OK
    )


def test_zim_exists(permanent_zim_url, current_zim_url, ua_headers: Headers):
    assert (
        requests.head(
            permanent_zim_url, allow_redirects=True, headers=ua_headers
        ).status_code
        == HTTPStatus.OK
    )
    assert (
        requests.head(
            current_zim_url, allow_redirects=True, headers=ua_headers
        ).status_code
        == HTTPStatus.OK
    )


def test_zim_permalink(permanent_zim_url, current_zim_url, ua_headers: Headers):
    assert (
        requests.head(
            permanent_zim_url, allow_redirects=True, timeout=TIMEOUT, headers=ua_headers
        ).url
        == requests.head(
            current_zim_url, allow_redirects=True, timeout=TIMEOUT, headers=ua_headers
        ).url
    )


def test_zim_mirrors_list(current_zim_mirrors):
    # arbitrary number ; should fail if we dont get this (currently it's 14)
    assert len(current_zim_mirrors) >= 12


@pytest.mark.parametrize("mirror", ZIM_MIRRORS, ids=ZIM_MIRRORS_IDS)
def test_mirror_has_zim_file(
    mirror: Mirror, current_zim_path: str, ua_headers: Headers
):
    url = urljoin(mirror.base_url, current_zim_path)
    assert (
        requests.head(
            url,
            timeout=TIMEOUT,
            allow_redirects=mirror.is_load_balancer,
            headers=ua_headers,
        ).status_code
        == HTTPStatus.OK
    )


@pytest.mark.parametrize("mirror", ZIM_MIRRORS, ids=ZIM_MIRRORS_IDS)
def test_mirror_zim_has_contenttype(
    mirror: Mirror, current_zim_path: str, ua_headers: Headers
):
    url = urljoin(mirror.base_url, current_zim_path)
    assert requests.head(
        url,
        timeout=TIMEOUT,
        allow_redirects=mirror.is_load_balancer,
        headers=ua_headers,
    ).headers.get("content-type")


@pytest.mark.parametrize("mirror", ZIM_MIRRORS, ids=ZIM_MIRRORS_IDS)
def test_mirror_zim_contenttype(
    mirror: Mirror, current_zim_path: str, ua_headers: Headers
):
    url = urljoin(mirror.base_url, current_zim_path)
    print(url)
    ctype = requests.head(
        url,
        timeout=TIMEOUT,
        allow_redirects=mirror.is_load_balancer,
        headers=ua_headers,
    ).headers.get("content-type")
    if ctype is None:
        pytest.xfail("no content-type")
    assert ctype in (
        "application/octet-stream",
        "application/x-zim",
        "application/x-openzim",  # not correct but does not harm
    )


def test_apk_exists(permanent_apk_url, current_apk_url, ua_headers: Headers):
    assert (
        requests.head(
            permanent_apk_url,
            allow_redirects=True,
            headers=ua_headers,
        ).status_code
        == HTTPStatus.OK
    )
    assert (
        requests.head(
            current_apk_url,
            allow_redirects=True,
            headers=ua_headers,
        ).status_code
        == HTTPStatus.OK
    )


def test_apk_permalink(permanent_apk_url, current_apk_url, ua_headers: Headers):
    assert (
        requests.head(
            permanent_apk_url,
            allow_redirects=True,
            timeout=TIMEOUT,
            headers=ua_headers,
        ).url
        == requests.head(
            current_apk_url,
            allow_redirects=True,
            timeout=TIMEOUT,
            headers=ua_headers,
        ).url
    )


def test_apk_mirrors_list(current_apk_mirrors):
    # ATM this is no-op but prevents further issues
    assert len(current_apk_mirrors) >= len(EXPECTED_APK_MIRRORS)


@pytest.mark.parametrize("mirror", APK_MIRRORS, ids=APK_MIRRORS_IDS)
def test_mirror_has_apk_file(
    mirror: Mirror, current_apk_path: str, ua_headers: Headers
):
    url = urljoin(mirror.base_url, current_apk_path)
    assert (
        requests.head(
            url,
            timeout=TIMEOUT,
            allow_redirects=mirror.is_load_balancer,
            headers=ua_headers,
        ).status_code
        == HTTPStatus.OK
    )


@pytest.mark.parametrize("mirror", APK_MIRRORS, ids=APK_MIRRORS_IDS)
def test_mirror_apk_has_contenttype(
    mirror: Mirror, current_apk_path: str, ua_headers: Headers
):
    url = urljoin(mirror.base_url, current_apk_path)
    assert requests.head(
        url,
        timeout=TIMEOUT,
        allow_redirects=mirror.is_load_balancer,
        headers=ua_headers,
    ).headers.get("content-type")


@pytest.mark.parametrize("mirror", APK_MIRRORS, ids=APK_MIRRORS_IDS)
def test_mirror_apk_contenttype(
    mirror: Mirror, current_apk_path: str, ua_headers: Headers
):
    url = urljoin(mirror.base_url, current_apk_path)
    ctype = requests.head(
        url,
        timeout=TIMEOUT,
        allow_redirects=mirror.is_load_balancer,
        headers=ua_headers,
    ).headers.get("content-type")
    if ctype is None:
        pytest.xfail("no content-type")
    assert ctype == "application/vnd.android.package-archive"
