"""PyMessage: Read iMessage data from iPhone backup databases.

A Python package for reading iMessage data from iPhone backup SQLite databases
and returning clean pandas DataFrames. Makes it simple to go from an iPhone
backup to filtered message DataFrames/CSVs.
"""

# read version from installed package
from importlib.metadata import version

from pymessage.attachments import get_attachments
from pymessage.backups import find_backups, get_backup_info
from pymessage.conversations import list_conversations
from pymessage.messages import get_messages

__version__ = version("pymessage")

__all__ = [
    "get_messages",
    "list_conversations",
    "find_backups",
    "get_backup_info",
    "get_attachments",
]