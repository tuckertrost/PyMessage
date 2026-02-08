# PyMessage Documentation

Welcome to PyMessage - a Python package for reading iMessage data from iPhone backup SQLite databases.

## Overview

PyMessage makes it simple to extract, filter, and analyze iMessage data from iPhone backups. It returns clean pandas DataFrames ready for analysis or export to CSV.

## Key Features

- **Clean pandas DataFrames** with properly typed columns
- **Smart phone number matching** handles various formats (+1, country codes, etc.)
- **Automatic timestamp conversion** from Apple's epoch to standard datetime
- **Group chat detection** identifies group vs 1-on-1 conversations
- **Reaction/tapback parsing** extracts reactions (loved, liked, etc.)
- **Attachment resolution** locates files in backup's SHA-1 structure
- **Flexible filtering** by phone numbers, date ranges, or both
- **CSV export** built-in export functionality
- **No external dependencies** only pandas and standard library

## Quick Start

```python
from pymessage import get_messages, find_backups

# Find available backups
backups = find_backups()
print(f"Found {len(backups)} backups")

# Get all messages from most recent backup
df = get_messages(backup_path=backups[0]["path"])
print(df.head())
```

## Installation

```bash
pip install pymessage
```

Or with uv:

```bash
uv pip install pymessage
```

## Requirements

- Python >= 3.10
- macOS (for backup discovery features)
- iPhone backup created via iTunes/Finder

## Documentation

- [API Reference](API.md) - Complete API documentation
- [Code Examples](code-examples.md) - Additional examples and usage patterns

## GitHub

Visit the [PyMessage GitHub repository](https://github.com/yourusername/pymessage) for source code, issues, and contributions.
