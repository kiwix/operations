#!/usr/bin/env python3

import argparse
import re
import sys
import tempfile
from pathlib import Path

PATTERN = re.compile(r"^(?P<ident>[a-z\-]+)_(?P<date>\d{4}-\d{2})$")


def run(root: Path, map_path: Path, dry_run: bool) -> int:
    print(f"Creating WP1 redirects map from {root!s} to {map_path!s} with {dry_run=}")

    # compute map of all matching _ident_ with their sorted versions
    folders: dict[str, str] = {}
    for path in root.iterdir():
        if not path.is_dir or not PATTERN.match(path.name):
            continue
        ident, version = PATTERN.match(path.name).groupdict().values()
        if ident not in folders or version > folders[ident]:
            folders[ident] = version

    tmp_file = Path(
        tempfile.NamedTemporaryFile(
            prefix=f"{map_path.stem}_",
            suffix=map_path.suffix,
            dir=map_path.parent,
            delete=False,
        ).name
    )
    try:
        with open(tmp_file, "w") as fh:
            for ident, version in folders.items():
                line = rf"~^/{ident}(|[^_].*)$ /{ident}_{version}$1;"
                print(line)
                fh.write(line)

        if dry_run:
            print("DRY-RUN, no change to map file.")
            return 0

        tmp_file.rename(map_path)
    finally:
        tmp_file.unlink(missing_ok=True)

    print(f"Updated {map_path!s}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create nginx redirects map so version-less redirects to latest version"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Only list version folders to be deleted, dont actually delete.",
        dest="dry_run",
    )

    parser.add_argument(help="WP1 data folder", dest="folder", type=Path)
    parser.add_argument(help="Path to the target folder", dest="target", type=Path)

    args = parser.parse_args()
    return run(
        root=args.folder.expanduser().resolve(),
        map_path=args.target.expanduser().resolve(),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
