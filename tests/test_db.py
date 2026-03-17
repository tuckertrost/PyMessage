"""Tests for pymessage.db module."""

import sqlite3
from pathlib import Path

import pytest

from pymessage.backups import Backup
from pymessage.db import ChatDatabase, _locate_in_manifest, locate_chat_db, validate_db_params


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

    def test_uses_manifest_when_present(self, mock_backup: Backup):
        """locate_chat_db() uses Manifest.db when it exists."""
        result = locate_chat_db(mock_backup.path)
        # mock_backup has Manifest.db — result should be the file from manifest lookup
        assert result.name == "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        assert result.exists()

    def test_falls_back_to_hash_without_manifest(self, mock_backup: Backup):
        """locate_chat_db() falls back to hardcoded hash when no Manifest.db."""
        (mock_backup.path / "Manifest.db").unlink()
        result = locate_chat_db(mock_backup.path)
        assert result.name == "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        assert result.exists()

    def test_raises_on_encrypted_backup(self, tmp_path: Path):
        """locate_chat_db() raises ValueError for encrypted backups."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        (backup_dir / "Manifest.db").write_bytes(b"not valid sqlite data")

        with pytest.raises(ValueError, match="encrypted"):
            locate_chat_db(backup_dir)

    def test_error_mentions_unencrypted(self, tmp_path: Path):
        """FileNotFoundError message mentions 'unencrypted' when chat.db is missing."""
        empty_backup = tmp_path / "empty_backup"
        empty_backup.mkdir()

        with pytest.raises(FileNotFoundError, match="unencrypted"):
            locate_chat_db(empty_backup)


class TestLocateInManifest:
    """Tests for _locate_in_manifest helper."""

    def _make_manifest(self, backup_path: Path, file_id: str, domain: str, relative_path: str) -> None:
        """Create a minimal Manifest.db with one Files entry."""
        conn = sqlite3.connect(backup_path / "Manifest.db")
        conn.execute(
            "CREATE TABLE Files (fileID TEXT PRIMARY KEY, domain TEXT, relativePath TEXT, flags INTEGER, file BLOB)"
        )
        conn.execute(
            "INSERT INTO Files VALUES (?, ?, ?, ?, ?)",
            (file_id, domain, relative_path, 1, None),
        )
        conn.commit()
        conn.close()

    def test_returns_path_when_found(self, tmp_path: Path):
        """Returns the correct hash path when the file is in Manifest.db."""
        file_id = "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        self._make_manifest(tmp_path, file_id, "HomeDomain", "Library/SMS/sms.db")

        result = _locate_in_manifest(tmp_path, "HomeDomain", "Library/SMS/sms.db")

        assert result == tmp_path / "3d" / file_id

    def test_returns_none_when_no_manifest(self, tmp_path: Path):
        """Returns None when Manifest.db does not exist."""
        result = _locate_in_manifest(tmp_path, "HomeDomain", "Library/SMS/sms.db")
        assert result is None

    def test_returns_none_when_file_not_in_manifest(self, tmp_path: Path):
        """Returns None when Manifest.db exists but has no matching row."""
        self._make_manifest(tmp_path, "aabbcc", "HomeDomain", "Library/Other/file.db")

        result = _locate_in_manifest(tmp_path, "HomeDomain", "Library/SMS/sms.db")
        assert result is None

    def test_raises_on_encrypted_manifest(self, tmp_path: Path):
        """Raises ValueError when Manifest.db exists but cannot be read as SQLite."""
        (tmp_path / "Manifest.db").write_bytes(b"BINARYencryptedgibberish!@#$")

        with pytest.raises(ValueError, match="encrypted"):
            _locate_in_manifest(tmp_path, "HomeDomain", "Library/SMS/sms.db")
