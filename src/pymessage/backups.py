"""iPhone backup discovery and metadata extraction.

This module provides utilities for finding iPhone backups on macOS and
extracting metadata from backup directories.
"""

import plistlib
from datetime import datetime
from pathlib import Path
from typing import Any


def find_backups() -> list[dict[str, Any]]:
    """Scan default macOS location for iPhone backups.

    Searches ~/Library/Application Support/MobileSync/Backup/ for backup
    directories and extracts metadata from each.

    Returns:
        List of backup metadata dictionaries, each containing:
        - path (Path): Absolute path to backup directory
        - device_name (str): Device name from Info.plist
        - last_backup (datetime): Last backup timestamp
        - ios_version (str): iOS version string
        - phone_number (str | None): Phone number if available
        - serial_number (str): Device serial number

    Examples:
        >>> backups = find_backups()
        >>> for backup in backups:
        ...     print(f"{backup['device_name']}: {backup['path']}")
        John's iPhone: /Users/user/Library/Application Support/MobileSync/Backup/abc123...
    """
    # Default macOS backup location
    backup_root = Path.home() / "Library" / "Application Support" / "MobileSync" / "Backup"

    if not backup_root.exists():
        return []

    backups = []
    for backup_dir in backup_root.iterdir():
        if backup_dir.is_dir():
            try:
                info = get_backup_info(backup_dir)
                backups.append(info)
            except (FileNotFoundError, ValueError):
                # Skip invalid backup directories
                continue

    # Sort by last backup date (most recent first)
    backups.sort(key=lambda x: x["last_backup"], reverse=True)

    return backups


def get_backup_info(backup_path: str | Path) -> dict[str, Any]:
    """Extract metadata from iPhone backup directory.

    Reads Info.plist and Manifest.plist to extract device information
    and backup details.

    Args:
        backup_path: Path to backup directory.

    Returns:
        Dictionary with backup metadata:
        - path (Path): Absolute path to backup directory
        - device_name (str): Device name from Info.plist
        - last_backup (datetime): Last backup timestamp
        - ios_version (str): iOS version string
        - phone_number (str | None): Phone number if available
        - serial_number (str): Device serial number

    Raises:
        FileNotFoundError: If backup_path doesn't exist.
        ValueError: If Info.plist is missing or malformed.

    Examples:
        >>> info = get_backup_info("/path/to/backup")
        >>> print(info["device_name"])
        John's iPhone
    """
    backup_path = Path(backup_path)

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup directory not found: {backup_path}")

    info_plist_path = backup_path / "Info.plist"
    if not info_plist_path.exists():
        raise ValueError(
            f"Info.plist not found in backup directory: {backup_path}"
        )

    plist_data = parse_info_plist(info_plist_path)

    return {
        "path": backup_path.absolute(),
        "device_name": plist_data.get("Device Name", "Unknown Device"),
        "last_backup": plist_data.get("Last Backup Date", datetime.now()),
        "ios_version": plist_data.get("Product Version", "Unknown"),
        "phone_number": plist_data.get("Phone Number"),
        "serial_number": plist_data.get("Serial Number", "Unknown"),
    }


def parse_info_plist(plist_path: Path) -> dict[str, Any]:
    """Parse Info.plist from iPhone backup.

    Uses standard library plistlib to read binary or XML plist format.

    Key fields extracted:
    - Device Name
    - Last Backup Date
    - Product Type (e.g., "iPhone12,1")
    - Product Version (iOS version)
    - Phone Number
    - Serial Number
    - IMEI

    Args:
        plist_path: Path to Info.plist file.

    Returns:
        Dictionary of parsed plist data.

    Raises:
        ValueError: If plist file is malformed.

    Examples:
        >>> data = parse_info_plist(Path("/path/to/Info.plist"))
        >>> print(data["Device Name"])
        John's iPhone
    """
    try:
        with open(plist_path, "rb") as f:
            plist_data = plistlib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse Info.plist: {e}") from e

    return plist_data
