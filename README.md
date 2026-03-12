# PyMessage

Read iMessage data from iPhone backup SQLite databases and return clean pandas DataFrames.

PyMessage makes it dead simple to go from an iPhone backup → filtered message DataFrames/CSVs. No external dependencies beyond pandas and sqlite3.

## Installation

```bash
uv pip install git+https://github.com/tuckertrostbyui/PyMessage.git
```

Or with standard pip:

```bash
pip install git+https://github.com/tuckertrostbyui/PyMessage.git
```

## Requirements

- Python >= 3.10
- macOS (for backup discovery features)
- iPhone backup created via iTunes/Finder or iCloud backup downloaded to local machine

## Quick Start

```python
from pymessage import get_messages, find_backups

# Find available backups automatically
backups = find_backups()
print(f"Found {len(backups)} backups")
print(f"Most recent: {backups[0]['device_name']}")

# Get all messages from most recent backup
df = get_messages(backup_path=backups[0]["path"])
print(f"Retrieved {len(df)} messages")
print(df.head())
```

## Basic Usage

### Get Messages

```python
from pymessage import get_messages

# Get all messages
df = get_messages(backup_path="/path/to/backup")

# Filter by phone number
df = get_messages(
    backup_path="/path/to/backup",
    phone_numbers="+1234567890"
)

# Filter by date range
df = get_messages(
    backup_path="/path/to/backup",
    date_range=("2024-01-01", "2024-12-31")
)

# Export to CSV
df = get_messages(
    backup_path="/path/to/backup",
    phone_numbers=["+1234567890", "+0987654321"],
    output_csv="messages.csv"
)
```

### List Conversations

```python
from pymessage import list_conversations

# Get all conversations with statistics
conversations = list_conversations(backup_path="/path/to/backup")

# Sort by most active
conversations = conversations.sort_values("message_count", ascending=False)
print(conversations.head())

# Filter to group chats only
group_chats = conversations[conversations["is_group_chat"] == True]
```

### Find Backups

```python
from pymessage import find_backups, get_backup_info

# Scan for all backups
backups = find_backups()
for backup in backups:
    print(f"{backup['device_name']}: {backup['ios_version']}")
    print(f"  Last backup: {backup['last_backup']}")
    print(f"  Path: {backup['path']}")

# Get info for specific backup
info = get_backup_info("/path/to/backup")
print(f"Device: {info['device_name']}")
print(f"iOS: {info['ios_version']}")
```

### Get Attachments

```python
from pymessage import get_attachments

# Get all attachments
attachments = get_attachments(backup_path="/path/to/backup")

# Filter to images only
images = attachments[attachments["mime_type"].str.startswith("image/")]
print(f"Found {len(images)} images")

# Get attachments for specific conversation
attachments = get_attachments(
    backup_path="/path/to/backup",
    phone_numbers="+1234567890"
)
```

## DataFrame Columns

### get_messages() returns:

- `timestamp`: Message timestamp in UTC
- `read_at`: When message was read (None if unread)
- `sender`: Phone number or email of sender
- `message_text`: Text content
- `is_from_me`: True if sent by device owner
- `chat_id`: Chat identifier
- `is_group_chat`: True if group conversation
- `attachment_path`: Path to attachment file (if any)
- `reaction_type`: Type of reaction ("loved", "liked", etc.)
- `reaction_action`: "add" or "remove" for reactions

### list_conversations() returns:

- `chat_id`: Chat identifier
- `is_group_chat`: True if group conversation
- `participants`: List of phone numbers/emails
- `participant_count`: Number of participants
- `message_count`: Total messages in conversation
- `first_message`: Earliest message timestamp
- `last_message`: Most recent message timestamp
- `display_name`: Chat display name (if available)

## Features

- **Clean pandas DataFrames**: Returns properly typed DataFrames ready for analysis
- **Smart phone number matching**: Handles various formats (+1, country codes, formatting)
- **Automatic timestamp conversion**: Converts Apple's nanosecond timestamps to standard datetime
- **Group chat detection**: Identifies group chats vs 1-on-1 conversations
- **Reaction/tapback parsing**: Extracts reactions (loved, liked, etc.) with add/remove actions
- **Attachment resolution**: Locates attachment files in backup SHA-1 structure
- **Flexible filtering**: Filter by phone numbers, date ranges, or both
- **CSV export**: Built-in CSV export functionality
- **No external dependencies**: Only requires pandas and standard library

## Where is my iPhone backup?

### macOS (default location):
```
~/Library/Application Support/MobileSync/Backup/
```

Each backup is in a folder with a unique identifier (like `00008030-001234567890ABCD`).

### Create a backup:
1. Connect iPhone to Mac
2. Open Finder
3. Select your iPhone in the sidebar
4. Click "Back Up Now"

## Documentation

Full API documentation available at: [https://byuirpytooling.github.io/pypackage_template](https://byuirpytooling.github.io/pypackage_template)

## Development

```bash
# Clone the repository
git clone https://github.com/yourusername/pymessage.git
cd pymessage

# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest tests/

# Run linter
ruff check src/

# Build docs
mkdocs serve
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.

## Acknowledgments

Database schema understanding based on the excellent [imessage-exporter](https://github.com/ReagentX/imessage-exporter) Rust project.
