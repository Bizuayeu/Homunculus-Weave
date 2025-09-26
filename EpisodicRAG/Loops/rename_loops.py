#!/usr/bin/env python3
"""
Script to rename Loop files from 3-digit to 4-digit format.
Example: Loop001_title.txt -> Loop0001_title.txt
"""
import os
import re
import sys

def main():
    # Get the current directory
    loops_dir = os.path.dirname(os.path.abspath(__file__))

    # Pattern to match Loop files with 3-digit numbers
    pattern = re.compile(r'^(Loop)(\d{3})(_.*\.txt)$')

    # Get all files in the directory
    files = os.listdir(loops_dir)

    # Track renaming operations
    rename_operations = []

    # Find files to rename
    for filename in files:
        match = pattern.match(filename)
        if match:
            prefix = match.group(1)
            number = match.group(2)
            suffix = match.group(3)

            # Create new filename with 4-digit format
            new_number = number.zfill(4)
            new_filename = f"{prefix}{new_number}{suffix}"

            # Add to operations list
            rename_operations.append((filename, new_filename))

    # Display what will be renamed
    if not rename_operations:
        print("No files found to rename.")
        return

    print(f"Found {len(rename_operations)} files to rename:")
    print("-" * 50)
    for old_name, new_name in rename_operations[:5]:
        print(f"  {old_name} -> {new_name}")
    if len(rename_operations) > 5:
        print(f"  ... and {len(rename_operations) - 5} more files")
    print("-" * 50)

    # Ask for confirmation
    response = input("\nProceed with renaming? (y/n): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        return

    # Perform the renaming
    success_count = 0
    error_count = 0

    for old_name, new_name in rename_operations:
        old_path = os.path.join(loops_dir, old_name)
        new_path = os.path.join(loops_dir, new_name)

        try:
            # Check if target already exists
            if os.path.exists(new_path):
                print(f"Warning: {new_name} already exists, skipping...")
                error_count += 1
                continue

            # Rename the file
            os.rename(old_path, new_path)
            print(f"Renamed: {old_name} -> {new_name}")
            success_count += 1

        except Exception as e:
            print(f"Error renaming {old_name}: {e}")
            error_count += 1

    # Print summary
    print("\n" + "=" * 50)
    print(f"Renaming complete!")
    print(f"  Successfully renamed: {success_count} files")
    if error_count > 0:
        print(f"  Errors: {error_count} files")
    print("=" * 50)

if __name__ == "__main__":
    main()