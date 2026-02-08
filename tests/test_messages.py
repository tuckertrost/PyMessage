"""Tests for pymessage.messages module."""

from pathlib import Path

import pandas as pd
import pytest

from pymessage.messages import get_messages


class TestGetMessages:
    """Tests for get_messages function."""

    def test_get_all_messages(self, mock_chat_db: Path):
        """Test retrieving all messages without filters."""
        df = get_messages(db_path=mock_chat_db)
        assert not df.empty
        assert len(df) == 5  # 5 messages in fixture
        assert list(df.columns) == [
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

    def test_timestamps_converted(self, mock_chat_db: Path):
        """Test that Apple timestamps are properly converted."""
        df = get_messages(db_path=mock_chat_db)
        assert df["timestamp"].dtype == "datetime64[ns, UTC]"
        assert all(df["timestamp"].notna())
        # First message has seconds format timestamp
        assert df.iloc[0]["timestamp"].year == 2020

    def test_read_at_timestamp(self, mock_chat_db: Path):
        """Test that read_at timestamps are properly converted."""
        df = get_messages(db_path=mock_chat_db)
        # First message has read timestamp
        assert df.iloc[0]["read_at"] is not pd.NaT
        # Second message is unread (date_read = 0)
        assert df.iloc[1]["read_at"] is pd.NaT

    def test_is_from_me_boolean(self, mock_chat_db: Path):
        """Test that is_from_me is converted to boolean."""
        df = get_messages(db_path=mock_chat_db)
        assert df["is_from_me"].dtype == bool
        # Check that we have both True and False values
        assert df["is_from_me"].any()  # At least one True
        assert not df["is_from_me"].all()  # At least one False

    def test_reactions_parsed(self, mock_chat_db: Path):
        """Test that reactions are properly parsed."""
        df = get_messages(db_path=mock_chat_db)
        # Message 4 is a reaction (loved)
        reaction_row = df[df["reaction_type"] == "loved"]
        assert not reaction_row.empty
        assert reaction_row.iloc[0]["reaction_action"] == "add"

    def test_group_chat_detection(self, mock_chat_db: Path):
        """Test that group chats are properly detected."""
        df = get_messages(db_path=mock_chat_db)
        # Message 3 is in group chat (chat_identifier starts with "chat")
        group_msg = df[df["chat_id"] == "chat123456789"]
        assert not group_msg.empty
        assert group_msg.iloc[0]["is_group_chat"] == True

    def test_filter_by_phone_number(self, mock_chat_db: Path):
        """Test filtering messages by phone number."""
        df = get_messages(db_path=mock_chat_db, phone_numbers="+12345678900")
        assert not df.empty
        # Should only return messages from/to this number
        assert all(
            row["sender"] == "+12345678900" or row["is_from_me"]
            for _, row in df.iterrows()
        )

    def test_filter_by_multiple_phones(self, mock_chat_db: Path):
        """Test filtering by multiple phone numbers."""
        df = get_messages(
            db_path=mock_chat_db,
            phone_numbers=["+12345678900", "+19876543210"],
        )
        assert not df.empty

    def test_phone_number_variants(self, mock_chat_db: Path):
        """Test that phone number variants work for matching."""
        # Try different formats of same number
        df1 = get_messages(db_path=mock_chat_db, phone_numbers="+12345678900")
        df2 = get_messages(db_path=mock_chat_db, phone_numbers="2345678900")
        df3 = get_messages(db_path=mock_chat_db, phone_numbers="12345678900")
        # All should return same results
        assert len(df1) == len(df2) == len(df3)

    def test_filter_by_date_range(self, mock_chat_db: Path):
        """Test filtering messages by date range."""
        # Messages are from 2020-2021 in fixture
        df = get_messages(
            db_path=mock_chat_db, date_range=("2020-01-01", "2020-12-31")
        )
        assert not df.empty
        assert all(df["timestamp"].dt.year == 2020)

    def test_filter_combined(self, mock_chat_db: Path):
        """Test filtering by both phone and date range."""
        df = get_messages(
            db_path=mock_chat_db,
            phone_numbers="+12345678900",
            date_range=("2020-01-01", "2021-12-31"),
        )
        assert not df.empty

    def test_csv_export(self, mock_chat_db: Path, tmp_path: Path):
        """Test CSV export functionality."""
        csv_path = tmp_path / "messages.csv"
        df = get_messages(db_path=mock_chat_db, output_csv=csv_path)
        assert csv_path.exists()
        # Read back and verify
        df_read = pd.read_csv(csv_path)
        assert len(df_read) == len(df)

    def test_backup_path(self, mock_backup: Path):
        """Test using backup_path instead of db_path."""
        df = get_messages(backup_path=mock_backup)
        assert not df.empty
        assert len(df) == 5

    def test_empty_result(self, mock_chat_db: Path):
        """Test that empty results return proper DataFrame structure."""
        df = get_messages(
            db_path=mock_chat_db,
            phone_numbers="+99999999999",  # Non-existent
        )
        assert df.empty
        assert list(df.columns) == [
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

    def test_invalid_date_range_format(self, mock_chat_db: Path):
        """Test that invalid date_range raises ValueError."""
        with pytest.raises(ValueError, match="tuple"):
            get_messages(db_path=mock_chat_db, date_range="2020-01-01")

    def test_invalid_date_range_order(self, mock_chat_db: Path):
        """Test that start > end raises ValueError."""
        with pytest.raises(ValueError, match="must be before"):
            get_messages(
                db_path=mock_chat_db, date_range=("2021-01-01", "2020-01-01")
            )

    def test_both_paths_raises(self, mock_chat_db: Path, mock_backup: Path):
        """Test that providing both paths raises ValueError."""
        with pytest.raises(ValueError, match="exactly one"):
            get_messages(db_path=mock_chat_db, backup_path=mock_backup)

    def test_neither_path_raises(self):
        """Test that providing neither path raises ValueError."""
        with pytest.raises(ValueError, match="Must provide either"):
            get_messages()
