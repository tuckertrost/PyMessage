"""Database connection and management utilities.

This module provides utilities for connecting to iMessage chat databases,
locating databases within iPhone backup directories, and validating parameters.
"""

import sqlite3
from pathlib import Path

from pymessage.schema import CHAT_DB_HASH_PATH


class ChatDatabase:
    """Context manager for iMessage chat database connections.

    Handles both direct database paths and iPhone backup directories,
    automatically locating chat.db within backups using the known SHA-1 path.

    Examples:
        >>> # Direct database path
        >>> with ChatDatabase(db_path="/path/to/chat.db") as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT COUNT(*) FROM message")
        ...     print(cursor.fetchone()[0])

        >>> # iPhone backup directory
        >>> with ChatDatabase(backup_path="/path/to/backup") as conn:
        ...     # chat.db automatically located
        ...     cursor = conn.cursor()
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        backup_path: Path | str | None = None,
    ) -> None:
        """Initialize ChatDatabase context manager.

        Args:
            db_path: Direct path to chat.db file (mutually exclusive with backup_path).
            backup_path: Path to iPhone backup directory (mutually exclusive with db_path).

        Raises:
            ValueError: If both or neither of db_path/backup_path provided.
            FileNotFoundError: If specified path doesn't exist.
        """
        self.resolved_db_path = validate_db_params(db_path, backup_path)
        self.conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        """Enter context and open database connection.

        Returns:
            Open SQLite connection to chat database.
        """
        self.conn = sqlite3.connect(self.resolved_db_path)
        # Enable row factory for easier access to results
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and close database connection."""
        if self.conn:
            self.conn.close()


def validate_db_params(
    db_path: Path | str | None, backup_path: Path | str | None
) -> Path:
    """Validate and resolve database parameters.

    Ensures exactly one of db_path or backup_path is provided, converts to Path,
    and validates existence.

    Args:
        db_path: Direct path to chat.db file.
        backup_path: Path to iPhone backup directory.

    Returns:
        Resolved Path object pointing to chat.db.

    Raises:
        ValueError: If both or neither parameter provided.
        FileNotFoundError: If specified path doesn't exist.

    Examples:
        >>> path = validate_db_params(db_path="/path/to/chat.db", backup_path=None)
        >>> path = validate_db_params(db_path=None, backup_path="/path/to/backup")
    """
    if db_path and backup_path:
        raise ValueError(
            "Must provide exactly one of 'backup_path' or 'db_path', not both. "
            "Use backup_path='/path/to/backup' for iPhone backups, or "
            "db_path='/path/to/chat.db' for direct database access."
        )

    if not db_path and not backup_path:
        raise ValueError(
            "Must provide either 'backup_path' or 'db_path'. "
            "Use backup_path='/path/to/backup' for iPhone backups, or "
            "db_path='/path/to/chat.db' for direct database access."
        )

    if db_path:
        db_path = Path(db_path)
        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")
        return db_path

    # backup_path must be provided
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup directory not found: {backup_path}")

    return locate_chat_db(backup_path)


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
