#!/usr/bin/env python3

"""forever-tunning script whitelisting Kiwix Catalog ZIM torrents in the Tracker

- Fetches minibrain endpoint returning list of all BT info hashes
- Stores them in memory (~300KB)
- Adds the one we didn't have to the tracker whitelist using the API
- Sleeps until next iteration
"""

# /// script
# dependencies = [
#   "requests<3",
#   "humanfriendly==10.0",
# ]
# ///

import logging
import os
import sys
import time

import humanfriendly
import requests
import requests.adapters

API_URL = os.environ["API_URL"]
API_STARTUP_DURATION = humanfriendly.parse_timespan(
    os.getenv("API_STARTUP_DURATION") or "30s"
)
BTIHS_SOURCE_URL = (
    os.getenv("BTIHS_SOURCE_URL", "")
    or "https://lb.download.kiwix.org/well-known/btihs.txt"
)
DEBUG = bool(os.getenv("DEBUG") or "")
REFRESH_INTERVAL = humanfriendly.parse_timespan(os.getenv("REFRESH_INTERVAL") or "1h")
TOKEN = os.environ["TOKEN"]
TIMEOUT = int(os.getenv("TIMEOUT") or "30")
USER_AGENT = os.getenv("USER_AGENT", "kiwix-bot/1.0 (tracker-whitelister)")

logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)
logger = logging.getLogger("whitelister")
should_top: bool = False

session: requests.Session = requests.Session()
session.headers["User-Agent"] = USER_AGENT
whitelist: list[str] = []


def contact_api() -> int:
    """Nb of torrents in tracker. Serves as API test allowing it to fail for a bit

    Returns -1 if API could not be reached"""
    last_exc = None
    for _ in range(int(API_STARTUP_DURATION)):
        try:
            resp = session.get(
                f"{API_URL}/stats", params={"token": TOKEN}, timeout=TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()["torrents"]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to contact API: {exc!s}")
            last_exc = exc
            time.sleep(1)
            continue
    logger.exception(last_exc)
    raise OSError(f"Unable to contact API: {last_exc!s}")


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


def refresh() -> tuple[int, int]:
    """nb of new btih found and nb of actually added to the tracker"""
    resp = session.get(url=BTIHS_SOURCE_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    nb_new, nb_added = 0, 0
    all_btihs = resp.text.splitlines()
    logger.debug(f"Received {len(all_btihs):,} info hashes")
    for btih in all_btihs:
        if btih not in whitelist:
            nb_new += 1
            if add_torrent(btih):
                nb_added += 1
                whitelist.append(btih)
    return nb_new, nb_added


def pause():
    """wait for next refresh iteration"""
    logger.debug(f"pausing for {humanfriendly.format_timespan(REFRESH_INTERVAL)}")
    # micro 1s pause to allow interrupt
    for _ in range(int(REFRESH_INTERVAL)):
        time.sleep(1)


def main() -> int:
    logger.info("Starting whitelister")
    logger.debug(f"- {API_URL=}")
    logger.debug(f"- {TOKEN=}")
    logger.debug(
        f"- REFRESH_INTERVAL={humanfriendly.format_timespan(REFRESH_INTERVAL)}"
    )

    nb_torrents = contact_api()
    logger.info(f"API Connection successful. {nb_torrents:,} torrents in the Tracker")

    while not should_top:
        try:
            nb_new, nb_added = refresh()
            if not nb_new:
                logger.info("No new btih")
            elif nb_new == nb_added:
                logger.info(f"Added {nb_added:,} new btih")
            else:
                logger.info(f"Added {nb_added:,} new btih but {nb_new:,} received")
        except Exception as exc:
            logger.error(f"Failed to refresh: {exc!s}")
            logger.exception(exc)
        pause()
    return 0


if __name__ == "__main__":
    sys.exit(main())
