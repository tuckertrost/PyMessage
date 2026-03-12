"""Message retrieval and DataFrame construction.

This module provides the primary get_messages() function for retrieving
iMessage messages from chat databases and returning clean pandas DataFrames.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

from pymessage.contacts import build_contacts_lookup
from pymessage.db import ChatDatabase
from pymessage.schema import (
    GROUP_CHAT_PREFIX,
    convert_apple_timestamp,
    parse_attributed_body,
    parse_reaction_type,
)
from pymessage.utils import generate_phone_variants, normalize_phone_number


def get_messages(
    backup,
    phone_numbers: str | list[str] | None = None,
    date_range: tuple[str | datetime, str | datetime] | None = None,
    output_csv: str | Path | None = None,
) -> pd.DataFrame:
    """Retrieve iMessage messages from a chat database.

    Query messages with optional filtering by phone numbers and date range.
    Returns a pandas DataFrame with message details, attachments, and reactions.

    Args:
        backup: A Backup object specifying the data source. Use find_backups()
            to discover available sources, or EXAMPLE_BACKUP for testing.
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
        - contact_name (str): Display name from handle table, or "Me" for sent messages
        - message_text (str): Text content of message
        - is_from_me (bool): True if sent by device owner
        - chat_id (str): Chat identifier
        - is_group_chat (bool): True if group conversation
        - attachment_path (str | None): Path to attachment file
        - reaction_type (str | None): Type of reaction if this is a tapback
        - reaction_action (str | None): "add" or "remove" for reactions

    Raises:
        ValueError: If date_range has invalid format.
        FileNotFoundError: If specified path doesn't exist.

    Examples:
        >>> from pymessage import find_backups, get_messages
        >>> backups = find_backups()
        >>> df = get_messages(backups[0])

        >>> # Get messages for specific contact
        >>> df = get_messages(backups[0], phone_numbers="+1234567890")

        >>> # Get messages in date range and export to CSV
        >>> df = get_messages(
        ...     backups[0],
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

    # Build contacts lookup from AddressBook (higher priority than handle table)
    contacts_lookup = build_contacts_lookup(backup)

    # Execute query and build handle lookup (fallback when no contacts entry)
    with ChatDatabase(backup) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, uncanonicalized_id FROM handle")
        handle_lookup = {
            row["id"]: (row["uncanonicalized_id"] or row["id"])
            for row in cursor.fetchall()
        }
        df = pd.read_sql_query(query, conn, params=params)

    # Process DataFrame
    df = _process_message_dataframe(df, handle_lookup, contacts_lookup)

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
            m.attributedBody,
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

        # Filter by chat_identifier matching the phone number.
        # 1-on-1 chats use the contact's phone number as chat_identifier,
        # so this naturally excludes group chats (which use "chat..." IDs).
        placeholders = ",".join("?" * len(all_variants))
        query += f" AND c.chat_identifier IN ({placeholders})"
        params.extend(all_variants)

    # Add date range filter. The message.date column uses two formats:
    #   - nanoseconds since 2001-01-01 (modern iOS, m.date >= 1e12)
    #   - seconds since 2001-01-01 (older iOS, m.date < 1e12)
    # Both must be handled so the comparison is meaningful either way.
    _NS_THRESH = 1_000_000_000_000  # same as schema.NANOSECOND_THRESHOLD
    apple_epoch = pd.Timestamp("2001-01-01", tz="UTC")

    if start_date is not None:
        start_seconds = (start_date - apple_epoch).total_seconds()
        start_ns = int(start_seconds * 1_000_000_000)
        query += (
            f" AND ((m.date >= {_NS_THRESH} AND m.date >= ?)"
            f" OR (m.date < {_NS_THRESH} AND m.date >= ?))"
        )
        params.extend([start_ns, start_seconds])

    if end_date is not None:
        end_seconds = (end_date - apple_epoch).total_seconds()
        end_ns = int(end_seconds * 1_000_000_000)
        query += (
            f" AND ((m.date >= {_NS_THRESH} AND m.date <= ?)"
            f" OR (m.date < {_NS_THRESH} AND m.date <= ?))"
        )
        params.extend([end_ns, end_seconds])

    query += " ORDER BY m.date ASC"

    return (query, params)


def _process_message_dataframe(
    df: pd.DataFrame,
    handle_lookup: dict[str, str],
    contacts_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Process raw query results into clean DataFrame.

    Applies timestamp conversion, reaction parsing, group chat detection,
    contact name resolution, and column renaming.

    Args:
        df: Raw DataFrame from SQL query.
        handle_lookup: Mapping of handle.id to display name (uncanonicalized_id
            or fallback to id).
        contacts_lookup: Optional mapping of normalized phone number to display
            name from the system AddressBook (higher priority than handle_lookup).

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
                "contact_name",
                "message_text",
                "is_from_me",
                "chat_id",
                "is_group_chat",
                "attachment_path",
                "reaction_type",
                "reaction_action",
            ]
        )

    # Fall back to attributedBody when text is NULL (modern macOS/iOS)
    mask = df["text"].isna()
    if mask.any():
        df.loc[mask, "text"] = df.loc[mask, "attributedBody"].apply(
            parse_attributed_body
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

    # Resolve contact name: AddressBook name > handle table > raw sender
    def _resolve_name(r):
        if r["is_from_me"]:
            return "Me"
        sender = r["sender"]
        if contacts_lookup and isinstance(sender, str):
            normalized = normalize_phone_number(sender)
            if normalized in contacts_lookup:
                return contacts_lookup[normalized]
        return handle_lookup.get(sender, sender)

    df["contact_name"] = df.apply(_resolve_name, axis=1)

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
        "contact_name",
        "message_text",
        "is_from_me",
        "chat_id",
        "is_group_chat",
        "attachment_path",
        "reaction_type",
        "reaction_action",
    ]

    return df[columns]
