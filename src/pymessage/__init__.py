"""PyMessage: Read iMessage data from iPhone backup databases.

A Python package for reading iMessage data from iPhone backup SQLite databases
and returning clean pandas DataFrames. Makes it simple to go from an iPhone
backup to filtered message DataFrames/CSVs.
"""

import datetime
from importlib.metadata import version
from pathlib import Path

from pymessage.analytics import get_activity_summary, get_contact_heatmap, get_contact_summary
from pymessage.attachments import get_attachments
from pymessage.backups import Backup, find_backups, get_backup_info
from pymessage.conversations import list_conversations
from pymessage.messages import get_messages

__version__ = version("pymessage")

EXAMPLE_BACKUP = Backup(
    type="iphone",
    path=Path(__file__).parent / "data" / "example_backup",
    device_name="Tucker's iPhone",
    last_backup=datetime.datetime(2024, 3, 1),
    ios_version="17.2",
    phone_number="+18015550101",
)

__all__ = [
    "get_messages",
    "list_conversations",
    "find_backups",
    "get_backup_info",
    "get_attachments",
    "Backup",
    "EXAMPLE_BACKUP",
    "get_activity_summary",
    "get_contact_summary",
    "get_contact_heatmap",
]
