"""Tests for pymessage.db module."""

from pathlib import Path

import pytest

from pymessage.db import ChatDatabase, locate_chat_db, validate_db_params


class TestChatDatabase:
    """Tests for ChatDatabase context manager."""

    def test_direct_db_path(self, mock_chat_db: Path):
        """Test opening database with direct path."""
        with ChatDatabase(db_path=mock_chat_db) as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM message")
            count = cursor.fetchone()[0]
            assert count == 5  # 5 test messages in fixture

    def test_backup_path(self, mock_backup: Path):
        """Test opening database from backup directory."""
        with ChatDatabase(backup_path=mock_backup) as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM message")
            count = cursor.fetchone()[0]
            assert count == 5

    def test_row_factory_enabled(self, mock_chat_db: Path):
        """Test that row factory is enabled for dict-like access."""
        with ChatDatabase(db_path=mock_chat_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT text FROM message WHERE rowid = 1")
            row = cursor.fetchone()
            assert row["text"] == "Hello, world!"

    def test_connection_closes(self, mock_chat_db: Path):
        """Test that connection is properly closed after context exit."""
        db = ChatDatabase(db_path=mock_chat_db)
        with db as conn:
            pass
        # Connection should be closed now
        with pytest.raises(Exception):
            conn.execute("SELECT 1")


class TestValidateDbParams:
    """Tests for validate_db_params function."""

    def test_both_params_raises(self, tmp_path: Path):
        """Test that providing both params raises ValueError."""
        db_path = tmp_path / "chat.db"
        db_path.touch()
        backup_path = tmp_path / "backup"
        backup_path.mkdir()

        with pytest.raises(ValueError, match="exactly one"):
            validate_db_params(db_path, backup_path)

    def test_neither_param_raises(self):
        """Test that providing neither param raises ValueError."""
        with pytest.raises(ValueError, match="Must provide either"):
            validate_db_params(None, None)

    def test_db_path_not_exists(self, tmp_path: Path):
        """Test that non-existent db_path raises FileNotFoundError."""
        db_path = tmp_path / "nonexistent.db"
        with pytest.raises(FileNotFoundError, match="Database file not found"):
            validate_db_params(db_path, None)

    def test_backup_path_not_exists(self, tmp_path: Path):
        """Test that non-existent backup_path raises FileNotFoundError."""
        backup_path = tmp_path / "nonexistent_backup"
        with pytest.raises(
            FileNotFoundError, match="Backup directory not found"
        ):
            validate_db_params(None, backup_path)

    def test_valid_db_path(self, mock_chat_db: Path):
        """Test validation with valid db_path."""
        result = validate_db_params(mock_chat_db, None)
        assert result == mock_chat_db
        assert result.exists()

    def test_valid_backup_path(self, mock_backup: Path):
        """Test validation with valid backup_path."""
        result = validate_db_params(None, mock_backup)
        assert result.exists()
        assert result.name == "3d0d7e5fb2ce288813306e4d4636395e047a3d28"

    def test_string_paths(self, mock_chat_db: Path):
        """Test that string paths are converted to Path objects."""
        result = validate_db_params(str(mock_chat_db), None)
        assert isinstance(result, Path)
        assert result == mock_chat_db


class TestLocateChatDb:
    """Tests for locate_chat_db function."""

    def test_locate_in_backup(self, mock_backup: Path):
        """Test locating chat.db in backup directory."""
        result = locate_chat_db(mock_backup)
        assert result.exists()
        assert result.name == "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        assert "3d" in str(result)

    def test_missing_chat_db(self, tmp_path: Path):
        """Test that missing chat.db raises FileNotFoundError."""
        empty_backup = tmp_path / "empty_backup"
        empty_backup.mkdir()

        with pytest.raises(FileNotFoundError, match="chat.db not found"):
            locate_chat_db(empty_backup)

    def test_returns_absolute_path(self, mock_backup: Path):
        """Test that returned path is absolute."""
        result = locate_chat_db(mock_backup)
        assert result.is_absolute()
