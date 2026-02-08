"""Tests for pymessage.backups module."""

import plistlib
from datetime import datetime
from pathlib import Path

import pytest

from pymessage.backups import get_backup_info, parse_info_plist


class TestGetBackupInfo:
    """Tests for get_backup_info function."""

    def test_valid_backup(self, tmp_path: Path):
        """Test extracting info from valid backup."""
        # Create mock backup with Info.plist
        backup_dir = tmp_path / "test_backup"
        backup_dir.mkdir()

        info_plist = {
            "Device Name": "Test iPhone",
            "Last Backup Date": datetime(2024, 1, 1),
            "Product Version": "17.0",
            "Phone Number": "+12345678900",
            "Serial Number": "ABC123",
        }

        with open(backup_dir / "Info.plist", "wb") as f:
            plistlib.dump(info_plist, f)

        result = get_backup_info(backup_dir)

        assert result["path"] == backup_dir.absolute()
        assert result["device_name"] == "Test iPhone"
        assert result["last_backup"] == datetime(2024, 1, 1)
        assert result["ios_version"] == "17.0"
        assert result["phone_number"] == "+12345678900"
        assert result["serial_number"] == "ABC123"

    def test_missing_backup_raises(self, tmp_path: Path):
        """Test that missing backup directory raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            get_backup_info(nonexistent)

    def test_missing_plist_raises(self, tmp_path: Path):
        """Test that missing Info.plist raises ValueError."""
        backup_dir = tmp_path / "test_backup"
        backup_dir.mkdir()
        with pytest.raises(ValueError, match="Info.plist not found"):
            get_backup_info(backup_dir)

    def test_minimal_plist(self, tmp_path: Path):
        """Test handling of minimal plist with missing fields."""
        backup_dir = tmp_path / "test_backup"
        backup_dir.mkdir()

        # Minimal plist with some fields missing
        info_plist = {
            "Device Name": "Test iPhone",
        }

        with open(backup_dir / "Info.plist", "wb") as f:
            plistlib.dump(info_plist, f)

        result = get_backup_info(backup_dir)

        assert result["device_name"] == "Test iPhone"
        assert result["ios_version"] == "Unknown"
        assert result["phone_number"] is None


class TestParseInfoPlist:
    """Tests for parse_info_plist function."""

    def test_parse_valid_plist(self, tmp_path: Path):
        """Test parsing valid Info.plist."""
        plist_path = tmp_path / "Info.plist"

        data = {
            "Device Name": "Test iPhone",
            "Product Version": "17.0",
        }

        with open(plist_path, "wb") as f:
            plistlib.dump(data, f)

        result = parse_info_plist(plist_path)

        assert result["Device Name"] == "Test iPhone"
        assert result["Product Version"] == "17.0"

    def test_malformed_plist_raises(self, tmp_path: Path):
        """Test that malformed plist raises ValueError."""
        plist_path = tmp_path / "Info.plist"

        # Write invalid plist data
        with open(plist_path, "w") as f:
            f.write("invalid plist data")

        with pytest.raises(ValueError, match="Failed to parse"):
            parse_info_plist(plist_path)
