# API Reference

Complete API documentation for PyMessage functions.

## Core Functions

Retrieve iMessage messages from iPhone backup database.

::: pymessage.messages.get_messages

List all conversations with summary statistics.

::: pymessage.conversations.list_conversations

## Backup Management

Scan default macOS location for iPhone backups.

::: pymessage.backups.find_backups

Extract metadata from iPhone backup directory.

::: pymessage.backups.get_backup_info

## Attachments

Retrieve attachment metadata and file paths.

::: pymessage.attachments.get_attachments

Resolve attachment filename to actual path in backup.

::: pymessage.attachments.resolve_attachment_path

## Utility Functions

Convert Apple timestamp to pandas Timestamp.

::: pymessage.schema.convert_apple_timestamp

Parse reaction/tapback type from associated_message_type.

::: pymessage.schema.parse_reaction_type

Normalize phone number to digits-only format.

::: pymessage.utils.normalize_phone_number

Generate lookup variants for phone number matching.

::: pymessage.utils.generate_phone_variants

## Analytics

Summary statistics across all messages.

::: pymessage.analytics.get_activity_summary

Per-contact messaging statistics.

::: pymessage.analytics.get_contact_summary

Build a 7×24 message-count heatmap for a contact.

::: pymessage.analytics.get_contact_heatmap
