import re
import urllib.parse

import pytest
import requests
from utils import Mirror, get_current_mirrors, get_url

# MB only provides the full list of mirrors through this.
MIRRORS_LIST_URL: str = "https://download.kiwix.org/mirrors.html"
# list of mirrors (hostname) not to use in tests
EXCLUDED_MIRRORS: list[str] = []
# this is using the permalink pattern
# from the permalink redirects (no warehouse path, no period in filename)
# using wikipedia_he_* as this is the only pattern mirrored by all mirrors
# good enough for now
PERMANENT_ZIM_URL: str = "https://download.kiwix.org/zim/wikipedia_he_all_maxi.zim"
# all non-zim-only mirrors mirror all other files
PERMANENT_APK_URL: str = (
    "https://download.kiwix.org/release/kiwix-android/"
    "org.kiwix.kiwixmobile.standalone.apk"
)

# we have no other way to know which mirrors are supposed to have APKs
# taken from https://github.com/kiwix/container-images
#            /blob/main/mirrorbrain/bin/update_mirrorbrain_db.sh
EXPECTED_APK_MIRRORS: list[str] = [
    "mirrors.dotsrc.org",
    "mirror.download.kiwix.org",
    "ftp.nluug.nl",
    "ftp.fau.de",
    "md.mirrors.hacktegic.com",
    "mirror-sites-fr.mblibrary.info",
    "mirror-sites-in.mblibrary.info",
]
ZIM_MIRRORS: list[Mirror] = get_current_mirrors(MIRRORS_LIST_URL, EXCLUDED_MIRRORS)
# IDs are used for pytest output
ZIM_MIRRORS_IDS: list[str] = [mirror.hostname for mirror in ZIM_MIRRORS]
# we could have discovered mirrors via testing an actual APK online which would
# have included any extra mirror serving it but it causes other issues (chicken/egg)
# and expecting maintenance of tests on mirror update is OK
APK_MIRRORS: list[Mirror] = [
    mirror for mirror in ZIM_MIRRORS if mirror.hostname in EXPECTED_APK_MIRRORS
]
APK_MIRRORS_IDS: list[str] = [mirror.hostname for mirror in APK_MIRRORS]
PERMANENT_KIWIX_RELEASE_URL: str = (
    "https://download.kiwix.org/release/kiwix-tools/kiwix-tools_linux-x86_64.tar.gz"
)
PERMANENT_KIWIX_NIGHTLY_URL: str = (
    "https://download.kiwix.org/nightly/kiwix-tools_linux-x86_64.tar.gz"
)
PERMANENT_OPENZIM_RELEASE_URL: str = (
    "https://download.openzim.org/release/libzim/libzim.tar.xz"
)
PERMANENT_OPENZIM_NIGHTLY_URL: str = (
    "https://download.kiwix.org/nightly/libzim_linux-x86_64.tar.gz"
)


@pytest.fixture(scope="session")
def illus_endpoint():
    resp = requests.get(get_url(path="/catalog/search?count=1"), timeout=5)
    for line in resp.text.splitlines():

        match = re.search(r"/catalog/v2/illustration/([^/]+)/\?size=48", line)
        if match:
            yield match.group()


@pytest.fixture(scope="session")
def mirrors_list_url():
    yield MIRRORS_LIST_URL


@pytest.fixture(scope="session")
def excluded_mirrors():
    yield EXCLUDED_MIRRORS


@pytest.fixture(scope="session")
def permanent_zim_url():
    yield PERMANENT_ZIM_URL


@pytest.fixture(scope="session")
def current_zim_url(permanent_zim_url):
    resp = requests.head(permanent_zim_url, allow_redirects=False, timeout=5)
    resp.raise_for_status()
    yield resp.headers["Location"]


@pytest.fixture(scope="session")
def current_zim_path(current_zim_url):
    yield urllib.parse.urlparse(current_zim_url).path.lstrip("/")


@pytest.fixture(scope="session")
def permanent_apk_url():
    yield PERMANENT_APK_URL


@pytest.fixture(scope="session")
def current_apk_url(permanent_apk_url):
    resp = requests.head(permanent_apk_url, allow_redirects=False, timeout=5)
    resp.raise_for_status()
    yield resp.headers["Location"]


@pytest.fixture(scope="session")
def current_apk_path(current_apk_url):
    yield urllib.parse.urlparse(current_apk_url).path.lstrip("/")


@pytest.fixture(scope="session")
def current_zim_mirrors():
    yield ZIM_MIRRORS


@pytest.fixture(scope="session")
def current_apk_mirrors():
    yield APK_MIRRORS
