# Code Examples

Practical examples for common PyMessage use cases.

## Getting Started

### Find and Inspect Backups

```python
from pymessage import find_backups

backups = find_backups()

for backup in backups:
    print(f"Device: {backup.device_name}")
    print(f"iOS Version: {backup.ios_version}")
    print(f"Last Backup: {backup.last_backup}")
    print(f"Path: {backup.path}")
    print()
```

!!! tip "No backups found?"
    If `find_backups()` returns an empty list, you may not have an iPhone backup
    on this Mac yet. See the [iPhone Backup Guide](iphone-backup.md) to create one.

### Load All Messages

```python
from pymessage import find_backups, get_messages

backups = find_backups()
df = get_messages(backups[0])

print(f"Total messages: {len(df)}")
print(df.head())
```

---

## Filtering Messages

### Filter by Phone Number

```python
from pymessage import find_backups, get_messages

backups = find_backups()

# Single contact — accepts any common format
df = get_messages(backups[0], phone_numbers="+12085550100")

# Multiple contacts at once
df = get_messages(
    backups[0],
    phone_numbers=["+12085550100", "+12085550200"]
)

print(f"Messages with these contacts: {len(df)}")
```

### Filter by Date Range

```python
from pymessage import find_backups, get_messages

backups = find_backups()

# All messages in a calendar year
df = get_messages(
    backups[0],
    date_range=("2024-01-01", "2024-12-31")
)

print(f"Messages in 2024: {len(df)}")
```

### Combine Filters and Export to CSV

```python
from pymessage import find_backups, get_messages

backups = find_backups()

df = get_messages(
    backups[0],
    phone_numbers="+12085550100",
    date_range=("2024-06-01", "2024-12-31"),
    output_csv="messages_export.csv"
)

print(f"Exported {len(df)} messages to messages_export.csv")
```

---

## Working with Conversations

### List All Conversations

```python
from pymessage import find_backups, list_conversations

backups = find_backups()
convos = list_conversations(backups[0])

print(convos[["chat_id", "display_name", "message_count", "last_message"]])
```

### Find Your Most Active Conversations

```python
from pymessage import find_backups, list_conversations

backups = find_backups()
convos = list_conversations(backups[0])

top = convos.sort_values("message_count", ascending=False).head(10)
print(top[["display_name", "message_count", "last_message"]])
```

### Filter to Group Chats Only

```python
from pymessage import find_backups, list_conversations

backups = find_backups()
convos = list_conversations(backups[0])

group_chats = convos[convos["is_group_chat"] == True]
print(f"You are in {len(group_chats)} group chats")
print(group_chats[["display_name", "participant_count", "message_count"]])
```

---

## Analyzing Message Data

### Count Sent vs. Received

```python
from pymessage import find_backups, get_messages

backups = find_backups()
df = get_messages(backups[0])

sent = df[df["is_from_me"] == True]
received = df[df["is_from_me"] == False]

print(f"Sent:     {len(sent)}")
print(f"Received: {len(received)}")
```

### Find Messages with Reactions

```python
from pymessage import find_backups, get_messages

backups = find_backups()
df = get_messages(backups[0])

reactions = df[df["reaction_type"].notna()]
print(f"Total reactions: {len(reactions)}")
print(reactions["reaction_type"].value_counts())
```

### Monthly Message Volume

```python
from pymessage import find_backups, get_messages

backups = find_backups()
df = get_messages(backups[0])

df["month"] = df["timestamp"].dt.to_period("M")
monthly = df.groupby("month").size().reset_index(name="message_count")
print(monthly)
```

---

## Working with Attachments

### List All Attachments

```python
from pymessage import find_backups, get_attachments

backups = find_backups()
attachments = get_attachments(backups[0])

print(f"Total attachments: {len(attachments)}")
print(attachments[["filename", "mime_type", "file_size"]].head())
```

### Find Images Only

```python
from pymessage import find_backups, get_attachments

backups = find_backups()
attachments = get_attachments(backups[0])

images = attachments[attachments["mime_type"].str.startswith("image/", na=False)]
print(f"Images: {len(images)}")
print(images["mime_type"].value_counts())
```

### Get Attachments for a Specific Contact

```python
from pymessage import find_backups, get_attachments

backups = find_backups()
attachments = get_attachments(backups[0], phone_numbers="+12085550100")

print(f"Attachments from this contact: {len(attachments)}")
```

---

## Analytics

### Overall Activity Summary

```python
from pymessage import find_backups, get_messages, get_activity_summary

backups = find_backups()
df = get_messages(backups[0])

summary, top_contacts = get_activity_summary(df)

print(f"Total messages: {summary['total_messages'].iloc[0]}")
print(f"Most active day: {summary['most_active_day_of_week'].iloc[0]}")
print(f"Most active hour: {summary['most_active_hour'].iloc[0]}:00")
print()
print("Top contacts:")
print(top_contacts)
```

### Activity for a Specific Contact

```python
from pymessage import find_backups, get_messages, get_contact_summary

backups = find_backups()
df = get_messages(backups[0])

stats = get_contact_summary(df, "+12085550100")

print(f"Total messages: {stats['total_messages'].iloc[0]}")
print(f"You sent:       {stats['total_sent'].iloc[0]}")
print(f"They sent:      {stats['total_received'].iloc[0]}")
```

### Message Heatmap for a Contact

```python
from pymessage import find_backups, get_messages, get_contact_heatmap

backups = find_backups()
df = get_messages(backups[0])

# Returns a 7×24 DataFrame: rows = days of week, columns = hours 0–23
heatmap = get_contact_heatmap(df, "+12085550100")
print(heatmap)
```

---

## Using a Direct Path

If you already know where your backup is, you can pass the path directly instead of using `find_backups()`.

=== "iPhone Backup"

    ```python
    from pymessage import get_messages

    df = get_messages("~/Library/Application Support/MobileSync/Backup/your-backup-id")
    print(df.head())
    ```

=== "macOS Messages"

    ```python
    from pymessage import get_messages

    df = get_messages("~/Library/Messages/chat.db")
    print(df.head())
    ```

!!! note "Finding your backup ID"
    Open Finder, press **Command + Shift + G**, paste
    `~/Library/Application Support/MobileSync/Backup/`, and press Enter.
    The folder name you see is your backup ID.
