# PRD: iMessage Skill

## Goal

Provide an AI-first, send-only iMessage skill for macOS. An agent should be able to send an iMessage to an explicit handle after a dry-run review and explicit send confirmation.

## Users

The primary user is a Mac owner who delegates communication tasks to a local or remote AI agent. The user may not be physically near the Mac after initial setup, so routine sends must not require per-message GUI approval.

## Requirements

- Send iMessage through the local `Messages.app` account.
- Accept a handle passed by the caller, such as `alice@example.com` or `+15555550123`.
- Avoid reading Contacts and Messages history.
- Dry-run without touching Messages.
- Require `--confirm-send` for real sends.
- Return machine-readable JSON for agent workflows.
- Include offline tests and a skipped-by-default live integration test.
- Keep private handles and contact aliases out of the public repository.

## Non-Goals

- Reading incoming or historical messages.
- Discovering contacts.
- Verifying whether a handle is iMessage-capable before send.
- Group chat creation.
- SMS fallback.
- Background daemon behavior.

## Success Criteria

- `imessage-send send --dry-run --format json` produces a complete review payload without launching or controlling Messages.
- `imessage-send send --confirm-send --format json` calls the AppleScript bridge and returns a success envelope when `osascript` exits cleanly.
- Default `pytest` runs without sending messages.
- Live integration sends one message only when all opt-in environment variables are present.
- A privacy scan finds no real contact handles in public repo files.
