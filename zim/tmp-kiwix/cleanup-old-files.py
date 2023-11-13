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

import os
import argparse
import datetime

def list_files_to_delete(folder_path, days):
    """
    List files that are older than a specified number of days.

    Args:
        folder_path (str): The path to the target folder.
        days (int): Delete files older than this many days.

    Returns:
        list: A list of file paths to be deleted.
    """
    current_time = datetime.datetime.now()
    files_to_delete = []

    def list_files(folder_path):
        for foldername, subfolders, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                yield file_path

    for file_path in list_files(folder_path):
        # Get the last modification time of the file
        file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

        # Calculate the difference in days
        days_difference = (current_time - file_time).days

        if days_difference > days:
            files_to_delete.append(file_path)

    return files_to_delete

def list_directories_to_delete(folder_path, files_to_delete):
    """
    List empty subdirectories or subdirectories containing only files to be deleted.

    Args:
        folder_path (str): The path to the target folder.
        files_to_delete (list): A list of file paths to be deleted.

    Returns:
        list: A list of empty subdirectories to be deleted.
    """
    empty_directories_to_delete = []

    for foldername, subfolders, filenames in os.walk(folder_path):
        for subfolder in subfolders:
            subfolder_path = os.path.join(foldername, subfolder)
            
            # Check if the directory is already empty or contains only files that will be deleted
            if not os.listdir(subfolder_path) or all(os.path.join(subfolder_path, filename) in files_to_delete for filename in os.listdir(subfolder_path)):
                empty_directories_to_delete.append(subfolder_path)

    return empty_directories_to_delete

def process_deletion(dry_run, files_to_delete, empty_directories_to_delete):
    """
    Process file and directory deletion based on the dry-run status.

    Args:
        dry_run (bool): True for dry-run, False for actual deletion.
        files_to_delete (list): A list of file paths to be deleted.
        empty_directories_to_delete (list): A list of empty subdirectories to be deleted.
    """
    if dry_run:
        print(f"These files would be deleted:")
        print("\n".join(files_to_delete))
        print("\nEmpty subdirectories that would be deleted:")
        print("\n".join(empty_directories_to_delete))
    else:
        print(f"Deleting files:")
        for file_path in files_to_delete:
            os.remove(file_path)
            print(f"Deleted: {file_path}")

        print(f"\nDeleting empty subdirectories:")
        for directory_path in empty_directories_to_delete:
            os.rmdir(directory_path)
            print(f"Deleted empty directory: {directory_path}")

def main():
    """
    Main function to parse arguments and initiate the deletion process.
    """
    parser = argparse.ArgumentParser(description="Delete old files and empty subdirectories.")
    parser.add_argument("-d", "--dry-run", action="store_true", default=False, help="Perform a dry run (default: False)")
    parser.add_argument("-f", "--folder", required=True, help="Path to the target folder")
    parser.add_argument("-n", "--days", type=int, default=30, help="Delete files older than this many days (default: 30)")

    args = parser.parse_args()

    files_to_delete = list_files_to_delete(args.folder, args.days)
    empty_directories_to_delete = list_directories_to_delete(args.folder, files_to_delete)

    process_deletion(args.dry_run, files_to_delete, empty_directories_to_delete)

if __name__ == "__main__":
    main()
