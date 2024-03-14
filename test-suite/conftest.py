import re

import pytest
import requests
from utils import get_url


@pytest.fixture(scope="session")
def illus_endpoint():
    resp = requests.get(get_url(path="/catalog/search?count=1"), timeout=5)
    for line in resp.text.splitlines():

        match = re.search(r"/catalog/v2/illustration/([^/]+)/\?size=48", line)
        if match:
            yield match.group()
