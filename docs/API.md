# API Reference

Complete API documentation for PyMessage functions.

## Core Functions

### get_messages

Retrieve iMessage messages from iPhone backup database.

::: pymessage.messages.get_messages

### list_conversations

List all conversations with summary statistics.

::: pymessage.conversations.list_conversations

## Backup Management

### find_backups

Scan default macOS location for iPhone backups.

::: pymessage.backups.find_backups

### get_backup_info

Extract metadata from iPhone backup directory.

::: pymessage.backups.get_backup_info

## Attachments

### get_attachments

Retrieve attachment metadata and file paths.

::: pymessage.attachments.get_attachments

### resolve_attachment_path

Resolve attachment filename to actual path in backup.

::: pymessage.attachments.resolve_attachment_path

## Utility Functions

### convert_apple_timestamp

Convert Apple timestamp to pandas Timestamp.

::: pymessage.schema.convert_apple_timestamp

### parse_reaction_type

Parse reaction/tapback type from associated_message_type.

::: pymessage.schema.parse_reaction_type

### normalize_phone_number

Normalize phone number to digits-only format.

::: pymessage.utils.normalize_phone_number

### generate_phone_variants

Generate lookup variants for phone number matching.

::: pymessage.utils.generate_phone_variants
