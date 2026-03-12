"""Tests for pymessage.db module."""

from pathlib import Path

import pytest

from pymessage.backups import Backup
from pymessage.db import ChatDatabase, locate_chat_db, validate_db_params


class TestChatDatabase:
    """Tests for ChatDatabase context manager."""

    def test_iphone_backup(self, mock_backup: Backup):
        """Test opening database from an iPhone backup."""
        with ChatDatabase(mock_backup) as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM message")
            count = cursor.fetchone()[0]
            assert count == 6

    def test_macos_backup(self, mock_backup: Backup):
        """Test opening database as macos type (read-only)."""
        db_path = (
            mock_backup.path / "3d" / "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        )
        macos_backup = Backup(
            type="macos",
            path=db_path,
            device_name="MacBook Messages",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        with ChatDatabase(macos_backup) as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM message")
            count = cursor.fetchone()[0]
            assert count == 6

    def test_row_factory_enabled(self, mock_backup: Backup):
        """Test that row factory is enabled for dict-like access."""
        with ChatDatabase(mock_backup) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT text FROM message WHERE rowid = 1")
            row = cursor.fetchone()
            assert row["text"] == "Hello, world!"

    def test_connection_closes(self, mock_backup: Backup):
        """Test that connection is properly closed after context exit."""
        db = ChatDatabase(mock_backup)
        with db as conn:
            pass
        # Connection should be closed now
        with pytest.raises(Exception):
            conn.execute("SELECT 1")

    def test_is_macos_false_for_iphone(self, mock_backup: Backup):
        """Test that is_macos is False for iphone backup type."""
        db = ChatDatabase(mock_backup)
        assert db.is_macos is False

    def test_is_macos_true_for_macos_type(self, mock_backup: Backup):
        """Test that is_macos is True for macos backup type."""
        db_path = (
            mock_backup.path / "3d" / "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        )
        macos_backup = Backup(
            type="macos",
            path=db_path,
            device_name="MacBook Messages",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        db = ChatDatabase(macos_backup)
        assert db.is_macos is True


class TestValidateDbParams:
    """Tests for validate_db_params function."""

    def test_iphone_type_returns_chat_db_path(self, mock_backup: Backup):
        """Test that iphone type resolves to chat.db inside backup."""
        result = validate_db_params(mock_backup)
        assert result.exists()
        assert result.name == "3d0d7e5fb2ce288813306e4d4636395e047a3d28"

    def test_macos_type_returns_path_directly(self, mock_backup: Backup):
        """Test that macos type returns the path as-is."""
        db_path = (
            mock_backup.path / "3d" / "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        )
        macos_backup = Backup(
            type="macos",
            path=db_path,
            device_name="MacBook Messages",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        result = validate_db_params(macos_backup)
        assert result == db_path

    def test_invalid_type_raises(self, tmp_path: Path):
        """Test that an invalid backup type raises ValueError."""
        bad_backup = Backup(
            type="unknown",
            path=tmp_path,
            device_name="Bad",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        with pytest.raises(ValueError, match="Invalid backup type"):
            validate_db_params(bad_backup)

    def test_iphone_path_not_exists(self, tmp_path: Path):
        """Test that non-existent iphone backup path raises FileNotFoundError."""
        missing = Backup(
            type="iphone",
            path=tmp_path / "nonexistent",
            device_name="Missing",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        with pytest.raises(FileNotFoundError):
            validate_db_params(missing)

    def test_iphone_no_chat_db_raises(self, tmp_path: Path):
        """Test that backup dir without chat.db raises FileNotFoundError."""
        empty_backup = tmp_path / "empty_backup"
        empty_backup.mkdir()
        backup = Backup(
            type="iphone",
            path=empty_backup,
            device_name="Empty",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        with pytest.raises(FileNotFoundError, match="chat.db not found"):
            validate_db_params(backup)


class TestLocateChatDb:
    """Tests for locate_chat_db function."""

    def test_locate_in_backup(self, mock_backup: Backup):
        """Test locating chat.db in backup directory."""
        result = locate_chat_db(mock_backup.path)
        assert result.exists()
        assert result.name == "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        assert "3d" in str(result)

    def test_missing_chat_db(self, tmp_path: Path):
        """Test that missing chat.db raises FileNotFoundError."""
        empty_backup = tmp_path / "empty_backup"
        empty_backup.mkdir()

        with pytest.raises(FileNotFoundError, match="chat.db not found"):
            locate_chat_db(empty_backup)

    def test_returns_absolute_path(self, mock_backup: Backup):
        """Test that returned path is absolute."""
        result = locate_chat_db(mock_backup.path)
        assert result.is_absolute()
