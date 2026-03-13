"""Conversation management and metadata retrieval.

This module provides utilities for listing conversations, retrieving participant
information, and analyzing conversation metadata.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from pymessage.backups import coerce_to_backup
from pymessage.contacts import build_contacts_lookup
from pymessage.db import ChatDatabase
from pymessage.schema import GROUP_CHAT_PREFIX, convert_apple_timestamp
from pymessage.utils import normalize_phone_number


def list_conversations(
    backup,
    include_empty: bool = False,
) -> pd.DataFrame:
    """List all conversations with summary statistics.

    Returns metadata about each conversation including participant count,
    message count, and date range.

    Args:
        backup: A Backup object specifying the data source. Use find_backups()
            to discover available sources, or EXAMPLE_BACKUP for testing.
        include_empty: Include conversations with no messages (default False).

    Returns:
        DataFrame with columns:
        - chat_id (str): Chat identifier
        - is_group_chat (bool): True if group conversation
        - participants (list[str]): List of phone numbers/emails
        - participant_count (int): Number of participants
        - message_count (int): Total messages in conversation
        - first_message (pd.Timestamp): Earliest message timestamp
        - last_message (pd.Timestamp): Most recent message timestamp
        - display_name (str | None): Chat display name if available

    Raises:
        FileNotFoundError: If specified path doesn't exist.

    Examples:
        >>> from pymessage import find_backups, list_conversations
        >>> backups = find_backups()
        >>> df = list_conversations(backups[0])
        >>> # Filter to group chats only
        >>> groups = df[df["is_group_chat"] == True]
        >>> # Sort by most active
        >>> df.sort_values("message_count", ascending=False)
    """
    backup = coerce_to_backup(backup)

    with ChatDatabase(backup) as conn:
        # Query chat statistics
        query = """
            SELECT
                c.rowid as chat_id_num,
                c.chat_identifier,
                c.display_name,
                c.service_name,
                COUNT(DISTINCT cmj.message_id) as message_count,
                MIN(m.date) as first_message_date,
                MAX(m.date) as last_message_date,
                COUNT(DISTINCT chj.handle_id) as participant_count
            FROM chat c
            LEFT JOIN chat_message_join cmj ON c.rowid = cmj.chat_id
            LEFT JOIN message m ON cmj.message_id = m.rowid
            LEFT JOIN chat_handle_join chj ON c.rowid = chj.chat_id
            GROUP BY c.rowid
            HAVING message_count > 0 OR ?
            ORDER BY last_message_date DESC
        """

        df = pd.read_sql_query(query, conn, params=[include_empty])

        # Get participants for each chat
        if not df.empty:
            df["participants"] = df["chat_id_num"].apply(
                lambda cid: get_participants(cid, conn)
            )
        else:
            df["participants"] = None

    contacts_lookup = build_contacts_lookup(backup)

    # Process DataFrame
    df = _process_conversations_dataframe(df, contacts_lookup)

    return df


def get_participants(chat_id: int, conn: sqlite3.Connection) -> list[str]:
    """Get list of participant phone numbers/emails for a chat.

    Args:
        chat_id: Chat rowid from database.
        conn: Database connection.

    Returns:
        List of participant identifiers (phone numbers or emails).

    Examples:
        >>> with ChatDatabase(db_path="/path/to/chat.db") as conn:
        ...     participants = get_participants(1, conn)
        ...     print(participants)
        ['+12345678900', '+19876543210']
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT h.id
        FROM handle h
        JOIN chat_handle_join chj ON h.rowid = chj.handle_id
        WHERE chj.chat_id = ?
    """,
        [chat_id],
    )

    return [row[0] for row in cursor.fetchall()]


def is_group_chat(chat_identifier: str, participant_count: int) -> bool:
    """Determine if chat is a group conversation.

    Group chats are identified by:
    1. chat_identifier starts with "chat" prefix, OR
    2. More than 2 participants

    Args:
        chat_identifier: Chat identifier from database.
        participant_count: Number of participants.

    Returns:
        True if group chat, False for 1-on-1.

    Examples:
        >>> is_group_chat("chat123456789", 3)
        True
        >>> is_group_chat("+12345678900", 2)
        False
        >>> is_group_chat("+12345678900", 3)
        True
    """
    if pd.isna(chat_identifier):
        return False

    return chat_identifier.startswith(GROUP_CHAT_PREFIX) or participant_count > 2


def _process_conversations_dataframe(df: pd.DataFrame, contacts_lookup: dict) -> pd.DataFrame:
    """Process raw conversations query results into clean DataFrame.

    Args:
        df: Raw DataFrame from SQL query.
        contacts_lookup: Mapping of normalized phone number to display name.

    Returns:
        Processed DataFrame with clean columns.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "chat_id",
                "contact_name",
                "is_group_chat",
                "participants",
                "participant_count",
                "message_count",
                "first_message",
                "last_message",
                "display_name",
            ]
        )

    # Convert timestamps
    df["first_message"] = df["first_message_date"].apply(convert_apple_timestamp)
    df["last_message"] = df["last_message_date"].apply(convert_apple_timestamp)

    # Detect group chats
    df["is_group_chat"] = df.apply(
        lambda row: is_group_chat(row["chat_identifier"], row["participant_count"]),
        axis=1,
    )

    # Rename columns
    df = df.rename(columns={"chat_identifier": "chat_id"})

    # Resolve contact_name: for 1-on-1 chats look up chat_id (the phone number);
    # for group chats use display_name if set, else None.
    def _resolve_convo_name(row):
        if row["is_group_chat"]:
            dn = row["display_name"]
            return dn if pd.notna(dn) and dn else None
        chat_id = row["chat_id"]
        if not isinstance(chat_id, str):
            return chat_id
        if contacts_lookup:
            normalized = normalize_phone_number(chat_id)
            if normalized in contacts_lookup:
                return contacts_lookup[normalized]
        return chat_id

    df["contact_name"] = df.apply(_resolve_convo_name, axis=1)

    # Select final columns in desired order
    columns = [
        "chat_id",
        "contact_name",
        "is_group_chat",
        "participants",
        "participant_count",
        "message_count",
        "first_message",
        "last_message",
        "display_name",
    ]

    return df[columns]
