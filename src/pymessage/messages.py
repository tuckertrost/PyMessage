"""Message retrieval and DataFrame construction.

This module provides the primary get_messages() function for retrieving
iMessage messages from chat databases and returning clean pandas DataFrames.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

from pymessage.db import ChatDatabase
from pymessage.schema import (
    GROUP_CHAT_PREFIX,
    convert_apple_timestamp,
    parse_reaction_type,
)
from pymessage.utils import generate_phone_variants, normalize_phone_number


def get_messages(
    backup_path: str | Path | None = None,
    db_path: str | Path | None = None,
    phone_numbers: str | list[str] | None = None,
    date_range: tuple[str | datetime, str | datetime] | None = None,
    output_csv: str | Path | None = None,
) -> pd.DataFrame:
    """Retrieve iMessage messages from iPhone backup database.

    Query messages with optional filtering by phone numbers and date range.
    Returns a pandas DataFrame with message details, attachments, and reactions.

    Args:
        backup_path: Path to iPhone backup directory (mutually exclusive with db_path).
        db_path: Direct path to chat.db file (mutually exclusive with backup_path).
        phone_numbers: Single phone number or list to filter conversations.
            Accepts various formats: "+1234567890", "(123) 456-7890", "email@example.com"
        date_range: Tuple of (start, end) dates for filtering. Dates can be:
            - ISO format strings: "2024-01-01", "2024-12-31"
            - datetime objects
            If None, returns all messages.
        output_csv: Optional path to export results as CSV.

    Returns:
        DataFrame with columns:
        - timestamp (pd.Timestamp): Message timestamp in UTC
        - read_at (pd.Timestamp | None): When message was read (None if unread)
        - sender (str): Phone number or email of sender
        - message_text (str): Text content of message
        - is_from_me (bool): True if sent by device owner
        - chat_id (str): Chat identifier
        - is_group_chat (bool): True if group conversation
        - attachment_path (str | None): Path to attachment file in backup
        - reaction_type (str | None): Type of reaction if this is a tapback
        - reaction_action (str | None): "add" or "remove" for reactions

    Raises:
        ValueError: If both or neither of backup_path/db_path provided.
        ValueError: If date_range has invalid format.
        FileNotFoundError: If specified path doesn't exist.

    Examples:
        >>> # Get all messages from backup
        >>> df = get_messages(backup_path="/path/to/backup")

        >>> # Get messages for specific contact
        >>> df = get_messages(
        ...     backup_path="/path/to/backup",
        ...     phone_numbers="+1234567890"
        ... )

        >>> # Get messages in date range and export to CSV
        >>> df = get_messages(
        ...     db_path="/path/to/chat.db",
        ...     date_range=("2024-01-01", "2024-12-31"),
        ...     output_csv="messages.csv"
        ... )
    """
    # Normalize phone numbers to list
    phone_list = _normalize_phone_input(phone_numbers)

    # Parse date range
    start_date, end_date = _parse_date_range(date_range)

    # Build SQL query
    query, params = _build_message_query(phone_list, start_date, end_date)

    # Execute query
    with ChatDatabase(db_path=db_path, backup_path=backup_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    # Process DataFrame
    df = _process_message_dataframe(df)

    # Export to CSV if requested
    if output_csv:
        df.to_csv(output_csv, index=False)

    return df


def _normalize_phone_input(phone_numbers: str | list[str] | None) -> list[str] | None:
    """Normalize phone number input to list of normalized numbers.

    Args:
        phone_numbers: Single phone number, list of numbers, or None.

    Returns:
        List of normalized phone numbers, or None.
    """
    if phone_numbers is None:
        return None

    if isinstance(phone_numbers, str):
        phone_numbers = [phone_numbers]

    return [normalize_phone_number(phone) for phone in phone_numbers]


def _parse_date_range(
    date_range: tuple[str | datetime, str | datetime] | None,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Parse date range tuple into pandas Timestamps.

    Args:
        date_range: Tuple of (start, end) dates as strings or datetime objects.

    Returns:
        Tuple of (start_timestamp, end_timestamp) or (None, None).

    Raises:
        ValueError: If date_range format is invalid or start > end.
    """
    if date_range is None:
        return (None, None)

    if not isinstance(date_range, tuple) or len(date_range) != 2:
        raise ValueError(
            "date_range must be a tuple of (start, end) dates. "
            "Example: ('2024-01-01', '2024-12-31')"
        )

    start, end = date_range

    try:
        start_ts = pd.to_datetime(start, utc=True)
        end_ts = pd.to_datetime(end, utc=True)
    except Exception as e:
        raise ValueError(
            f"Invalid date format in date_range: {e}. "
            "Use ISO format strings like '2024-01-01' or datetime objects."
        ) from e

    if start_ts > end_ts:
        raise ValueError(
            f"date_range start ({start}) must be before end ({end})"
        )

    return (start_ts, end_ts)


