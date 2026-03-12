"""Database schema constants and conversion utilities.

This module provides constants for iMessage database tables and columns,
as well as utility functions for converting Apple-specific data formats
to standard Python types.
"""

import pandas as pd

# Table names
TABLE_MESSAGE = "message"
TABLE_HANDLE = "handle"
TABLE_CHAT = "chat"
TABLE_ATTACHMENT = "attachment"
TABLE_CHAT_MESSAGE_JOIN = "chat_message_join"
TABLE_CHAT_HANDLE_JOIN = "chat_handle_join"
TABLE_MESSAGE_ATTACHMENT_JOIN = "message_attachment_join"

# File paths
CHAT_DB_HASH_PATH = "3d/3d0d7e5fb2ce288813306e4d4636395e047a3d28"

# Message item types
ITEM_TYPE_TEXT = 0
ITEM_TYPE_GROUP_ACTION = 1
ITEM_TYPE_ATTACHMENT = 2

# Reaction/tapback types (add actions)
REACTION_TYPES = {
    2000: "loved",
    2001: "liked",
    2002: "disliked",
    2003: "laughed",
    2004: "emphasized",
    2005: "questioned",
    2006: "loved",  # alternative encoding
    2007: "loved",  # alternative encoding
}

# Reaction remove offset (3000-3007 are remove actions)
REACTION_REMOVE_OFFSET = 1000

# Group chat identifier pattern
GROUP_CHAT_PREFIX = "chat"

# Apple epoch constants
APPLE_EPOCH = pd.Timestamp("2001-01-01", tz="UTC")
NANOSECOND_THRESHOLD = 1_000_000_000_000  # 1 trillion


def convert_apple_timestamp(timestamp: int | float | None) -> pd.Timestamp | None:
    """Convert Apple timestamp to pandas Timestamp.

    Apple uses two timestamp formats:
    - Values >= 1 trillion: nanoseconds since 2001-01-01
    - Values < 1 trillion: seconds since 2001-01-01

    Zero values are treated as None (no timestamp).

    Args:
        timestamp: Apple timestamp value, or None.

    Returns:
        pandas Timestamp object in UTC, or None if input is None/zero.

    Examples:
        >>> convert_apple_timestamp(None)

        >>> convert_apple_timestamp(0)

        >>> # Seconds format (older iOS)
        >>> ts = convert_apple_timestamp(629990400)
        >>> ts.year
        2020
        >>> # Nanoseconds format (modern iOS)
        >>> ts = convert_apple_timestamp(629990400000000000)
        >>> ts.year
        2020
    """
    if timestamp is None or timestamp == 0:
        return None

    if timestamp >= NANOSECOND_THRESHOLD:
        # Nanoseconds since 2001-01-01
        return APPLE_EPOCH + pd.Timedelta(timestamp, unit="ns")
    else:
        # Seconds since 2001-01-01
        return APPLE_EPOCH + pd.Timedelta(timestamp, unit="s")


def parse_reaction_type(
    associated_message_type: int | None,
) -> tuple[str | None, str | None]:
    """Parse reaction/tapback type from associated_message_type.

    Reactions are encoded as separate messages with specific type codes:
    - 2000-2007: Tapback added
    - 3000-3007: Tapback removed

    Args:
        associated_message_type: Type code from message.associated_message_type.

    Returns:
        Tuple of (reaction_type, action) where:
        - reaction_type: "loved", "liked", "disliked", "laughed",
          "emphasized", "questioned", or None
        - action: "add" or "remove" or None

    Examples:
        >>> parse_reaction_type(2000)
        ('loved', 'add')
        >>> parse_reaction_type(3001)
        ('liked', 'remove')
        >>> parse_reaction_type(2003)
        ('laughed', 'add')
        >>> parse_reaction_type(None)
        (None, None)
        >>> parse_reaction_type(0)
        (None, None)
    """
    if associated_message_type is None or associated_message_type == 0:
        return (None, None)

    # Check if this is a reaction removal (3000-3007)
    if 3000 <= associated_message_type <= 3007:
        reaction_code = associated_message_type - REACTION_REMOVE_OFFSET
        reaction_type = REACTION_TYPES.get(reaction_code)
        return (reaction_type, "remove")

    # Check if this is a reaction addition (2000-2007)
    if 2000 <= associated_message_type <= 2007:
        reaction_type = REACTION_TYPES.get(associated_message_type)
        return (reaction_type, "add")

    # Not a recognized reaction type
    return (None, None)


# attributedBody binary format constants
_NS_STRING_MARKER = b"NSString"
_ATTRIBUTED_BODY_PREAMBLE_LEN = 5  # bytes after NSString marker before length
_MULTI_BYTE_LENGTH_FLAG = 0x81  # indicates 2-byte little-endian length follows


def parse_attributed_body(blob: bytes | None) -> str | None:
    """Extract plain text from an iMessage attributedBody binary blob.

    Modern macOS (Ventura+) and iOS 16+ store message text in the
    attributedBody column as a serialized NSAttributedString (typedstream
    format) instead of the text column. This function extracts the plain
    text content from that binary blob.

    Args:
        blob: Raw bytes from the attributedBody column, or None.

    Returns:
        Extracted plain text string, or None if blob is None/empty/unparseable.

    Examples:
        >>> parse_attributed_body(None) is None
        True
        >>> parse_attributed_body(b"") is None
        True
    """
    if not blob:
        return None

    idx = blob.find(_NS_STRING_MARKER)
    if idx == -1:
        return None

    # Skip marker + preamble
    start = idx + len(_NS_STRING_MARKER) + _ATTRIBUTED_BODY_PREAMBLE_LEN
    if start >= len(blob):
        return None

    # Read length
    length_byte = blob[start]
    if length_byte == _MULTI_BYTE_LENGTH_FLAG:
        # 2-byte little-endian length
        if start + 3 > len(blob):
            return None
        length = int.from_bytes(blob[start + 1 : start + 3], byteorder="little")
        text_start = start + 3
    else:
        length = length_byte
        text_start = start + 1

    # Extract text
    if text_start + length > len(blob):
        return None

    return blob[text_start : text_start + length].decode("utf-8", errors="replace")
