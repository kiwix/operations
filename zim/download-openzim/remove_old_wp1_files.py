import argparse
import re
import shutil
import sys
from pathlib import Path

PATTERN = re.compile(r"^(?P<ident>[a-z\-]+)_(?P<date>\d{4}-\d{2})$")


def folders_to_delete(root: Path, nb_to_keep: int) -> list[Path]:

    # compute map of all matching _ident_ with their sorted versions
    folders: dict[str, list[str]] = {}
    for path in root.iterdir():
        if not path.is_dir or not PATTERN.match(path.name):
            continue
        ident, version = PATTERN.match(path.name).groupdict().values()
        if ident not in folders:
            folders[ident] = []
        folders[ident].append(version)
        folders[ident].sort()

    # exclude all of those that have less than 2 versions and remove last 2 versions
    to_remove: list[Path] = []
    for ident, versions in folders.items():
        for version in versions[:-nb_to_keep]:
            to_remove.append(root.joinpath(f"{ident}_{version}"))
    return to_remove


def delete_folders(folders: list[Path]):
    for folder in folders:
        shutil.rmtree(folder, ignore_errors=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete old WP1 version folders")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Only list version folders to be deleted, dont actually delete.",
        dest="dry_run",
    )

    parser.add_argument(
        "--keep-versions",
        type=int,
        default=2,
        help="Number of versions to keep (older will be removed)",
        dest="nb_to_keep",
    )

    parser.add_argument(help="Path to the target folder", dest="folder", type=Path)

    args = parser.parse_args()

    to_remove = folders_to_delete(root=args.folder.expanduser().resolve(), nb_to_keep=args.nb_to_keep)
    print("Version folders to delete:")
    print("- " + "\n- ".join([p.name for p in to_remove]))

    if args.dry_run:
        print("DRY-RUN, nothing deleted. exiting.")
        return 0

    delete_folders(to_remove)
    print(f"Deleted {len(to_remove)} version folders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