def _build_message_query(
    phone_list: list[str] | None,
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> tuple[str, list]:
    """Build SQL query for retrieving messages with filters.

    Args:
        phone_list: List of normalized phone numbers for filtering.
        start_date: Start date filter (pandas Timestamp).
        end_date: End date filter (pandas Timestamp).

    Returns:
        Tuple of (sql_query, parameters) for parameterized execution.
    """
    query = """
        SELECT
            m.rowid,
            m.text,
            m.date,
            m.date_read,
            m.is_from_me,
            m.associated_message_type,
            h.id as sender,
            c.chat_identifier,
            a.filename as attachment_path
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.rowid
        LEFT JOIN chat_message_join cmj ON m.rowid = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.rowid
        LEFT JOIN message_attachment_join maj ON m.rowid = maj.message_id
        LEFT JOIN attachment a ON maj.attachment_id = a.rowid
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

    # Add date range filter (convert pandas timestamps to Apple epoch)
    if start_date is not None:
        # Convert to seconds since Apple epoch (2001-01-01)
        apple_epoch = pd.Timestamp("2001-01-01", tz="UTC")
        start_seconds = (start_date - apple_epoch).total_seconds()
        query += " AND m.date >= ?"
        params.append(start_seconds)

    if end_date is not None:
        apple_epoch = pd.Timestamp("2001-01-01", tz="UTC")
        end_seconds = (end_date - apple_epoch).total_seconds()
        query += " AND m.date <= ?"
        params.append(end_seconds)

    query += " ORDER BY m.date ASC"

    return (query, params)


def _process_message_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Process raw query results into clean DataFrame.

    Applies timestamp conversion, reaction parsing, group chat detection,
    and column renaming.

    Args:
        df: Raw DataFrame from SQL query.

    Returns:
        Processed DataFrame with clean columns.
    """
    if df.empty:
        # Return empty DataFrame with correct columns
        return pd.DataFrame(
            columns=[
                "timestamp",
                "read_at",
                "sender",
                "message_text",
                "is_from_me",
                "chat_id",
                "is_group_chat",
                "attachment_path",
                "reaction_type",
                "reaction_action",
            ]
        )

    # Convert timestamps
    df["timestamp"] = df["date"].apply(convert_apple_timestamp)
    df["read_at"] = df["date_read"].apply(convert_apple_timestamp)

    # Parse reactions
    reactions = df["associated_message_type"].apply(parse_reaction_type)
    df["reaction_type"] = reactions.apply(lambda x: x[0])
    df["reaction_action"] = reactions.apply(lambda x: x[1])

    # Detect group chats
    df["is_group_chat"] = df["chat_identifier"].apply(
        lambda x: x.startswith(GROUP_CHAT_PREFIX) if pd.notna(x) else False
    )

    # Convert is_from_me to boolean
    df["is_from_me"] = df["is_from_me"].astype(bool)

    # Select and rename columns
    df = df.rename(
        columns={
            "text": "message_text",
            "chat_identifier": "chat_id",
        }
    )

    # Select final columns in desired order
    columns = [
        "timestamp",
        "read_at",
        "sender",
        "message_text",
        "is_from_me",
        "chat_id",
        "is_group_chat",
        "attachment_path",
        "reaction_type",
        "reaction_action",
    ]

    return df[columns]
