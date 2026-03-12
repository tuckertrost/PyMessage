"""macOS Messages database discovery and validation.

This module provides utilities for locating and validating the macOS
Messages chat.db database, which requires Full Disk Access permission.
"""

import platform
import sqlite3
from pathlib import Path

# Default macOS Messages database location
MACOS_CHAT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"


def find_macos_db() -> Path:
    """Locate the macOS Messages chat.db database.

    Checks for the existence and readability of ~/Library/Messages/chat.db.
    This database requires Full Disk Access permission in macOS System Settings.

    Returns:
        Path to the macOS chat.db file.

    Raises:
        OSError: If not running on macOS.
        FileNotFoundError: If chat.db does not exist at the expected location.
        PermissionError: If Full Disk Access has not been granted.

    Examples:
        >>> db_path = find_macos_db()
        >>> print(db_path)
        /Users/username/Library/Messages/chat.db
    """
    if platform.system() != "Darwin":
        raise OSError(
            "macOS Messages database is only available on macOS. "
            "Use backup_path for iPhone backups on other platforms."
        )

    if not MACOS_CHAT_DB_PATH.exists():
        raise FileNotFoundError(
            f"macOS Messages database not found at: {MACOS_CHAT_DB_PATH}"
        )

    # Test readability — Full Disk Access is required
    try:
        conn = sqlite3.connect(
            f"file:{MACOS_CHAT_DB_PATH}?mode=ro", uri=True
        )
        conn.execute("SELECT COUNT(*) FROM message")
        conn.close()
    except sqlite3.OperationalError as e:
        raise PermissionError(
            f"Cannot read macOS Messages database: {e}. "
            "Grant Full Disk Access to your terminal application:\n"
            "  System Settings > Privacy & Security > Full Disk Access\n"
            "Then restart your terminal."
        ) from e

    return MACOS_CHAT_DB_PATH


def resolve_macos_attachment_path(filename: str) -> Path | None:
    """Resolve attachment filename from macOS Messages database to real path.

    In the macOS Messages database, attachment filenames are stored as
    absolute paths with ~ prefix (e.g., ~/Library/Messages/Attachments/...).
    This function expands the path and verifies the file exists.

    Args:
        filename: Filename from the attachment table (may start with ~).

    Returns:
        Absolute path to the attachment file, or None if not found.

    Examples:
        >>> path = resolve_macos_attachment_path(
        ...     "~/Library/Messages/Attachments/ab/12/IMG_1234.jpg"
        ... )
    """
    if not filename:
        return None

    expanded = Path(filename).expanduser()
    return expanded if expanded.exists() else None
