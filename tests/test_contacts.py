"""Tests for pymessage.contacts module."""

import sqlite3
from pathlib import Path

import pytest

from pymessage.backups import Backup
from pymessage.contacts import (
    _display_name,
    _insert_variants,
    _load_iphone_contacts,
    build_contacts_lookup,
)

# SHA-1 of "HomeDomain-Library/AddressBook/AddressBook.sqlitedb"
_IPHONE_AB_HASH = "31bb7ba8914766d4ba40d6dfb6113c8b614be442"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_iphone_addressbook(tmp_path: Path) -> Path:
    """Create a minimal iPhone AddressBook SQLite at the expected SHA-1 path.

    Returns the backup root directory (tmp_path).
    """
    ab_dir = tmp_path / _IPHONE_AB_HASH[:2]
    ab_dir.mkdir(parents=True, exist_ok=True)
    ab_path = ab_dir / _IPHONE_AB_HASH

    conn = sqlite3.connect(ab_path)
    conn.executescript("""
        CREATE TABLE ABPerson (
            ROWID INTEGER PRIMARY KEY,
            First TEXT,
            Last TEXT,
            Nickname TEXT
        );
        CREATE TABLE ABMultiValue (
            record_id INTEGER,
            property INTEGER,
            value TEXT
        );
    """)
    conn.execute("INSERT INTO ABPerson VALUES (1, 'Alice', 'Smith', NULL)")
    conn.execute("INSERT INTO ABPerson VALUES (2, 'Bob', NULL, 'Bobby')")
    conn.execute("INSERT INTO ABMultiValue VALUES (1, 3, '+12345678900')")
    conn.execute("INSERT INTO ABMultiValue VALUES (2, 3, '+19876543210')")
    conn.commit()
    conn.close()

    return tmp_path


# ---------------------------------------------------------------------------
# TestDisplayName
# ---------------------------------------------------------------------------

class TestDisplayName:
    def test_nickname_takes_priority(self):
        assert _display_name("John", "Doe", "JD") == "JD"

    def test_first_last_joined(self):
        assert _display_name("John", "Doe", None) == "John Doe"

    def test_nickname_only(self):
        assert _display_name(None, None, "JD") == "JD"

    def test_first_only(self):
        assert _display_name("John", None, None) == "John"

    def test_last_only(self):
        assert _display_name(None, "Doe", None) == "Doe"

    def test_all_none_returns_none(self):
        assert _display_name(None, None, None) is None

    def test_whitespace_stripped(self):
        assert _display_name("  John  ", "  Doe  ", None) == "John Doe"

    def test_empty_strings_treated_as_none(self):
        assert _display_name("", "", None) is None

    def test_nickname_whitespace_stripped(self):
        assert _display_name("John", "Doe", "  JD  ") == "JD"


# ---------------------------------------------------------------------------
# TestInsertVariants
# ---------------------------------------------------------------------------

class TestInsertVariants:
    def test_inserts_all_us_phone_variants_plus_format(self):
        lookup: dict = {}
        _insert_variants(lookup, "+12345678900", "Alice")
        assert "+12345678900" in lookup
        assert "12345678900" in lookup
        assert "2345678900" in lookup
        assert all(v == "Alice" for v in lookup.values())

    def test_inserts_all_us_phone_variants_10_digit(self):
        lookup: dict = {}
        _insert_variants(lookup, "2345678900", "Alice")
        assert "2345678900" in lookup
        assert "+12345678900" in lookup
        assert "12345678900" in lookup

    def test_inserts_all_us_phone_variants_11_digit(self):
        lookup: dict = {}
        _insert_variants(lookup, "12345678900", "Alice")
        assert "12345678900" in lookup
        assert "+12345678900" in lookup
        assert "2345678900" in lookup

    def test_email_skipped(self):
        lookup: dict = {}
        _insert_variants(lookup, "alice@example.com", "Alice")
        assert lookup == {}

    def test_first_found_wins(self):
        lookup: dict = {}
        _insert_variants(lookup, "+12345678900", "Alice")
        _insert_variants(lookup, "2345678900", "Bob")  # same number, different name
        # Alice was inserted first — all variants remain Alice
        assert lookup["+12345678900"] == "Alice"
        assert lookup["2345678900"] == "Alice"
        assert lookup["12345678900"] == "Alice"

    def test_empty_number_skipped(self):
        lookup: dict = {}
        _insert_variants(lookup, "", "Alice")
        assert lookup == {}

    def test_international_number_inserted_as_is(self):
        # Non-US number: no +1 variants generated, but the normalized form is stored
        lookup: dict = {}
        _insert_variants(lookup, "+441234567890", "Alice")
        assert len(lookup) >= 1
        assert "Alice" in lookup.values()


