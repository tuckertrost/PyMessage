"""iPhone backup discovery and metadata extraction.

This module provides utilities for finding iPhone backups on macOS and
extracting metadata from backup directories.
"""

import plistlib
import sqlite3
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Backup:
    """Represents a single iMessage data source.

    Wraps either an iPhone backup directory or the macOS Messages database
    into a unified object accepted by all pymessage functions.

    Attributes:
        type: Source type — "iphone" or "macos".
        path: Path to backup directory (iphone) or chat.db file (macos).
        device_name: Human-readable device label.
        last_backup: Timestamp of most recent backup, or None if unknown.
        ios_version: iOS version string (e.g. "17.2"), or None.
        phone_number: Device phone number, or None if unavailable.

    Examples:
        >>> backups = find_backups()
        >>> df = get_messages(backups[0])

        >>> print(backups[0])
        [iPhone] Tucker's iPhone (iOS 17.2) — Last backup: 2024-03-01
    """

    type: str
    path: Path
    device_name: str
    last_backup: datetime | None
    ios_version: str | None
    phone_number: str | None

    def __repr__(self) -> str:
        if self.type == "iphone":
            ios = f" (iOS {self.ios_version})" if self.ios_version else ""
            date = (
                f" \u2014 Last backup: {self.last_backup.date()}"
                if self.last_backup
                else ""
            )
            return f"[iPhone] {self.device_name}{ios}{date}"
        return f"[macOS] {self.device_name}"


def coerce_to_backup(backup) -> "Backup":
    """Accept a Backup object or a raw path string/Path to a chat.db file.

    Passing a raw path is a convenience shortcut — it wraps the path in a
    macOS-type Backup so callers can write::

        get_messages('/Users/me/Library/Messages/chat.db')

    instead of constructing a Backup manually.
    """
    if isinstance(backup, Backup):
        return backup
    path = Path(backup).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"chat.db not found at: {path}")
    return Backup(
        type="macos",
        path=path,
        device_name=str(path),
        last_backup=None,
        ios_version=None,
        phone_number=None,
    )


def find_backups() -> list[Backup]:
    """Scan for all available iMessage data sources.

    Searches ~/Library/Application Support/MobileSync/Backup/ for iPhone
    backups and checks ~/Library/Messages/chat.db for the macOS Messages
    database.

    Returns:
        List of Backup objects sorted by last backup date (most recent first),
        with the macOS entry appended at the end if found.

    Examples:
        >>> backups = find_backups()
        >>> for b in backups:
        ...     print(b)
        [iPhone] Tucker's iPhone (iOS 17.2) — Last backup: 2024-03-01
        [macOS] MacBook Messages
    """
    # Default macOS backup location
    backup_root = (
        Path.home() / "Library" / "Application Support" / "MobileSync" / "Backup"
    )

    backups: list[Backup] = []

    if backup_root.exists():
        raw: list[dict[str, Any]] = []
        for backup_dir in backup_root.iterdir():
            if backup_dir.is_dir():
                try:
                    info = get_backup_info(backup_dir)
                    raw.append(info)
                except (FileNotFoundError, ValueError):
                    continue

        # Sort by last backup date (most recent first)
        raw.sort(key=lambda x: x["last_backup"], reverse=True)

        for info in raw:
            backups.append(
                Backup(
                    type="iphone",
                    path=info["path"],
                    device_name=info["device_name"],
                    last_backup=info["last_backup"],
                    ios_version=info["ios_version"],
                    phone_number=info["phone_number"],
                )
            )

    # Check for macOS Messages database
    macos_db = Path.home() / "Library" / "Messages" / "chat.db"
    if macos_db.exists():
        try:
            conn = sqlite3.connect(f"file:{macos_db}?mode=ro", uri=True)
            conn.execute("SELECT COUNT(*) FROM message")
            conn.close()
            backups.append(
                Backup(
                    type="macos",
                    path=macos_db,
                    device_name="MacBook Messages",
                    last_backup=None,
                    ios_version=None,
                    phone_number=None,
                )
            )
        except Exception as e:
            warnings.warn(
                f"Found {macos_db} but could not open it: {e}\n"
                "This is usually a permissions issue. Grant Full Disk Access to your\n"
                "Terminal (or Python/Jupyter) in:\n"
                "  System Settings → Privacy & Security → Full Disk Access",
                stacklevel=2,
            )

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
