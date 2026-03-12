"""Contact name resolution from macOS AddressBook and iPhone backup contacts."""

import sqlite3
from pathlib import Path

from pymessage.utils import normalize_phone_number

# macOS AddressBook location
_MACOS_AB_SOURCES = Path.home() / "Library" / "Application Support" / "AddressBook" / "Sources"
_MACOS_AB_ROOT = Path.home() / "Library" / "Application Support" / "AddressBook" / "AddressBook-v22.abcddb"

# iPhone backup AddressBook SHA-1 path
# SHA-1 of "HomeDomain-Library/AddressBook/AddressBook.sqlitedb"
_IPHONE_AB_HASH = "31bb7ba8914766d4ba40d6dfb6113c8b614be442"
_IPHONE_AB_PATH = Path(_IPHONE_AB_HASH[:2]) / _IPHONE_AB_HASH


def build_contacts_lookup(backup) -> dict[str, str]:
    """Build a phone-number-to-display-name mapping from the appropriate contacts source.

    For macOS backups, reads from ~/Library/Application Support/AddressBook.
    For iPhone backups, reads from the backup's AddressBook.sqlitedb.

    Args:
        backup: A Backup object.

    Returns:
        Dict mapping normalized phone number strings to display names.
        Multiple normalized variants of each number are inserted so lookups
        work regardless of how the handle is stored in chat.db.
    """
    if backup.type == "macos":
        return _load_macos_contacts()
    if backup.type == "iphone":
        return _load_iphone_contacts(Path(backup.path))
    return {}


def _display_name(first, last, nickname) -> str | None:
    """Return the best display name from contact fields."""
    if nickname:
        return nickname.strip()
    parts = [p.strip() for p in (first or "", last or "") if p and p.strip()]
    return " ".join(parts) if parts else None


def _insert_variants(lookup: dict, raw_number: str, name: str) -> None:
    """Normalize a raw phone number and insert all variants into lookup."""
    if not raw_number or "@" in raw_number:
        # Skip emails — chat.db already stores them as-is
        return
    normalized = normalize_phone_number(raw_number)
    if not normalized:
        return

    # Generate variants: with/without +1 for US numbers
    variants = {normalized}
    if normalized.startswith("+1") and len(normalized) == 12:
        variants.add(normalized[1:])   # 12345678900
        variants.add(normalized[2:])   # 2345678900
    elif normalized.startswith("1") and len(normalized) == 11:
        variants.add("+" + normalized)
        variants.add(normalized[1:])
    elif len(normalized) == 10:
        variants.add("+1" + normalized)
        variants.add("1" + normalized)

    for v in variants:
        lookup.setdefault(v, name)  # first found wins


def _load_macos_contacts() -> dict[str, str]:
    """Load contacts from all macOS AddressBook source databases."""
    lookup: dict[str, str] = {}

    dbs = list(_MACOS_AB_SOURCES.glob("*/AddressBook-v22.abcddb"))
    dbs.append(_MACOS_AB_ROOT)

    for db_path in dbs:
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT r.ZFIRSTNAME, r.ZLASTNAME, r.ZNICKNAME, p.ZFULLNUMBER
                FROM ZABCDRECORD r
                JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
            """)
            for row in cur.fetchall():
                name = _display_name(row["ZFIRSTNAME"], row["ZLASTNAME"], row["ZNICKNAME"])
                if name and row["ZFULLNUMBER"]:
                    _insert_variants(lookup, row["ZFULLNUMBER"], name)
            conn.close()
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            continue

    return lookup


def _load_iphone_contacts(backup_root: Path) -> dict[str, str]:
    """Load contacts from an iPhone backup's AddressBook.sqlitedb."""
    lookup: dict[str, str] = {}
    ab_path = backup_root / _IPHONE_AB_PATH

    if not ab_path.exists():
        return lookup

    try:
        conn = sqlite3.connect(f"file:{ab_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # property=3 is phone number in iPhone AddressBook
        cur.execute("""
            SELECT p.First, p.Last, p.Nickname, mv.value AS phone
            FROM ABPerson p
            JOIN ABMultiValue mv ON mv.record_id = p.ROWID
            WHERE mv.property = 3
        """)
        for row in cur.fetchall():
            name = _display_name(row["First"], row["Last"], row["Nickname"])
            if name and row["phone"]:
                _insert_variants(lookup, row["phone"], name)
        conn.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        pass

    return lookup
