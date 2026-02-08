"""Pytest fixtures for pymessage tests."""

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def mock_chat_db(tmp_path: Path) -> Path:
    """Create a minimal mock chat.db for testing.

    Creates a SQLite database with realistic iMessage schema and sample data
    including messages, handles, chats, attachments, and reactions.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Path to the created chat.db file.
    """
    db_path = tmp_path / "chat.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create message table
    cursor.execute("""
        CREATE TABLE message (
            rowid INTEGER PRIMARY KEY,
            guid TEXT,
            text TEXT,
            date INTEGER,
            date_read INTEGER,
            is_from_me INTEGER,
            handle_id INTEGER,
            associated_message_type INTEGER,
            associated_message_guid TEXT
        )
    """)

    # Create handle table
    cursor.execute("""
        CREATE TABLE handle (
            rowid INTEGER PRIMARY KEY,
            id TEXT
        )
    """)

    # Create chat table
    cursor.execute("""
        CREATE TABLE chat (
            rowid INTEGER PRIMARY KEY,
            chat_identifier TEXT,
            service_name TEXT,
            display_name TEXT
        )
    """)

    # Create attachment table
    cursor.execute("""
        CREATE TABLE attachment (
            rowid INTEGER PRIMARY KEY,
            filename TEXT,
            mime_type TEXT,
            total_bytes INTEGER
        )
    """)

    # Create junction tables
    cursor.execute("""
        CREATE TABLE chat_message_join (
            chat_id INTEGER,
            message_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE chat_handle_join (
            chat_id INTEGER,
            handle_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE message_attachment_join (
            message_id INTEGER,
            attachment_id INTEGER
        )
    """)

    # Insert test handles (contacts)
    cursor.execute("INSERT INTO handle VALUES (1, '+12345678900')")
    cursor.execute("INSERT INTO handle VALUES (2, '+19876543210')")
    cursor.execute("INSERT INTO handle VALUES (3, 'user@example.com')")

    # Insert test chats
    # Chat 1: 1-on-1 conversation
    cursor.execute(
        "INSERT INTO chat VALUES (1, '+12345678900', 'iMessage', NULL)"
    )
    # Chat 2: Group chat
    cursor.execute(
        "INSERT INTO chat VALUES (2, 'chat123456789', 'iMessage', 'Test Group')"
    )

    # Insert test messages
    # Message 1: Regular text message (seconds format timestamp)
    cursor.execute("""
        INSERT INTO message VALUES (
            1, 'guid1', 'Hello, world!', 629990400, 629990500, 0, 1, NULL, NULL
        )
    """)
    # Message 2: Message from me (nanoseconds format timestamp)
    cursor.execute("""
        INSERT INTO message VALUES (
            2, 'guid2', 'Reply message', 630000000000000000, 0, 1, NULL, NULL, NULL
        )
    """)
    # Message 3: Group chat message
    cursor.execute("""
        INSERT INTO message VALUES (
            3, 'guid3', 'Group message', 630100000, 0, 0, 2, NULL, NULL
        )
    """)
    # Message 4: Reaction to message 1 (loved)
    cursor.execute("""
        INSERT INTO message VALUES (
            4, 'guid4', NULL, 630000100, 0, 0, 1, 2000, 'p:0/guid1'
        )
    """)
    # Message 5: Message with attachment
    cursor.execute("""
        INSERT INTO message VALUES (
            5, 'guid5', 'Photo attached', 630200000, 0, 0, 1, NULL, NULL
        )
    """)

    # Insert test attachment
    cursor.execute("""
        INSERT INTO attachment VALUES (
            1, 'Library/SMS/Attachments/ab/12/IMG_1234.jpg', 'image/jpeg', 102400
        )
    """)

    # Link messages to chats
    cursor.execute("INSERT INTO chat_message_join VALUES (1, 1)")
    cursor.execute("INSERT INTO chat_message_join VALUES (1, 2)")
    cursor.execute("INSERT INTO chat_message_join VALUES (1, 4)")
    cursor.execute("INSERT INTO chat_message_join VALUES (1, 5)")
    cursor.execute("INSERT INTO chat_message_join VALUES (2, 3)")

    # Link chats to handles (participants)
    cursor.execute("INSERT INTO chat_handle_join VALUES (1, 1)")  # 1-on-1 chat
    cursor.execute("INSERT INTO chat_handle_join VALUES (2, 1)")  # Group chat
    cursor.execute("INSERT INTO chat_handle_join VALUES (2, 2)")  # Group chat
    cursor.execute("INSERT INTO chat_handle_join VALUES (2, 3)")  # Group chat

    # Link message to attachment
    cursor.execute("INSERT INTO message_attachment_join VALUES (5, 1)")

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_backup(tmp_path: Path, mock_chat_db: Path) -> Path:
    """Create a minimal mock iPhone backup directory structure.

    Creates the directory structure with chat.db at the correct SHA-1 path
    as it appears in real iPhone backups.

    Args:
        tmp_path: Pytest temporary directory fixture.
        mock_chat_db: Path to mock chat database fixture.

    Returns:
        Path to the backup root directory.
    """
    backup_root = tmp_path / "mock_backup"
    backup_root.mkdir()

    # Create the SHA-1 path for chat.db
    chat_db_dir = backup_root / "3d"
    chat_db_dir.mkdir()

    # Copy mock chat.db to the expected location
    import shutil

    chat_db_path = chat_db_dir / "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
    shutil.copy(mock_chat_db, chat_db_path)

    return backup_root