# ---------------------------------------------------------------------------
# TestLoadIphoneContacts
# ---------------------------------------------------------------------------

class TestLoadIphoneContacts:
    def test_reads_first_last_name(self, tmp_path: Path):
        backup_root = _make_iphone_addressbook(tmp_path)
        lookup = _load_iphone_contacts(backup_root)
        assert lookup.get("+12345678900") == "Alice Smith"

    def test_nickname_used_when_present(self, tmp_path: Path):
        backup_root = _make_iphone_addressbook(tmp_path)
        lookup = _load_iphone_contacts(backup_root)
        assert lookup.get("+19876543210") == "Bobby"

    def test_all_us_variants_inserted(self, tmp_path: Path):
        backup_root = _make_iphone_addressbook(tmp_path)
        lookup = _load_iphone_contacts(backup_root)
        assert lookup.get("+12345678900") == "Alice Smith"
        assert lookup.get("12345678900") == "Alice Smith"
        assert lookup.get("2345678900") == "Alice Smith"

    def test_missing_db_returns_empty(self, tmp_path: Path):
        lookup = _load_iphone_contacts(tmp_path)
        assert lookup == {}

    def test_corrupt_db_returns_empty(self, tmp_path: Path):
        ab_dir = tmp_path / _IPHONE_AB_HASH[:2]
        ab_dir.mkdir()
        ab_path = ab_dir / _IPHONE_AB_HASH
        ab_path.write_bytes(b"not a valid sqlite database")
        lookup = _load_iphone_contacts(tmp_path)
        assert lookup == {}

    def test_contact_without_phone_not_included(self, tmp_path: Path):
        """A person with no phone rows in ABMultiValue should not appear in lookup."""
        ab_dir = tmp_path / _IPHONE_AB_HASH[:2]
        ab_dir.mkdir(parents=True, exist_ok=True)
        ab_path = ab_dir / _IPHONE_AB_HASH

        conn = sqlite3.connect(ab_path)
        conn.executescript("""
            CREATE TABLE ABPerson (
                ROWID INTEGER PRIMARY KEY,
                First TEXT,
                Last TEXT,
                Nickname TEXT
            );
            CREATE TABLE ABMultiValue (
                record_id INTEGER,
                property INTEGER,
                value TEXT
            );
        """)
        conn.execute("INSERT INTO ABPerson VALUES (1, 'Ghost', 'Person', NULL)")
        # No phone rows for this person
        conn.commit()
        conn.close()

        lookup = _load_iphone_contacts(tmp_path)
        assert lookup == {}

    def test_only_property_3_included(self, tmp_path: Path):
        """Only rows with property=3 (phone) should be used — not emails (property=4)."""
        ab_dir = tmp_path / _IPHONE_AB_HASH[:2]
        ab_dir.mkdir(parents=True, exist_ok=True)
        ab_path = ab_dir / _IPHONE_AB_HASH

        conn = sqlite3.connect(ab_path)
        conn.executescript("""
            CREATE TABLE ABPerson (
                ROWID INTEGER PRIMARY KEY,
                First TEXT,
                Last TEXT,
                Nickname TEXT
            );
            CREATE TABLE ABMultiValue (
                record_id INTEGER,
                property INTEGER,
                value TEXT
            );
        """)
        conn.execute("INSERT INTO ABPerson VALUES (1, 'Alice', 'Smith', NULL)")
        conn.execute("INSERT INTO ABMultiValue VALUES (1, 4, 'alice@example.com')")  # email, not phone
        conn.commit()
        conn.close()

        lookup = _load_iphone_contacts(tmp_path)
        assert lookup == {}


