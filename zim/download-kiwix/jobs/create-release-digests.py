#!/usr/bin/env python3

import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Callable

import humanfriendly

DEBUG = bool(os.getenv("DEBUG"))

logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
logger = logging.getLogger("release-digest")


def get_digest_for(fpath: Path, func: Callable, chunk_size: int):
    """hashname, diget for a file"""
    h = func()
    with open(fpath, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.name, h.hexdigest()


def scan_and_compute(root: Path, digester: Callable, suffix: str, chunk_size: int):
    errors = skipped = computed = 0
    for fpath in root.rglob("*.*"):
        if fpath.is_dir() or fpath.suffix in (suffix, ".xml", ""):  # (feed.xml)
            continue
        logger.debug(fpath)
        digest_path = fpath.with_suffix(f"{fpath.suffix}{suffix}")
        if digest_path.exists():
            skipped += 1
            continue

        logger.debug(f"MISSING: {digest_path}")

        try:
            _, digest = get_digest_for(
                fpath=fpath, func=digester, chunk_size=chunk_size
            )
            digest_path.write_text(f"{digest}  {fpath.name}")
        except Exception as exc:
            logger.error(f"failed to compute/write digest for {fpath}: {exc!s}")
            logger.debug(exc, exc_info=True)
            errors += 1
        else:
            computed += 1
    return errors, skipped, computed


def main(roots: list[Path], digester: Callable, suffix: str, chunk_size: int) -> int:
    logger.info(f"Starting digest creator with {digester=}, {suffix=}, {chunk_size=}")
    total_nb_errors = total_nb_skipped = total_nb_computed = 0
    for root in roots:
        logger.info(f"Traversing {root!s}…")
        try:
            nb_errors, nb_skipped, nb_computed = scan_and_compute(
                root=root, digester=digester, suffix=suffix, chunk_size=chunk_size
            )
        except Exception as exc:
            logger.error("Exception processing {root!s}: {exc!s}")
            logger.exception(exc, stack_info=True)
            return 1
        logger.info(
            f"Done computing digests for {root}:"
            f"\n- {nb_errors=}\n- {nb_skipped=}\n- {nb_computed=}"
        )
        total_nb_errors += nb_errors
        total_nb_skipped += nb_skipped
        total_nb_computed += nb_computed
    logger.info(
        "Overall stats:"
        f"\n- {total_nb_errors=}\n- {total_nb_skipped=}\n- {total_nb_computed=}"
    )

    return total_nb_errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="create-release-digests",
        description="Computes MD5 digest for all files, stored next to them",
    )

    parser.add_argument(
        "--alg",
        help="Which algorithm to digest with (hashlib). Default to md5.",
        dest="alg",
        default="md5",
    )
    parser.add_argument(
        "--suffix",
        help="File suffix to store digest in. Default to .md5",
        dest="suffix",
        default=".md5",
    )
    parser.add_argument(
        "--chunk-size",
        help="Chunk size to use when computing digest. Larger means faster but consumes more RAM and CPU. Single file at a time though. Default to 8MiB",
        dest="chunk_size",
        type=humanfriendly.parse_size,
        default="8MiB",
    )

    parser.add_argument(
        "folders",
        help="Folder to scan and compute digest for",
        type=Path,
        nargs="+",
    )
    args = parser.parse_args()

    sys.exit(
        main(
            roots=[folder.expanduser().resolve() for folder in args.folders],
            digester=getattr(hashlib, args.alg),
            suffix=args.suffix,
            chunk_size=args.chunk_size,
        )
    )
