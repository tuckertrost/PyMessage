"""Attachment retrieval and path resolution.

This module provides utilities for retrieving attachment metadata and
resolving attachment file paths within iPhone backup directories.
"""

import hashlib
from pathlib import Path

import pandas as pd

from pymessage.db import ChatDatabase
from pymessage.schema import convert_apple_timestamp
from pymessage.utils import generate_phone_variants, normalize_phone_number


def get_attachments(
    backup_path: str | Path | None = None,
    db_path: str | Path | None = None,
    phone_numbers: str | list[str] | None = None,
) -> pd.DataFrame:
    """Retrieve attachment metadata and file paths.

    Returns information about all attachments in conversations,
    optionally filtered by phone numbers.

    Args:
        backup_path: Path to iPhone backup directory (mutually exclusive with db_path).
        db_path: Direct path to chat.db file (mutually exclusive with backup_path).
        phone_numbers: Filter to attachments in these conversations.

    Returns:
        DataFrame with columns:
        - attachment_id (int): Attachment rowid
        - message_id (int): Associated message rowid
        - filename (str): Original filename
        - mime_type (str): MIME type (e.g., "image/jpeg")
        - file_size (int): Size in bytes
        - backup_path (str | None): Full path in backup if backup_path provided
        - timestamp (pd.Timestamp): Message timestamp
        - sender (str): Sender phone/email

    Raises:
        ValueError: If both or neither of backup_path/db_path provided.
        FileNotFoundError: If specified path doesn't exist.

    Examples:
        >>> df = get_attachments(backup_path="/path/to/backup")
        >>> # Filter to images only
        >>> images = df[df["mime_type"].str.startswith("image/")]
    """
    # Normalize phone numbers to list
    phone_list = None
    if phone_numbers is not None:
        if isinstance(phone_numbers, str):
            phone_numbers = [phone_numbers]
        phone_list = [normalize_phone_number(phone) for phone in phone_numbers]

    # Build SQL query
    query, params = _build_attachments_query(phone_list)

    # Determine backup root if backup_path provided
    backup_root = Path(backup_path) if backup_path else None

    # Execute query
    with ChatDatabase(db_path=db_path, backup_path=backup_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    # Process DataFrame
    df = _process_attachments_dataframe(df, backup_root)

    return df


def resolve_attachment_path(filename: str, backup_root: Path) -> Path | None:
    """Resolve attachment filename to actual path in backup.

    iPhone backups store files using SHA1 hash of domain and relative path:
    path = SHA1("MediaDomain-" + relative_path)
    Structure: backup_root/[first_2_hex]/[full_hash]

    Args:
        filename: Relative filename from attachment table.
        backup_root: Root directory of backup.

    Returns:
        Absolute path to attachment file, or None if not found.

    Examples:
        >>> path = resolve_attachment_path(
        ...     "Library/SMS/Attachments/ab/12/IMG_1234.jpg",
        ...     Path("/path/to/backup")
        ... )
        >>> print(path)
        /path/to/backup/41/41746ffc65924078eae42725c979305626f57cca
    """
    if not filename:
        return None

    # Compute SHA1 hash of "MediaDomain-" + filename
    domain_path = f"MediaDomain-{filename}"
    hash_digest = hashlib.sha1(domain_path.encode()).hexdigest()

    # Build path: backup_root/[first_2]/[full_hash]
    file_path = backup_root / hash_digest[:2] / hash_digest

    return file_path if file_path.exists() else None


def _build_attachments_query(
    phone_list: list[str] | None,
) -> tuple[str, list]:
    """Build SQL query for retrieving attachments with filters.

    Args:
        phone_list: List of normalized phone numbers for filtering.

    Returns:
        Tuple of (sql_query, parameters) for parameterized execution.
    """
    query = """
        SELECT
            a.rowid as attachment_id,
            m.rowid as message_id,
            a.filename,
            a.mime_type,
            a.total_bytes as file_size,
            m.date,
            h.id as sender
        FROM attachment a
        JOIN message_attachment_join maj ON a.rowid = maj.attachment_id
        JOIN message m ON maj.message_id = m.rowid
        LEFT JOIN handle h ON m.handle_id = h.rowid
        WHERE 1=1
    """

    params = []

    # Add phone number filter
    if phone_list:
        # Generate all variants for all phone numbers
        all_variants = []
        for phone in phone_list:
            all_variants.extend(generate_phone_variants(phone))

        # Build IN clause with placeholders
        placeholders = ",".join("?" * len(all_variants))
        query += f" AND h.id IN ({placeholders})"
        params.extend(all_variants)

    query += " ORDER BY m.date DESC"

    return (query, params)


def _process_attachments_dataframe(
    df: pd.DataFrame, backup_root: Path | None
) -> pd.DataFrame:
    """Process raw attachments query results into clean DataFrame.

    Args:
        df: Raw DataFrame from SQL query.
        backup_root: Backup root path for resolving attachment paths.

    Returns:
        Processed DataFrame with clean columns.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "attachment_id",
                "message_id",
                "filename",
                "mime_type",
                "file_size",
                "backup_path",
                "timestamp",
                "sender",
            ]
        )

    # Convert timestamps
    df["timestamp"] = df["date"].apply(convert_apple_timestamp)

    # Resolve backup paths if backup_root provided
    if backup_root:
        df["backup_path"] = df["filename"].apply(
            lambda f: str(resolve_attachment_path(f, backup_root))
            if pd.notna(f)
            else None
        )
    else:
        df["backup_path"] = None

    # Select final columns in desired order
    columns = [
        "attachment_id",
        "message_id",
        "filename",
        "mime_type",
        "file_size",
        "backup_path",
        "timestamp",
        "sender",
    ]

    return df[columns]
