#!/usr/bin/env python3
"""Generate example iPhone backup for pymessage testing and demos.

Run this script to regenerate the example backup from scratch:
    python src/pymessage/data/generate_example_backup.py

Creates:
    src/pymessage/data/example_backup/Info.plist
    src/pymessage/data/example_backup/Manifest.plist
    src/pymessage/data/example_backup/3d/3d0d7e5fb2ce288813306e4d4636395e047a3d28
"""

import plistlib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
BACKUP_DIR = SCRIPT_DIR / "example_backup"
DB_DIR = BACKUP_DIR / "3d"
DB_PATH = DB_DIR / "3d0d7e5fb2ce288813306e4d4636395e047a3d28"

# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def apple_ts(dt: datetime) -> int:
    """Convert datetime to Apple nanosecond timestamp."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int((dt - APPLE_EPOCH).total_seconds() * 1_000_000_000)


def dt(days_ago: int, hour: int = 12, minute: int = 0) -> datetime:
    """Create a datetime relative to the script's run date."""
    base = datetime.now(timezone.utc).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    return base - timedelta(days=days_ago)


# ---------------------------------------------------------------------------
# attributedBody blob builder
# ---------------------------------------------------------------------------
def make_attributed_body(text: str) -> bytes:
    """Build a minimal typedstream blob that parse_attributed_body() can decode.

    Format: preamble + NSString marker + 5-byte preamble + length + utf-8 text
    """
    encoded = text.encode("utf-8")
    length = len(encoded)
    blob = (
        b"\x04\x0b"
        + b"NSString"
        + b"\x00\x00\x00\x00\x00"
        + bytes([length])
        + encoded
    )
    return blob


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE message (
    rowid INTEGER PRIMARY KEY,
    guid TEXT,
    text TEXT,
    attributedBody BLOB,
    date INTEGER,
    date_read INTEGER,
    is_from_me INTEGER DEFAULT 0,
    handle_id INTEGER DEFAULT 0,
    associated_message_type INTEGER DEFAULT 0,
    associated_message_guid TEXT
);

CREATE TABLE handle (
    rowid INTEGER PRIMARY KEY,
    id TEXT,
    uncanonicalized_id TEXT
);

CREATE TABLE chat (
    rowid INTEGER PRIMARY KEY,
    chat_identifier TEXT,
    service_name TEXT DEFAULT 'iMessage',
    display_name TEXT
);

CREATE TABLE attachment (
    rowid INTEGER PRIMARY KEY,
    filename TEXT,
    mime_type TEXT,
    total_bytes INTEGER
);

CREATE TABLE chat_message_join (
    chat_id INTEGER,
    message_id INTEGER
);

CREATE TABLE chat_handle_join (
    chat_id INTEGER,
    handle_id INTEGER
);

