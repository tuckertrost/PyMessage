"""Tests for pymessage.macos module."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from pymessage.macos import find_macos_db, resolve_macos_attachment_path


class TestFindMacosDb:
    """Tests for find_macos_db function."""

    def test_non_darwin_raises_os_error(self):
        """Test that non-macOS platforms raise OSError."""
        with patch("pymessage.macos.platform.system", return_value="Linux"):
            with pytest.raises(OSError, match="only available on macOS"):
                find_macos_db()

    def test_missing_db_raises_file_not_found(self, tmp_path: Path):
        """Test that missing chat.db raises FileNotFoundError."""
        fake_path = tmp_path / "nonexistent.db"
        with (
            patch("pymessage.macos.platform.system", return_value="Darwin"),
            patch("pymessage.macos.MACOS_CHAT_DB_PATH", fake_path),
        ):
            with pytest.raises(FileNotFoundError, match="not found"):
                find_macos_db()

    def test_permission_error_with_helpful_message(self, tmp_path: Path):
        """Test that unreadable database raises PermissionError with guidance."""
        fake_db = tmp_path / "chat.db"
        fake_db.touch()
        with (
            patch("pymessage.macos.platform.system", return_value="Darwin"),
            patch("pymessage.macos.MACOS_CHAT_DB_PATH", fake_db),
            patch(
                "pymessage.macos.sqlite3.connect",
                side_effect=sqlite3.OperationalError("unable to open database"),
            ),
        ):
            with pytest.raises(PermissionError, match="Full Disk Access"):
                find_macos_db()

    def test_valid_db_returns_path(self, mock_chat_db: Path):
        """Test that a valid, readable database returns its path."""
        with (
            patch("pymessage.macos.platform.system", return_value="Darwin"),
            patch("pymessage.macos.MACOS_CHAT_DB_PATH", mock_chat_db),
        ):
            result = find_macos_db()
            assert result == mock_chat_db


class TestResolveMacosAttachmentPath:
    """Tests for resolve_macos_attachment_path function."""

    def test_existing_file_returns_path(self, tmp_path: Path):
        """Test that existing files return their expanded path."""
        test_file = tmp_path / "test_attachment.jpg"
        test_file.touch()
        result = resolve_macos_attachment_path(str(test_file))
        assert result == test_file

    def test_missing_file_returns_none(self):
        """Test that missing files return None."""
        result = resolve_macos_attachment_path("/nonexistent/path/file.jpg")
        assert result is None

    def test_empty_filename_returns_none(self):
        """Test that empty string returns None."""
        result = resolve_macos_attachment_path("")
        assert result is None

    def test_none_filename_returns_none(self):
        """Test that None returns None."""
        result = resolve_macos_attachment_path(None)
        assert result is None

    def test_tilde_expansion(self, tmp_path: Path, monkeypatch):
        """Test that ~ paths are expanded."""
        test_file = tmp_path / "Library" / "Messages" / "Attachments" / "img.jpg"
        test_file.parent.mkdir(parents=True)
        test_file.touch()

        monkeypatch.setenv("HOME", str(tmp_path))
        result = resolve_macos_attachment_path(
            "~/Library/Messages/Attachments/img.jpg"
        )
        assert result is not None
        assert result.exists()