# ---------------------------------------------------------------------------
# TestBuildContactsLookup
# ---------------------------------------------------------------------------

class TestBuildContactsLookup:
    def test_iphone_backup_with_addressbook(self, tmp_path: Path):
        backup_root = _make_iphone_addressbook(tmp_path)
        backup = Backup(
            type="iphone",
            path=backup_root,
            device_name="Test iPhone",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        lookup = build_contacts_lookup(backup)
        assert isinstance(lookup, dict)
        assert "+12345678900" in lookup
        assert lookup["+12345678900"] == "Alice Smith"

    def test_iphone_backup_missing_addressbook_returns_empty(self, mock_backup: Backup):
        # mock_backup directory has no AddressBook — should return {}
        lookup = build_contacts_lookup(mock_backup)
        assert isinstance(lookup, dict)
        assert lookup == {}

    def test_lookup_keys_are_normalized_phones(self, tmp_path: Path):
        backup_root = _make_iphone_addressbook(tmp_path)
        backup = Backup(
            type="iphone",
            path=backup_root,
            device_name="Test iPhone",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        lookup = build_contacts_lookup(backup)
        # Keys should not contain formatting characters like spaces or dashes
        for key in lookup:
            assert " " not in key
            assert "-" not in key
            assert "(" not in key

    def test_unknown_backup_type_returns_empty(self):
        backup = Backup(
            type="unknown",
            path=Path("/tmp"),
            device_name="Test",
            last_backup=None,
            ios_version=None,
            phone_number=None,
        )
        lookup = build_contacts_lookup(backup)
        assert lookup == {}


class TestLoadIphoneContactsManifest:
    """Tests for _load_iphone_contacts() Manifest.db integration."""

    def _make_addressbook_db(self, path: Path) -> None:
        """Write a minimal AddressBook SQLite database to the given path."""
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE ABPerson (
                ROWID INTEGER PRIMARY KEY, First TEXT, Last TEXT, Nickname TEXT
            );
            CREATE TABLE ABMultiValue (
                record_id INTEGER, property INTEGER, value TEXT
            );
        """)
        conn.execute("INSERT INTO ABPerson VALUES (1, 'Alice', 'Smith', NULL)")
        conn.execute("INSERT INTO ABMultiValue VALUES (1, 3, '+12345678900')")
        conn.commit()
        conn.close()

    def test_uses_manifest_when_present(self, tmp_path: Path):
        """_load_iphone_contacts() finds AddressBook via Manifest.db lookup."""
        ab_hash = "31bb7ba8914766d4ba40d6dfb6113c8b614be442"
        ab_dir = tmp_path / ab_hash[:2]
        ab_dir.mkdir()
        self._make_addressbook_db(ab_dir / ab_hash)

        # Create Manifest.db pointing to the AddressBook
        manifest_conn = sqlite3.connect(tmp_path / "Manifest.db")
        manifest_conn.execute(
            "CREATE TABLE Files (fileID TEXT PRIMARY KEY, domain TEXT, relativePath TEXT, flags INTEGER, file BLOB)"
        )
        manifest_conn.execute(
            "INSERT INTO Files VALUES (?, ?, ?, ?, ?)",
            (ab_hash, "HomeDomain", "Library/AddressBook/AddressBook.sqlitedb", 1, None),
        )
        manifest_conn.commit()
        manifest_conn.close()

        lookup = _load_iphone_contacts(tmp_path)
        assert lookup.get("+12345678900") == "Alice Smith"

    def test_encrypted_backup_returns_empty(self, tmp_path: Path):
        """_load_iphone_contacts() returns {} without raising for encrypted backups."""
        (tmp_path / "Manifest.db").write_bytes(b"BINARYencryptedgibberish!@#$")

        lookup = _load_iphone_contacts(tmp_path)
        assert lookup == {}
