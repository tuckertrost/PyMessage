"""Tests for pymessage.backups module."""

import plistlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from pymessage.backups import Backup, find_backups, get_backup_info, parse_info_plist


def _make_backup_dir(parent: Path, name: str = "device1", date: datetime | None = None) -> Path:
    """Create a minimal iPhone backup directory with Info.plist."""
    backup_dir = parent / name
    backup_dir.mkdir(parents=True, exist_ok=True)
    info_plist = {
        "Device Name": "Test iPhone",
        "Last Backup Date": date or datetime(2024, 1, 1),
        "Product Version": "17.0",
        "Phone Number": "+12345678900",
        "Serial Number": "ABC123",
    }
    with open(backup_dir / "Info.plist", "wb") as f:
        plistlib.dump(info_plist, f)
    return backup_dir


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


class TestFindBackups:
    """Tests for find_backups() — platform-specific backup discovery."""

    # ── macOS ──────────────────────────────────────────────────────────────

    def test_macos_finds_iphone_backup(self, tmp_path: Path):
        """find_backups() returns iPhone backup found at the macOS path."""
        home = tmp_path / "home"
        backup_root = home / "Library" / "Application Support" / "MobileSync" / "Backup"
        _make_backup_dir(backup_root)

        with (
            patch("pymessage.backups.platform.system", return_value="Darwin"),
            patch("pymessage.backups.Path.home", return_value=home),
        ):
            result = find_backups()

        assert len(result) == 1
        assert result[0].type == "iphone"
        assert result[0].device_name == "Test iPhone"

    def test_macos_no_backups_returns_empty(self, tmp_path: Path):
        """find_backups() returns [] when backup root does not exist on macOS."""
        home = tmp_path / "home"
        home.mkdir()

        with (
            patch("pymessage.backups.platform.system", return_value="Darwin"),
            patch("pymessage.backups.Path.home", return_value=home),
        ):
            result = find_backups()

        assert result == []

    def test_macos_skips_dirs_without_plist(self, tmp_path: Path):
        """find_backups() silently skips backup dirs missing Info.plist."""
        home = tmp_path / "home"
        backup_root = home / "Library" / "Application Support" / "MobileSync" / "Backup"
        # Create a dir with no Info.plist
        (backup_root / "no_plist_dir").mkdir(parents=True)

        with (
            patch("pymessage.backups.platform.system", return_value="Darwin"),
            patch("pymessage.backups.Path.home", return_value=home),
        ):
            result = find_backups()

        assert result == []

    def test_macos_skips_non_directory_entries(self, tmp_path: Path):
        """find_backups() skips files in the backup root, returns only dirs."""
        home = tmp_path / "home"
        backup_root = home / "Library" / "Application Support" / "MobileSync" / "Backup"
        _make_backup_dir(backup_root, name="valid_device")
        # Place a stray file alongside the valid backup dir
        (backup_root / "stray_file.txt").write_text("noise")

        with (
            patch("pymessage.backups.platform.system", return_value="Darwin"),
            patch("pymessage.backups.Path.home", return_value=home),
        ):
            result = find_backups()

        assert len(result) == 1
        assert result[0].type == "iphone"

    # ── Windows — new iTunes path ──────────────────────────────────────────

    def test_windows_new_itunes_finds_backup(self, tmp_path: Path, monkeypatch):
        """find_backups() finds backup at %APPDATA%\\Apple\\MobileSync\\Backup."""
        appdata = tmp_path / "AppData"
        backup_root = appdata / "Apple" / "MobileSync" / "Backup"
        _make_backup_dir(backup_root)

        monkeypatch.setenv("APPDATA", str(appdata))
        with patch("pymessage.backups.platform.system", return_value="Windows"):
            result = find_backups()

        assert len(result) == 1
        assert result[0].type == "iphone"

    def test_windows_new_itunes_preferred_over_old(self, tmp_path: Path, monkeypatch):
        """When both iTunes paths exist, only the new path is scanned."""
        appdata = tmp_path / "AppData"
        new_root = appdata / "Apple" / "MobileSync" / "Backup"
        old_root = appdata / "Apple Computer" / "MobileSync" / "Backup"
        _make_backup_dir(new_root, name="new_device")
        _make_backup_dir(old_root, name="old_device")

        monkeypatch.setenv("APPDATA", str(appdata))
        with patch("pymessage.backups.platform.system", return_value="Windows"):
            result = find_backups()

        assert len(result) == 1
        assert result[0].device_name == "Test iPhone"
        # Confirm it came from the new path
        assert str(new_root) in str(result[0].path)

    # ── Windows — old iTunes fallback ─────────────────────────────────────

    def test_windows_old_itunes_used_when_new_missing(self, tmp_path: Path, monkeypatch):
        """find_backups() falls back to Apple Computer path when Apple/ missing."""
        appdata = tmp_path / "AppData"
        old_root = appdata / "Apple Computer" / "MobileSync" / "Backup"
        _make_backup_dir(old_root)

        monkeypatch.setenv("APPDATA", str(appdata))
        with patch("pymessage.backups.platform.system", return_value="Windows"):
            result = find_backups()

        assert len(result) == 1
        assert result[0].type == "iphone"

    # ── Windows — APPDATA env var handling ────────────────────────────────

    def test_windows_appdata_fallback_when_env_not_set(self, tmp_path: Path, monkeypatch):
        """find_backups() uses Path.home()/AppData/Roaming when APPDATA unset."""
        home = tmp_path / "home"
        backup_root = home / "AppData" / "Roaming" / "Apple" / "MobileSync" / "Backup"
        _make_backup_dir(backup_root)

        monkeypatch.delenv("APPDATA", raising=False)
        with (
            patch("pymessage.backups.platform.system", return_value="Windows"),
            patch("pymessage.backups.Path.home", return_value=home),
        ):
            result = find_backups()

        assert len(result) == 1
        assert result[0].type == "iphone"

    def test_windows_no_backup_dirs_returns_empty(self, tmp_path: Path, monkeypatch):
        """find_backups() returns [] when no backup dirs exist on Windows."""
        appdata = tmp_path / "AppData"
        appdata.mkdir()

        monkeypatch.setenv("APPDATA", str(appdata))
        with patch("pymessage.backups.platform.system", return_value="Windows"):
            result = find_backups()

        assert result == []

    # ── Linux / other ─────────────────────────────────────────────────────

    def test_linux_returns_empty(self):
        """find_backups() returns [] on Linux (no standard backup location)."""
        with patch("pymessage.backups.platform.system", return_value="Linux"):
            result = find_backups()

        assert result == []

    # ── macOS Messages DB guard ───────────────────────────────────────────

    def test_windows_skips_macos_messages_db(self, tmp_path: Path, monkeypatch):
        """find_backups() does not include a macOS Messages entry on Windows."""
        appdata = tmp_path / "AppData"
        appdata.mkdir()
        # Even if a chat.db-like path existed, it should not be picked up
        monkeypatch.setenv("APPDATA", str(appdata))
        with patch("pymessage.backups.platform.system", return_value="Windows"):
            result = find_backups()

        assert not any(b.type == "macos" for b in result)

    def test_macos_messages_db_included_when_readable(self, tmp_path: Path, mock_chat_db: Path):
        """find_backups() appends a macOS Backup when chat.db is readable."""
        home = tmp_path / "home"
        messages_dir = home / "Library" / "Messages"
        messages_dir.mkdir(parents=True)
        shutil.copy(mock_chat_db, messages_dir / "chat.db")

        # No iPhone backups — backup root won't exist
        with (
            patch("pymessage.backups.platform.system", return_value="Darwin"),
            patch("pymessage.backups.Path.home", return_value=home),
        ):
            result = find_backups()

        assert len(result) == 1
        assert result[0].type == "macos"

    def test_macos_messages_db_warns_on_error(self, tmp_path: Path):
        """find_backups() warns and skips macOS DB when it can't be opened."""
        home = tmp_path / "home"
        messages_dir = home / "Library" / "Messages"
        messages_dir.mkdir(parents=True)
        (messages_dir / "chat.db").touch()

        with (
            patch("pymessage.backups.platform.system", return_value="Darwin"),
            patch("pymessage.backups.Path.home", return_value=home),
            patch(
                "pymessage.backups.sqlite3.connect",
                side_effect=sqlite3.OperationalError("unable to open"),
            ),
            pytest.warns(UserWarning),
        ):
            result = find_backups()

        assert not any(b.type == "macos" for b in result)

    # ── Sort order ────────────────────────────────────────────────────────

    def test_backups_sorted_most_recent_first(self, tmp_path: Path):
        """find_backups() returns iPhone backups ordered newest first."""
        home = tmp_path / "home"
        backup_root = home / "Library" / "Application Support" / "MobileSync" / "Backup"
        _make_backup_dir(backup_root, name="old_device", date=datetime(2023, 1, 1))
        _make_backup_dir(backup_root, name="new_device", date=datetime(2024, 6, 1))

        with (
            patch("pymessage.backups.platform.system", return_value="Darwin"),
            patch("pymessage.backups.Path.home", return_value=home),
        ):
            result = find_backups()

        assert len(result) == 2
        assert result[0].last_backup > result[1].last_backup
