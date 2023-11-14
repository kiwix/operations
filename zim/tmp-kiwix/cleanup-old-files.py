#!/usr/local/bin/python3

"""
File and Directory Deletion Script

This script performs the deletion of files older than a specified number of days and
deletes empty subdirectories in a specified folder.

Usage:
    python cleanup-old-files.py -f /path/to/folder -n 30 [-d]

Options:
    -d, --dry-run   Perform a dry run to list the files and directories that would be deleted.
                    If not specified, the script performs the actual deletion.
    -f, --folder    Path to the target folder.
    -n, --days      Delete files older than this many days. Default is 30 days.
"""

import argparse
import datetime
from pathlib import Path


def list_files_to_delete(folder_path: Path, days: int) -> list[Path]:
    """List files that are older than a specified number of days."""
    minimum_time = (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()
    files_to_delete: list[Path] = []
    for file_path in folder_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.stat().st_mtime < minimum_time:
            files_to_delete.append(file_path)

    return files_to_delete


def list_directories_to_delete(
    folder_path: Path, files_to_delete: list[Path]
) -> list[Path]:
    """List empty subdirectories or subdirectories containing only files to be deleted."""
    empty_directories_to_delete: list[Path] = []

    for file in files_to_delete:
        current_parent = file.parent

        # Check recursively if the parent directory is not the root processing folder
        # and if it is still relative to this root folder (probably a no brainer)
        # and it is not already selected for deletion
        # and it is already empty or contains only files/directories that will be deleted
        while (
            current_parent != folder_path
            and current_parent.is_relative_to(folder_path)
            and current_parent not in empty_directories_to_delete
            and all(
                item in files_to_delete or item in empty_directories_to_delete
                for item in current_parent.iterdir()
            )
        ):
            empty_directories_to_delete.append(current_parent)
            current_parent = current_parent.parent

    return empty_directories_to_delete


def process_deletion(
    dry_run: bool, files_to_delete: list[Path], empty_directories_to_delete: list[Path]
):
    """Process file and directory deletion based on the dry-run status."""
    if dry_run:
        print(f"These files would be deleted:")
        print("\n".join(sorted(str(path) for path in files_to_delete)))
        print("\nEmpty subdirectories that would be deleted:")
        print("\n".join(sorted(str(path) for path in empty_directories_to_delete)))
    else:
        print(f"Deleting files:")
        for file_path in files_to_delete:
            file_path.unlink()
            print(f"Deleted: {file_path}")

        print(f"\nDeleting empty subdirectories:")
        for directory_path in empty_directories_to_delete:
            try:
                directory_path.rmdir()
                print(f"Deleted empty directory: {directory_path}")
            except OSError as ex:
                # do not fail script when we fail to delete a directory since this has
                # almost zero impact on storage + it might happen that a file is created
                # between our inventory and the real directory deletion
                print(f"Failed to delete directory {directory_path}:\n{ex}")


def main():
    """Main function to parse arguments and initiate the deletion process."""
    parser = argparse.ArgumentParser(
        description="Delete old files and empty subdirectories."
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        default=False,
        help="Perform a dry run (default: False)",
    )
    parser.add_argument(
        "-f", "--folder", required=True, help="Path to the target folder"
    )
    parser.add_argument(
        "-n",
        "--days",
        type=int,
        default=30,
        help="Delete files older than this many days (default: 30)",
    )

    args = parser.parse_args()

    folder_path = Path(args.folder)
    files_to_delete = list_files_to_delete(folder_path, args.days)
    empty_directories_to_delete = list_directories_to_delete(
        folder_path, files_to_delete
    )

    process_deletion(args.dry_run, files_to_delete, empty_directories_to_delete)


if __name__ == "__main__":
    main()
