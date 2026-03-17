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


def _locate_in_manifest(backup_path: Path, domain: str, relative_path: str) -> Path | None:
    """Look up a file in Manifest.db and return its hash path within the backup.

    Manifest.db is the SQLite index iTunes writes to every backup directory
    (on both Windows and macOS). It maps each file's SHA-1 hash to its original
    domain and relative path on the device.

    Args:
        backup_path: Root directory of the iPhone backup.
        domain: iTunes domain (e.g. "HomeDomain").
        relative_path: File path relative to domain root (e.g. "Library/SMS/sms.db").

    Returns:
        Full path to the hashed file within the backup, or None if Manifest.db
        does not exist or the file has no entry in it.

    Raises:
        ValueError: If Manifest.db exists but cannot be read as a SQLite
            database, which indicates the backup is encrypted.
    """
    manifest = backup_path / "Manifest.db"
    if not manifest.exists():
        return None
    try:
        conn = sqlite3.connect(manifest)
        row = conn.execute(
            "SELECT fileID FROM Files WHERE domain = ? AND relativePath = ?",
            (domain, relative_path),
        ).fetchone()
        conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(
            "This backup appears to be encrypted. Disable backup encryption in "
            "iTunes (Windows) or Finder (macOS) under the device's backup settings "
            "and create a new unencrypted backup."
        ) from exc
    if row is None:
        return None
    file_id = row[0]
    return backup_path / file_id[:2] / file_id


def locate_chat_db(backup_path: Path) -> Path:
    """Locate chat.db within an iPhone backup directory.

    Queries Manifest.db first (the standard iTunes backup index present on
    both Windows and macOS), then falls back to the known SHA-1 hash path for
    older backups that lack a manifest.

    Args:
        backup_path: Root directory of iPhone backup.

    Returns:
        Absolute path to chat.db file.

    Raises:
        ValueError: If the backup is encrypted (Manifest.db cannot be read).
        FileNotFoundError: If chat.db cannot be found at any known location.

    Examples:
        >>> db_path = locate_chat_db(Path("/path/to/backup"))
        >>> print(db_path)
        /path/to/backup/3d/3d0d7e5fb2ce288813306e4d4636395e047a3d28
    """
    # Manifest.db lookup (preferred — gives clear encrypted-backup errors)
    path = _locate_in_manifest(backup_path, "HomeDomain", "Library/SMS/sms.db")
    if path is not None and path.exists():
        return path

    # Fallback: hardcoded SHA-1 path for backups without Manifest.db
    path = backup_path / CHAT_DB_HASH_PATH
    if path.exists():
        return path

    raise FileNotFoundError(
        f"chat.db not found in backup: {backup_path}. "
        "Ensure this is a valid, unencrypted iPhone backup."
    )
