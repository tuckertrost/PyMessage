# PyMessage

A Python package for reading iMessage data from iPhone backup SQLite databases and the macOS Messages app. Returns clean pandas DataFrames.

## Package Overview

**Source:** `src/pymessage/`
**Tests:** `tests/`
**Package manager:** pip with `pyproject.toml`
**Python:** 3.13, uses `.venv/`

## Module Structure

| File | Purpose |
|------|---------|
| `__init__.py` | Public API exports |
| `db.py` | `ChatDatabase` context manager, `validate_db_params`, `locate_chat_db` |
| `messages.py` | `get_messages()` — primary message retrieval, returns DataFrame |
| `conversations.py` | `list_conversations()` — conversation metadata and participant info |
| `attachments.py` | `get_attachments()` — attachment metadata and path resolution |
| `analytics.py` | `get_activity_summary()`, `get_contact_summary()`, `get_contact_heatmap()` |
| `backups.py` | `Backup` dataclass, `find_backups()`, `get_backup_info()` |
| `macos.py` | `resolve_macos_attachment_path()` — macOS attachment path resolution (internal) |
| `schema.py` | DB table/column constants, `convert_apple_timestamp()`, `parse_attributed_body()`, `parse_reaction_type()` |
| `utils.py` | Phone number normalization helpers |
| `data/example_backup/` | Self-contained fake iPhone backup for testing and demos |
| `data/generate_example_backup.py` | Script to regenerate the example backup from scratch |

## Public API

All exported from `pymessage`:

```python
from pymessage import (
    Backup, find_backups, get_backup_info, EXAMPLE_BACKUP,
    get_messages, list_conversations, get_attachments,
    get_activity_summary, get_contact_summary, get_contact_heatmap,
)
```

### Data Source

All functions accept a single `Backup` object as their first argument:

```python
backups = find_backups()   # returns list[Backup] — iPhone backups + macOS DB
backup = backups[0]        # most recent iPhone backup
```

The `Backup` dataclass has fields: `type` ("iphone" or "macos"), `path`, `device_name`, `last_backup`, `ios_version`, `phone_number`.

`find_backups()` scans `~/Library/Application Support/MobileSync/Backup/` for iPhone backups and appends a macOS entry if `~/Library/Messages/chat.db` is readable.

### Key Functions

```python
# Get messages, optionally filtered by phone number and date range
df = get_messages(backup, phone_numbers="+12345678900", date_range=("2024-01-01", "2024-12-31"))

# List all conversations with stats
df = list_conversations(backup)

# Get attachment metadata
df = get_attachments(backup)

# Use built-in example backup (no real device needed)
from pymessage import EXAMPLE_BACKUP
df = get_messages(EXAMPLE_BACKUP)
```

### Analytics

```python
# Overall activity stats
summary_df, top_contacts_df = get_activity_summary(df, last_n_days=30)

# Per-contact stats
contact_df = get_contact_summary(df, "+12345678900")

# 7×24 message-count heatmap
heatmap = get_contact_heatmap(df, "+12345678900")  # index=Mon–Sun, columns=0–23
```

## Key Implementation Details

- **Apple timestamps:** Two formats — nanoseconds (>= 1e12) or seconds since 2001-01-01 UTC. Handled by `convert_apple_timestamp()`.
- **attributedBody:** Modern iOS 16+/macOS Ventura+ stores message text in a binary `attributedBody` column instead of `text`. Parsed by `parse_attributed_body()`.
- **Reactions/Tapbacks:** Encoded as messages with `associated_message_type` 2000-2007 (add) or 3000-3007 (remove).
- **chat.db location in backups:** Always at `backup_root/3d/3d0d7e5fb2ce288813306e4d4636395e047a3d28` (SHA-1 hashed path).
- **Group chat detection:** `chat_identifier` starts with `"chat"` or participant count > 2.
- **macOS DB:** Opened read-only (`?mode=ro`) to avoid locking conflicts with the Messages app.
- **contact_name:** Resolved from `handle.uncanonicalized_id` at query time; "Me" for sent messages.

## DataFrame Columns

### `get_messages()` returns:
`timestamp`, `read_at`, `sender`, `contact_name`, `message_text`, `is_from_me`, `chat_id`, `is_group_chat`, `attachment_path`, `reaction_type`, `reaction_action`

### `list_conversations()` returns:
`chat_id`, `is_group_chat`, `participants`, `participant_count`, `message_count`, `first_message`, `last_message`, `display_name`

### `get_activity_summary()` returns `(summary_df, top_contacts_df)`:
- `summary_df`: `total_messages`, `total_sent`, `total_received`, `avg_messages_per_day`, `unique_contacts`, `most_active_day_of_week`, `most_active_hour`, `late_night_contacts`, `pct_messages_with_attachments`, `avg_message_length`, `avg_response_time_seconds`, `conversations_initiated`, `conversations_received`, `ghost_contacts`
- `top_contacts_df`: `contact`, `total`, `sent`, `received`

### `get_contact_summary()` returns:
`total_messages`, `total_sent`, `total_received`, `send_receive_ratio`, `avg_messages_per_active_day`, `total_active_days`, `avg_read_time_seconds`, `avg_response_time_you_seconds`, `avg_response_time_contact_seconds`, `conversations_initiated_you`, `conversations_initiated_contact`, `longest_gap_days`, `messages_with_attachments`, `avg_message_length_you`, `avg_message_length_contact`, `short_message_count_you`, `short_message_count_contact`, `most_active_hour`, `most_active_day_of_week`

### `get_contact_heatmap()` returns:
7×24 DataFrame — index: Monday–Sunday, columns: 0–23 (hours), values: message counts

## Running Tests

```bash
pytest tests/
```
