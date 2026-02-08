"""Tests for pymessage.attachments module."""

import hashlib
from pathlib import Path

from pymessage.attachments import get_attachments, resolve_attachment_path


class TestGetAttachments:
    """Tests for get_attachments function."""

    def test_get_all_attachments(self, mock_chat_db: Path):
        """Test retrieving all attachments."""
        df = get_attachments(db_path=mock_chat_db)
        assert not df.empty
        assert len(df) == 1  # 1 attachment in fixture
        assert list(df.columns) == [
            "attachment_id",
            "message_id",
            "filename",
            "mime_type",
            "file_size",
            "backup_path",
            "timestamp",
            "sender",
        ]

    def test_attachment_metadata(self, mock_chat_db: Path):
        """Test that attachment metadata is correct."""
        df = get_attachments(db_path=mock_chat_db)
        assert df.iloc[0]["filename"] == "Library/SMS/Attachments/ab/12/IMG_1234.jpg"
        assert df.iloc[0]["mime_type"] == "image/jpeg"
        assert df.iloc[0]["file_size"] == 102400

    def test_timestamp_converted(self, mock_chat_db: Path):
        """Test that timestamp is properly converted."""
        df = get_attachments(db_path=mock_chat_db)
        # Pandas may use us (microseconds) or ns (nanoseconds)
        assert "datetime64" in str(df["timestamp"].dtype)
        assert "UTC" in str(df["timestamp"].dtype)

    def test_backup_path_none_without_backup(self, mock_chat_db: Path):
        """Test that backup_path is None when using db_path."""
        df = get_attachments(db_path=mock_chat_db)
        assert df.iloc[0]["backup_path"] is None


class TestResolveAttachmentPath:
    """Tests for resolve_attachment_path function."""

    def test_sha1_computation(self, tmp_path: Path):
        """Test that SHA-1 hash is computed correctly."""
        filename = "Library/SMS/Attachments/ab/12/IMG_1234.jpg"
        domain_path = f"MediaDomain-{filename}"
        expected_hash = hashlib.sha1(domain_path.encode()).hexdigest()

        # Create the expected file
        file_dir = tmp_path / expected_hash[:2]
        file_dir.mkdir()
        file_path = file_dir / expected_hash
        file_path.touch()

        result = resolve_attachment_path(filename, tmp_path)
        assert result == file_path
        assert result.exists()

    def test_missing_file_returns_none(self, tmp_path: Path):
        """Test that missing files return None."""
        filename = "nonexistent/file.jpg"
        result = resolve_attachment_path(filename, tmp_path)
        assert result is None

    def test_empty_filename_returns_none(self, tmp_path: Path):
        """Test that empty filename returns None."""
        result = resolve_attachment_path("", tmp_path)
        assert result is None

    def test_none_filename_returns_none(self, tmp_path: Path):
        """Test that None filename returns None."""
        result = resolve_attachment_path(None, tmp_path)
        assert result is None
