"""Attachment retrieval and path resolution.

This module provides utilities for retrieving attachment metadata and
resolving attachment file paths within iPhone backup directories.
"""

import hashlib
from pathlib import Path

import pandas as pd

from pymessage.db import ChatDatabase
from pymessage.macos import resolve_macos_attachment_path
from pymessage.schema import convert_apple_timestamp
from pymessage.utils import generate_phone_variants, normalize_phone_number


def get_attachments(
    backup,
    phone_numbers: str | list[str] | None = None,
) -> pd.DataFrame:
    """Retrieve attachment metadata and file paths.

    Returns information about all attachments in conversations,
    optionally filtered by phone numbers.

    Args:
        backup: A Backup object specifying the data source. Use find_backups()
            to discover available sources, or EXAMPLE_BACKUP for testing.
        phone_numbers: Filter to attachments in these conversations.

    Returns:
        DataFrame with columns:
        - attachment_id (int): Attachment rowid
        - message_id (int): Associated message rowid
        - filename (str): Original filename
        - mime_type (str): MIME type (e.g., "image/jpeg")
        - file_size (int): Size in bytes
        - file_path (str | None): Resolved path to attachment file
        - timestamp (pd.Timestamp): Message timestamp
        - sender (str): Sender phone/email

    Raises:
        FileNotFoundError: If specified path doesn't exist.

    Examples:
        >>> from pymessage import find_backups, get_attachments
        >>> backups = find_backups()
        >>> df = get_attachments(backups[0])
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

    # Execute query
    with ChatDatabase(backup) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    # Process DataFrame
    df = _process_attachments_dataframe(df, backup)

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

        # Filter by chat_identifier matching the phone number.
        # Attachments query doesn't join chat tables, so use a subquery
        # through chat_message_join → chat to match on chat_identifier.
        placeholders = ",".join("?" * len(all_variants))
        query += f"""
            AND m.rowid IN (
                SELECT cmj.message_id FROM chat_message_join cmj
                JOIN chat c2 ON cmj.chat_id = c2.rowid
                WHERE c2.chat_identifier IN ({placeholders})
            )
        """
        params.extend(all_variants)

    query += " ORDER BY m.date DESC"

    return (query, params)


def _process_attachments_dataframe(
    df: pd.DataFrame,
    backup,
) -> pd.DataFrame:
    """Process raw attachments query results into clean DataFrame.

    Args:
        df: Raw DataFrame from SQL query.
        backup: Backup object used to determine path resolution strategy.

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
                "file_path",
                "timestamp",
                "sender",
            ]
        )

    # Convert timestamps
    df["timestamp"] = df["date"].apply(convert_apple_timestamp)

    # Resolve attachment file paths based on source
    if backup.type == "macos":
        df["file_path"] = df["filename"].apply(
            lambda f: str(resolve_macos_attachment_path(f))
            if pd.notna(f)
            else None
        )
    elif backup.type == "iphone":
        backup_root = Path(backup.path)
        def _resolve_backup(f):
            if not pd.notna(f):
                return None
            p = resolve_attachment_path(f, backup_root)
            return str(p) if p is not None else None
        df["file_path"] = df["filename"].apply(_resolve_backup)
    else:
        df["file_path"] = None

    # Select final columns in desired order
    columns = [
        "attachment_id",
        "message_id",
        "filename",
        "mime_type",
        "file_size",
        "file_path",
        "timestamp",
        "sender",
    ]

    return df[columns]
