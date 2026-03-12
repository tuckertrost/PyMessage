"""Database connection and management utilities.

This module provides utilities for connecting to iMessage chat databases,
locating databases within iPhone backup directories, and validating parameters.
"""

import sqlite3
from pathlib import Path

from pymessage.schema import CHAT_DB_HASH_PATH


class ChatDatabase:
    """Context manager for iMessage chat database connections.

    Accepts a Backup object and opens the appropriate SQLite connection,
    using read-only mode for macOS databases to avoid lock conflicts
    with the Messages app.

    Examples:
        >>> backups = find_backups()
        >>> with ChatDatabase(backups[0]) as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT COUNT(*) FROM message")
        ...     print(cursor.fetchone()[0])
    """

    def __init__(self, backup) -> None:
        """Initialize ChatDatabase context manager.

        Args:
            backup: A Backup object specifying the data source.
                type="iphone" opens the chat.db inside the backup directory.
                type="macos" opens the chat.db read-only.

        Raises:
            ValueError: If backup.type is not "iphone" or "macos".
            FileNotFoundError: If the database file cannot be found.
        """
        self.resolved_db_path = validate_db_params(backup)
        self.is_macos = backup.type == "macos"
        self.conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        """Enter context and open database connection.

        Returns:
            Open SQLite connection to chat database.
        """
        if self.is_macos:
            # Open read-only to avoid lock conflicts with Messages app
            self.conn = sqlite3.connect(
                f"file:{self.resolved_db_path}?mode=ro", uri=True
            )
        else:
            self.conn = sqlite3.connect(self.resolved_db_path)
        # Enable row factory for easier access to results
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and close database connection."""
        if self.conn:
            self.conn.close()


def validate_db_params(backup) -> Path:
    """Validate a Backup object and return the resolved path to chat.db.

    Args:
        backup: A Backup object with type "iphone" or "macos".

    Returns:
        Resolved Path object pointing to chat.db.

    Raises:
        ValueError: If backup.type is not "iphone" or "macos".
        FileNotFoundError: If the database cannot be located.

    Examples:
        >>> backups = find_backups()
        >>> path = validate_db_params(backups[0])
    """
    if backup.type == "macos":
        return Path(backup.path)

    if backup.type == "iphone":
        backup_path = Path(backup.path)
        if not backup_path.exists():
            raise FileNotFoundError(
                f"Backup directory not found: {backup_path}"
            )
        return locate_chat_db(backup_path)

    raise ValueError(
        f"Invalid backup type: {backup.type!r}. Must be 'iphone' or 'macos'."
    )


def locate_chat_db(backup_path: Path) -> Path:
    """Locate chat.db within iPhone backup using known SHA-1 path.

    The chat.db file is always at a fixed location within iPhone backups:
    backup_root/3d/3d0d7e5fb2ce288813306e4d4636395e047a3d28

    Args:
        backup_path: Root directory of iPhone backup.

    Returns:
        Absolute path to chat.db file.

    Raises:
        FileNotFoundError: If chat.db not found at expected location.

    Examples:
        >>> db_path = locate_chat_db(Path("/path/to/backup"))
        >>> print(db_path)
        /path/to/backup/3d/3d0d7e5fb2ce288813306e4d4636395e047a3d28
    """
    chat_db_path = backup_path / CHAT_DB_HASH_PATH

    if not chat_db_path.exists():
        raise FileNotFoundError(
            f"chat.db not found at expected location: {chat_db_path}. "
            f"Ensure this is a valid iPhone backup directory."
        )

    return chat_db_path
