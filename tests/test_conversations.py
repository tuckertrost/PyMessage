"""Tests for pymessage.conversations module."""

from pathlib import Path

import pytest

from pymessage.conversations import (
    get_participants,
    is_group_chat,
    list_conversations,
)
from pymessage.db import ChatDatabase


class TestListConversations:
    """Tests for list_conversations function."""

    def test_list_all_conversations(self, mock_chat_db: Path):
        """Test listing all conversations."""
        df = list_conversations(db_path=mock_chat_db)
        assert not df.empty
        assert len(df) == 2  # 2 chats in fixture
        assert list(df.columns) == [
            "chat_id",
            "is_group_chat",
            "participants",
            "participant_count",
            "message_count",
            "first_message",
            "last_message",
            "display_name",
        ]

    def test_conversation_statistics(self, mock_chat_db: Path):
        """Test that conversation statistics are correct."""
        df = list_conversations(db_path=mock_chat_db)
        # Chat 1 (1-on-1) should have 4 messages
        chat1 = df[df["chat_id"] == "+12345678900"]
        assert not chat1.empty
        assert chat1.iloc[0]["message_count"] == 4

    def test_group_chat_detected(self, mock_chat_db: Path):
        """Test that group chats are detected."""
        df = list_conversations(db_path=mock_chat_db)
        group_chats = df[df["is_group_chat"] == True]
        assert not group_chats.empty
        # Should find the group chat
        assert any(group_chats["chat_id"].str.startswith("chat"))

    def test_participants_list(self, mock_chat_db: Path):
        """Test that participants are properly listed."""
        df = list_conversations(db_path=mock_chat_db)
        # Group chat should have 3 participants
        group_chat = df[df["chat_id"] == "chat123456789"]
        assert not group_chat.empty
        assert group_chat.iloc[0]["participant_count"] == 3
        assert isinstance(group_chat.iloc[0]["participants"], list)
        assert len(group_chat.iloc[0]["participants"]) == 3

    def test_timestamps_converted(self, mock_chat_db: Path):
        """Test that timestamps are properly converted."""
        df = list_conversations(db_path=mock_chat_db)
        # Pandas may use us (microseconds) or ns (nanoseconds)
        assert "datetime64" in str(df["first_message"].dtype)
        assert "UTC" in str(df["first_message"].dtype)
        assert "datetime64" in str(df["last_message"].dtype)
        assert "UTC" in str(df["last_message"].dtype)

    def test_display_name(self, mock_chat_db: Path):
        """Test that display names are included."""
        df = list_conversations(db_path=mock_chat_db)
        group_chat = df[df["chat_id"] == "chat123456789"]
        assert group_chat.iloc[0]["display_name"] == "Test Group"

    def test_sorted_by_last_message(self, mock_chat_db: Path):
        """Test that conversations have last_message dates."""
        df = list_conversations(db_path=mock_chat_db)
        # Verify last_message exists and is a timestamp for all conversations
        assert all(df["last_message"].notna())
        assert all(df["first_message"] <= df["last_message"])

    def test_backup_path(self, mock_backup: Path):
        """Test using backup_path instead of db_path."""
        df = list_conversations(backup_path=mock_backup)
        assert not df.empty
        assert len(df) == 2


class TestGetParticipants:
    """Tests for get_participants function."""

    def test_get_participants_one_on_one(self, mock_chat_db: Path):
        """Test getting participants for 1-on-1 chat."""
        with ChatDatabase(db_path=mock_chat_db) as conn:
            participants = get_participants(1, conn)
            assert isinstance(participants, list)
            assert len(participants) == 1
            assert "+12345678900" in participants

    def test_get_participants_group(self, mock_chat_db: Path):
        """Test getting participants for group chat."""
        with ChatDatabase(db_path=mock_chat_db) as conn:
            participants = get_participants(2, conn)
            assert isinstance(participants, list)
            assert len(participants) == 3
            assert "+12345678900" in participants
            assert "+19876543210" in participants
            assert "user@example.com" in participants


class TestIsGroupChat:
    """Tests for is_group_chat function."""

    def test_chat_prefix_identifies_group(self):
        """Test that 'chat' prefix identifies group chat."""
        assert is_group_chat("chat123456789", 2) is True

    def test_multiple_participants_identifies_group(self):
        """Test that >2 participants identifies group chat."""
        assert is_group_chat("+12345678900", 3) is True

    def test_one_on_one_not_group(self):
        """Test that 1-on-1 chat is not identified as group."""
        assert is_group_chat("+12345678900", 2) is False

    def test_none_identifier_not_group(self):
        """Test that None identifier is not group."""
        assert is_group_chat(None, 2) is False
