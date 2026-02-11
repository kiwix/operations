import os
from http import HTTPStatus
from queue import SimpleQueue
from unittest.mock import patch
from urllib.parse import urlsplit

import aiodns
import pycares
import pytest
import requests

# purposely using a custom name so it's not picked up automatically
IP6_PROXY = os.getenv("IP6_PROXY", "")

ALLOWED_STATUSES = (
    HTTPStatus.OK,
    HTTPStatus.PERMANENT_REDIRECT,
    HTTPStatus.TEMPORARY_REDIRECT,
    HTTPStatus.MOVED_PERMANENTLY,
    HTTPStatus.FOUND,
    HTTPStatus.NOT_FOUND,  # might have 404 (android), not our business
)


def get_proxies(ipv6: bool = False) -> dict[str, str] | None:
    return {"http": IP6_PROXY, "https": IP6_PROXY} if ipv6 else None


async def declares_ip6(domain) -> bool:
    """ whether a domain name has an AAAA record """
    async with aiodns.DNSResolver() as resolver:
        try:
            result = await resolver.query_dns(domain, "AAAA")
        except aiodns.error.DNSError:
            return False
        for record in result.answer:
            if record.type == pycares.QUERY_TYPE_CNAME:
                return await declares_ip6(record.data.cname)
            return record.type == pycares.QUERY_TYPE_AAAA
        return False


def get_domain_for(url: str) -> str:
    """ domain name from URL so we can query DNS """
    return urlsplit(url).hostname or ""


@pytest.mark.asyncio
async def test_all_urls(recorded_urls):

    all_urls = SimpleQueue()
    for url in recorded_urls:
        all_urls.put(url)
    checked_urls = set()
    print(f"Starting with {all_urls.qsize()} URLs")

    while not all_urls.empty():
        url = all_urls.get()
        if url in checked_urls:
            print(f"> already seen {url}")
            continue
        test_v6 = await declares_ip6(get_domain_for(url))
        proxy = get_proxies(ipv6=test_v6)

        print(f"[v4] {url}")
        resp = requests.get(url, stream=True, allow_redirects=False)
        assert resp.status_code in ALLOWED_STATUSES
        if resp.is_redirect and resp.next:
            all_urls.put(resp.next.url)

        if test_v6:
            print(f"[v6] {url}")
            resp = requests.get(url, proxies=proxy, stream=True, allow_redirects=False)
            assert resp.status_code in ALLOWED_STATUSES
            if resp.is_redirect and resp.next:
                all_urls.put(resp.next.url)

        checked_urls.add(url)

    print(f"{len(checked_urls)=}")
