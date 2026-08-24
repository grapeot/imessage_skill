# PRD: iMessage Skill

## Goal

Provide an AI-first iMessage skill for macOS with two capabilities:

1. **Send** — an agent sends an iMessage to an explicit handle after a dry-run review and explicit send confirmation.
2. **Read** — an agent inspects the local Messages history (a conversation with a contact, full-text search, or recent conversations) after a dry-run review and explicit read confirmation.

Both capabilities are read-your-own-machine tools: sending goes through `Messages.app`, reading goes through the local `chat.db` in read-only mode.

## Users

The primary user is a Mac owner who delegates communication tasks to a local or remote AI agent. The user may not be physically near the Mac after initial setup, so routine sends must not require per-message GUI approval, and routine lookups ("what did X last tell us?") must not require the user to copy messages out of the Messages app by hand.

## Requirements

Send path:

- Send iMessage through the local `Messages.app` account.
- Accept a handle passed by the caller, such as `alice@example.com` or `+15555550123`.
- Dry-run without touching Messages.
- Require `--confirm-send` for real sends.

Read path:

- Read message history from `~/Library/Messages/chat.db` in **read-only** mode; never write to the database.
- Decode message bodies from the `attributedBody` BLOB (Apple `streamtyped` format), since the `text` column is mostly empty.
- Support three read operations: `read` (one conversation by handle or contact name), `search` (full-text across history), and `chats` (recent conversations).
- Support time windows (`--since` / `--until`), direction filtering (`--direction in|out|all`), and result caps (`--limit`).
- Resolve contact display names to handles via the Contacts app when `--name` is used.
- Default to dry-run: report match counts and resolved handles only. Require `--confirm-read` to return message content.
- Accept an injectable database path (`--db`) so tests run against fixtures.

Shared:

- Return machine-readable JSON for agent workflows.
- Include offline tests and a skipped-by-default live integration test.
- Keep private handles and contact aliases out of the public repository.

## Non-Goals

- Modifying, deleting, or reacting to messages in any way.
- Group chat creation or sending to group chats.
- Verifying whether a handle is iMessage-capable before send.
- SMS fallback.
- Background daemon behavior or sync.
- Reading attachments, media, or read receipts.

## Success Criteria

- `imessage-send send --dry-run --format json` produces a complete review payload without launching or controlling Messages.
- `imessage-send send --confirm-send --format json` calls the AppleScript bridge and returns a success envelope when `osascript` exits cleanly.
- `imessage-send read --to <handle> --format json` (without `--confirm-read`) opens the database read-only, reports `match_count`, and prints no message content.
- `imessage-send read --to <handle> --confirm-read --format json` returns decoded message text, including bodies stored only in `attributedBody`.
- `imessage-send search` and `imessage-send chats` follow the same dry-run / `--confirm-read` gate.
- Default `pytest` runs without sending messages and without touching the real `chat.db`.
- Live integration sends one message only when all opt-in environment variables are present.
- A privacy scan finds no real contact handles in public repo files.