CREATE TABLE message_attachment_join (
    message_id INTEGER,
    attachment_id INTEGER
);
"""

# ---------------------------------------------------------------------------
# Contacts  (handle rowid, phone, uncanonicalized_id)
# ---------------------------------------------------------------------------
HANDLES = [
    (1, "+18015550001", "Brother Hathaway"),
    (2, "+18015550002", "Caleb"),
    (3, "+18015550003", "Mitch"),
    (4, "+18015550004", "John"),
    (5, "+18015550005", "Phillip"),
    (6, "+18015550006", "Dallin"),
    (7, "+18015550007", "Alyssa"),
    (8, "+18015550008", "Emma"),
    (9, "+18015550009", "Ryan"),
    (10, "+18015550010", "Sarah"),
]

# Handle id by name for convenience
H = {name: rowid for rowid, _, name in HANDLES}

# Chats
# chat rowid → (chat_identifier, display_name, [handle_rowids])
CHATS = {
    1: ("chat192837465", "CS Package Dev S25", [1, 2, 3, 4, 5, 6, 7]),
    2: ("+18015550003", None, [3]),        # Mitch 1-on-1
    3: ("+18015550002", None, [2]),        # Caleb 1-on-1
    4: ("+18015550001", None, [1]),        # Brother Hathaway 1-on-1
    5: ("+18015550008", None, [8]),        # Emma 1-on-1
    6: ("+18015550009", None, [9]),        # Ryan 1-on-1
}

# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------
msg_id = 0
messages = []   # (rowid, text_or_none, attributed_body, ts, ts_read, is_from_me, handle_id, assoc_type, assoc_guid)
chat_msg_joins = []   # (chat_id, message_id)
msg_attach_joins = []  # (message_id, attachment_id)
attachments = []       # (rowid, filename, mime_type, total_bytes)
attach_id = 0


def msg(
    chat_id: int,
    text: str | None,
    ts: datetime,
    *,
    is_from_me: bool = False,
    handle_name: str | None = None,
    assoc_type: int = 0,
    assoc_guid: str | None = None,
    read_delay: int = 60,
    attributed: bool = False,
    attach_filename: str | None = None,
) -> int:
    global msg_id, attach_id
    msg_id += 1
    rid = msg_id

    handle_id = 0 if is_from_me else H[handle_name]

    # Build text / attributed body
    if attributed and text:
        body = make_attributed_body(text)
        text_val = None
    else:
        body = None
        text_val = text

    ts_read = apple_ts(ts + timedelta(seconds=read_delay)) if not is_from_me else 0

    messages.append((
        rid,
        f"guid{rid}",
        text_val,
        body,
        apple_ts(ts),
        ts_read,
        1 if is_from_me else 0,
        handle_id,
        assoc_type,
        assoc_guid,
    ))
    chat_msg_joins.append((chat_id, rid))

    if attach_filename:
        attach_id += 1
        attachments.append((attach_id, attach_filename, "image/jpeg", 2_400_000))
        msg_attach_joins.append((rid, attach_id))

    return rid


# ---------------------------------------------------------------------------
# Messages — Group chat (chat 1)
# ---------------------------------------------------------------------------

# Day 58: Intro / early class banter
msg(1, "Hey everyone, welcome to the CS Package Dev group 🎉", dt(58, 9, 5), handle_name="Brother Hathaway")
msg(1, "Thanks for setting this up!", dt(58, 9, 12), is_from_me=True)
msg(1, "Finally a group chat without memes (hopefully)", dt(58, 9, 15), handle_name="Caleb")
msg(1, "No promises 😂", dt(58, 9, 17), handle_name="Mitch")

# Day 52: Basketball game incident
bball_msg = msg(1, "Okay so I may have gotten ejected from my son's basketball game last night", dt(52, 8, 45), handle_name="Brother Hathaway")
msg(1, "…for yelling at the ref", dt(52, 8, 46), handle_name="Brother Hathaway")
msg(1, "honestly not that surprising 😅", dt(52, 8, 50), handle_name="Caleb")
# Tapback: laughed on "honestly not that surprising"
prev = msg_id
msg(1, 'Laughed at "honestly not that surprising"', dt(52, 8, 51), handle_name="Mitch", assoc_type=2003, assoc_guid=f"p:0/guid{prev-1}")
msg(1, "Haha that's rough. Hope the ref deserved it", dt(52, 8, 53), is_from_me=True)
msg(1, "THEY ABSOLUTELY DID", dt(52, 8, 55), handle_name="Brother Hathaway")

# Day 48: numpy / John mention
msg(1, "Has anyone used numpy for the project yet?", dt(48, 10, 5), handle_name="Caleb")
msg(1, "John's basically royalty in this chat when numpy comes up", dt(48, 10, 7), handle_name="Mitch")
msg(1, "lol true, John carry", dt(48, 10, 9), is_from_me=True)
msg(1, "I mean I did write the numpy docs so", dt(48, 10, 11), handle_name="John")
# Tapback: loved on John's message
john_msg = msg_id
msg(1, 'Loved "I mean I did write the numpy docs so"', dt(48, 10, 12), handle_name="Caleb", assoc_type=2000, assoc_guid=f"p:0/guid{john_msg}")

# Day 45: Dallin is late (1st time)
msg(1, "omw, be there in 5", dt(45, 13, 22), handle_name="Dallin")
# Everyone else is already there doing something else
msg(1, "we literally just finished lol", dt(45, 13, 38), handle_name="Caleb")
msg(1, "classic Dallin", dt(45, 13, 39), is_from_me=True)
# Tapback eyes on "omw be there in 5"
dallin1 = msg_id - 3
msg(1, "👀", dt(45, 13, 40), handle_name="Mitch", assoc_type=2000, assoc_guid=f"p:0/guid{dallin1}")

# Day 40: Phillip's Data Science Society invite
msg(1, "Hey everyone! Data Science Society is hosting a workshop this Friday at 5pm. Free pizza, great speakers. Hope to see you all there! 🙌", dt(40, 14, 0), handle_name="Phillip")
# crickets...
# Day 38: Phillip follows up
msg(1, "Reminder: workshop is TOMORROW. It's going to be really good, don't miss it!", dt(38, 9, 15), handle_name="Phillip")
# Still nothing...
# Day 35: someone throws a bone
msg(1, 'Liked "workshop is TOMORROW"', dt(35, 11, 30), handle_name="Dallin", assoc_type=2001, assoc_guid=f"p:0/guid{msg_id-1}")

# Day 38: Alyssa's pay rate drop
msg(1, "yeah I'm just doing some work between classes, the $65/hr helps lol", dt(38, 11, 5), handle_name="Alyssa")
alyssa_msg = msg_id
msg(1, "WAIT WHAT", dt(38, 11, 6), handle_name="Caleb")
msg(1, "65 an hour???", dt(38, 11, 7), is_from_me=True)
msg(1, "I need to rethink my Arkansas offer", dt(38, 11, 8), handle_name="Caleb")
msg(1, 'Loved "the $65/hr helps lol"', dt(38, 11, 9), handle_name="Mitch", assoc_type=2000, assoc_guid=f"p:0/guid{alyssa_msg}")
msg(1, 'Loved "the $65/hr helps lol"', dt(38, 11, 9), handle_name="John", assoc_type=2000, assoc_guid=f"p:0/guid{alyssa_msg}")
msg(1, "wait where are you even working??", dt(38, 11, 11), handle_name="Phillip")
msg(1, "just a small startup, it's chill don't worry about it 😌", dt(38, 11, 14), handle_name="Alyssa")

# Day 35: Caleb announces Arkansas job
msg(1, "Hey guys, I got the job in Arkansas!! Starting in August 🎉", dt(35, 16, 0), handle_name="Caleb")
msg(1, "LET'S GOOO Caleb!! 🎊", dt(35, 16, 2), is_from_me=True)
msg(1, "Congrats!! Do they have internet out there yet?", dt(35, 16, 3), handle_name="Mitch")
msg(1, "isn't Arkansas just one big Walmart parking lot?", dt(35, 16, 5), handle_name="John")
msg(1, "lmaoooo 😂", dt(35, 16, 6), handle_name="Phillip")
msg(1, 'Liked "congrats"', dt(35, 16, 7), handle_name="Caleb", assoc_type=2001, assoc_guid=f"p:0/guid{msg_id-5}")
msg(1, "I will choose to ignore all of you", dt(35, 16, 9), handle_name="Caleb")
msg(1, "We're proud of you Caleb, for real", dt(35, 16, 11), handle_name="Alyssa")

# Day 30: second numpy mention
msg(1, "ran into a numpy broadcasting issue, anyone know the fix?", dt(30, 10, 30), is_from_me=True)
msg(1, "John to the rescue again I assume", dt(30, 10, 31), handle_name="Mitch")
john2 = msg(1, "yeah just reshape with np.newaxis", dt(30, 10, 33), handle_name="John")
msg(1, 'Loved "just reshape with np.newaxis"', dt(30, 10, 34), is_from_me=True, assoc_type=2000, assoc_guid=f"p:0/guid{john2}")
msg(1, "See? Royalty.", dt(30, 10, 35), handle_name="Caleb")

# Day 20: Dallin late (2nd time)
msg(1, "omw, be there in 5", dt(20, 15, 10), handle_name="Dallin")
msg(1, "we're done and packing up lol", dt(20, 15, 28), handle_name="Phillip")
dallin2 = msg_id - 2
msg(1, "👀", dt(20, 15, 29), handle_name="Alyssa", assoc_type=2000, assoc_guid=f"p:0/guid{dallin2}")

# Day 10: Dallin late (3rd time)
msg(1, "omw, be there in 5", dt(10, 14, 5), handle_name="Dallin")
msg(1, "Dallin... it ended 20 min ago", dt(10, 14, 32), is_from_me=True)

# Day 5: general project chat with attachment
msg(1, "Check out this graph I made for the final report 📊", dt(5, 11, 20), is_from_me=True, attach_filename="Library/SMS/Attachments/a1/01/IMG_4821.jpg")
msg(1, "nice that looks clean", dt(5, 11, 25), handle_name="Caleb")

# Day 2: wrap up
msg(1, "Good work everyone this semester! It's been a great class 🙌", dt(2, 17, 0), handle_name="Brother Hathaway")
msg(1, "Agreed, learned a ton!", dt(2, 17, 5), is_from_me=True)
msg(1, 'Liked "Good work everyone"', dt(2, 17, 6), handle_name="Mitch", assoc_type=2001, assoc_guid=f"p:0/guid{msg_id-2}")

# ---------------------------------------------------------------------------
# Mitch 1-on-1 (chat 2) — late night coding session
# ---------------------------------------------------------------------------
mitch_late = msg(2, "dude I just pushed it, took 6 hours but it works", dt(42, 2, 17), handle_name="Mitch", read_delay=24300)  # Tucker reads at 8:45am (~6.75hr)
msg(2, "GitHub link?", dt(42, 2, 17), handle_name="Mitch")
msg(2, "just pushed it check it out - super proud of this one", dt(42, 2, 18), handle_name="Mitch", attributed=True)
# Tucker responds next morning
msg(2, "haha saw this at 8am, nice work! what's the project?", dt(42, 8, 45), is_from_me=True)
msg(2, "it's a CLI tool for parsing iMessage exports. relevant to your interests 😂", dt(42, 8, 50), handle_name="Mitch")
msg(2, "lol actually yeah. how are you handling the attributedBody stuff?", dt(42, 8, 53), is_from_me=True)
msg(2, "regex on the binary blob basically. it's a mess but it works", dt(42, 8, 55), handle_name="Mitch")

# Day 28: follow-up
msg(2, "hey did you end up using my approach for the binary parsing?", dt(28, 14, 10), handle_name="Mitch")
msg(2, "haha somewhat, I took a different route but similar idea", dt(28, 14, 20), is_from_me=True)
msg(2, "nice, let me know if you need a code review", dt(28, 14, 22), handle_name="Mitch")
msg(2, "will do 🙏", dt(28, 14, 24), is_from_me=True, attributed=True)

# ---------------------------------------------------------------------------
# Caleb 1-on-1 (chat 3) — graduation + Arkansas banter
# ---------------------------------------------------------------------------
msg(3, "Dude graduation is like 3 weeks away. feels unreal", dt(50, 18, 30), handle_name="Caleb")
msg(3, "right?? feels like we just started", dt(50, 18, 32), is_from_me=True)
msg(3, "I'm lowkey nervous about the job", dt(50, 18, 35), handle_name="Caleb")
msg(3, "You'll crush it. Arkansas will be lucky to have you", dt(50, 18, 38), is_from_me=True)
msg(3, "Tucker. Arkansas is actually really nice.", dt(50, 18, 40), handle_name="Caleb")
msg(3, "I'm sure the Walmart has great lighting", dt(50, 18, 41), is_from_me=True, attributed=True)
msg(3, "I hate you lmaooo", dt(50, 18, 42), handle_name="Caleb")

# Day 36: after announcement
msg(3, "Okay I officially accepted the offer", dt(36, 10, 5), handle_name="Caleb")
msg(3, "Let's GOOOO 🎊 seriously so hyped for you man", dt(36, 10, 7), is_from_me=True)
msg(3, "Do they have a Chick-fil-A near the office?", dt(36, 10, 9), is_from_me=True)
msg(3, "Three of them within a mile. I checked.", dt(36, 10, 11), handle_name="Caleb")
msg(3, "okay maybe Arkansas is alright", dt(36, 10, 13), is_from_me=True)

# Day 15: catching up
msg(3, "Have you started packing yet?", dt(15, 20, 0), is_from_me=True)
msg(3, "lol no. I'm in denial", dt(15, 20, 3), handle_name="Caleb")
msg(3, "same energy tbh", dt(15, 20, 5), is_from_me=True)

# ---------------------------------------------------------------------------
# Brother Hathaway 1-on-1 (chat 4) — professional/intense
# ---------------------------------------------------------------------------
msg(4, "Tucker. Status update on the module?", dt(55, 8, 1), handle_name="Brother Hathaway")
msg(4, "Almost done, finishing tests today", dt(55, 8, 5), is_from_me=True)
msg(4, "Good. I need it by FRIDAY.", dt(55, 8, 6), handle_name="Brother Hathaway")
msg(4, "Will be done by Thursday", dt(55, 8, 8), is_from_me=True)
msg(4, "Good.", dt(55, 8, 9), handle_name="Brother Hathaway")

msg(4, "The DataFrame structure looks clean. Good work.", dt(44, 16, 30), handle_name="Brother Hathaway")
msg(4, "Thanks! Took a while to get the timestamp handling right", dt(44, 16, 35), is_from_me=True)
msg(4, "The attributedBody fallback was a smart call.", dt(44, 16, 37), handle_name="Brother Hathaway")

msg(4, "Office hours tomorrow. Come if you have blockers.", dt(22, 17, 0), handle_name="Brother Hathaway")
msg(4, "I'll be there, have a question about the plist parsing", dt(22, 17, 5), is_from_me=True)
msg(4, "See you then.", dt(22, 17, 6), handle_name="Brother Hathaway")

# ---------------------------------------------------------------------------
# Emma 1-on-1 (chat 5) — casual weekend plans
# ---------------------------------------------------------------------------
msg(5, "hey what are you doing this weekend?", dt(25, 16, 45), handle_name="Emma")
msg(5, "Not much, probably working on the package. You?", dt(25, 16, 50), is_from_me=True)
msg(5, "we're doing a hike Saturday morning if you want to come", dt(25, 16, 52), handle_name="Emma")
msg(5, "Oh nice, where?", dt(25, 16, 55), is_from_me=True)
msg(5, "Timp trail, leaving at 7am", dt(25, 16, 58), handle_name="Emma")
msg(5, "I'm in! See you then 🥾", dt(25, 17, 0), is_from_me=True, attributed=True)

msg(5, "that hike was so good. thanks for inviting me", dt(23, 13, 30), is_from_me=True)
msg(5, "yes!! we should do it again sometime", dt(23, 13, 40), handle_name="Emma")
msg(5, "100%", dt(23, 13, 42), is_from_me=True)

# ---------------------------------------------------------------------------
# Ryan 1-on-1 (chat 6) — unrelated short convo
# ---------------------------------------------------------------------------
msg(6, "hey did you watch that documentary on Netflix about the deep sea?", dt(18, 21, 10), handle_name="Ryan")
msg(6, "No, is it good?", dt(18, 21, 15), is_from_me=True)
msg(6, "dude it's insane. the anglerfish part especially", dt(18, 21, 17), handle_name="Ryan")
msg(6, "okay adding it to my list", dt(18, 21, 20), is_from_me=True)
msg(6, "watched it, you were right. nightmare fuel but fascinating", dt(16, 19, 5), is_from_me=True)
msg(6, "RIGHT?! the bioluminescence part too", dt(16, 19, 10), handle_name="Ryan")


# ---------------------------------------------------------------------------
# Write everything to the database
# ---------------------------------------------------------------------------
def build():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)

    # Write Info.plist
    info_plist = {
        "Device Name": "Tucker's iPhone",
        "Last Backup Date": datetime(2024, 3, 1, 12, 0, 0),
        "Product Type": "iPhone15,2",
        "Product Version": "17.2",
        "Phone Number": "+18015550101",
        "Serial Number": "F2LWQ3XHPN",
        "IMEI": "353012345678901",
        "Build Version": "21C62",
    }
    with open(BACKUP_DIR / "Info.plist", "wb") as f:
        plistlib.dump(info_plist, f, fmt=plistlib.FMT_XML)

    # Write Manifest.plist (minimal valid)
    manifest_plist = {
        "BackupState": "new",
        "Date": datetime(2024, 3, 1, 12, 0, 0),
        "IsEncrypted": False,
        "Version": "10.0",
        "WasPasscodeSet": False,
    }
    with open(BACKUP_DIR / "Manifest.plist", "wb") as f:
        plistlib.dump(manifest_plist, f, fmt=plistlib.FMT_XML)

    # Build SQLite database
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    # Insert handles
    conn.executemany(
        "INSERT INTO handle VALUES (?, ?, ?)",
        HANDLES,
    )

    # Insert chats and chat_handle_joins
    for chat_rowid, (identifier, display_name, handle_ids) in CHATS.items():
        conn.execute(
            "INSERT INTO chat VALUES (?, ?, 'iMessage', ?)",
            (chat_rowid, identifier, display_name),
        )
        for hid in handle_ids:
            conn.execute(
                "INSERT INTO chat_handle_join VALUES (?, ?)",
                (chat_rowid, hid),
            )

    # Insert messages
    conn.executemany(
        """INSERT INTO message
           (rowid, guid, text, attributedBody, date, date_read,
            is_from_me, handle_id, associated_message_type, associated_message_guid)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        messages,
    )

    # Insert chat_message_joins
    conn.executemany(
        "INSERT INTO chat_message_join VALUES (?, ?)",
        chat_msg_joins,
    )

    # Insert attachments
    conn.executemany(
        "INSERT INTO attachment VALUES (?, ?, ?, ?)",
        attachments,
    )

    # Insert message_attachment_joins
    conn.executemany(
        "INSERT INTO message_attachment_join VALUES (?, ?)",
        msg_attach_joins,
    )

    conn.commit()
    conn.close()

    print(f"Generated example backup at: {BACKUP_DIR}")
    print(f"  Messages: {len(messages)}")
    print(f"  Attachments: {len(attachments)}")
    print(f"  Chats: {len(CHATS)}")


if __name__ == "__main__":
    build()
