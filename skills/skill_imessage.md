# iMessage Skill

## Purpose

Use this skill to send outbound iMessage messages and to read local iMessage/SMS history from a macOS machine, through `Messages.app` (send) and the local `chat.db` (read). This is the canonical agent contract for this repository.

This is a plain Markdown skill document, not a vendor-specific packaged skill format. Agents should read it when the user asks to send an iMessage from a Mac or to look up local message history.

## Project Setup

From the repository root:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

Do not commit `.env`, private handles, contact maps, message bodies, screenshots, chat exports, local Messages databases, or automation logs.

## Send iMessage

Always dry-run before a real send unless the user has already given clear send authorization. Real sends require `--confirm-send`.

Dry-run:

```bash
.venv/bin/python -m imessage_skill.cli send \
  --to alice@example.com \
  --body "Message text" \
  --dry-run \
  --format json
```

Real send:

```bash
.venv/bin/python -m imessage_skill.cli send \
  --to alice@example.com \
  --body "Message text" \
  --confirm-send \
  --format json
```

Use `--body-file` for longer messages:

```bash
.venv/bin/python -m imessage_skill.cli send \
  --to alice@example.com \
  --body-file body.txt \
  --dry-run \
  --format json
```

## Read Message History

Reading is read-only and defaults to a dry-run that reports only how many messages match. Message content is only returned with `--confirm-read`.

Read a conversation by handle:

```bash
.venv/bin/python -m imessage_skill.cli read \
  --to +15555550123 \
  --since 2026-08-01 \
  --until 2026-08-24 \
  --limit 50 \
  --format json
```

Confirm the read (returns message content):

```bash
.venv/bin/python -m imessage_skill.cli read \
  --to +15555550123 \
  --confirm-read \
  --format json
```

Resolve a contact by display name (via the Contacts app):

```bash
.venv/bin/python -m imessage_skill.cli read \
  --name "Alice" \
  --direction in \
  --confirm-read \
  --format json
```

Search across all history:

```bash
.venv/bin/python -m imessage_skill.cli search \
  --query "invoice" \
  --since 2026-01-01 \
  --confirm-read \
  --format json
```

List recent conversations:

```bash
.venv/bin/python -m imessage_skill.cli chats --limit 20 --confirm-read --format json
```

Notes:

- `--since` / `--until` accept ISO-8601 or `YYYY-MM-DD`; naive values are interpreted in the local timezone.
- `--direction` filters by sender (`in`, `out`, `all`).
- `--db` overrides the database path (defaults to `~/Library/Messages/chat.db`).
- Phone matching is digit-based and US-aware: `(206) 458-5315` matches `+12064585315`.

## Doctor

Check that `osascript` is available and that the Messages scripting dictionary exposes iMessage accounts:

```bash
.venv/bin/python -m imessage_skill.cli doctor applescript --format json
```

Check that the local Messages database is readable:

```bash
.venv/bin/python -m imessage_skill.cli doctor messages-db --format json
```

The first read may require the launcher to have access to `~/Library/Messages` (see Setup below). These commands should not send a message.

## macOS Permission Setup

- Sending: the first real send from a launcher (Terminal, OpenCode, Python, …) may trigger a macOS Automation prompt asking whether that app can control Messages. Approve it once; subsequent sends from the same launcher should not prompt per message. Check `System Settings → Privacy & Security → Automation` if automation fails.
- Reading: the launcher must be able to read `~/Library/Messages/chat.db`. On recent macOS this typically requires granting **Full Disk Access** (System Settings → Privacy & Security → Full Disk Access) to the terminal or agent host. If the database is not accessible, the CLI returns a clean error instead of crashing.

## Contacts and Aliases

This public repository does not store private contact aliases. If the user says "message 老孟", resolve that alias from private workspace guidance first, then pass the resolved handle to this CLI with `--to`. For read commands, `--name` resolves a display name to handles via the local Contacts app; private alias-to-handle mappings still belong in workspace guidance, not in this repository.

## Tests

Default tests are offline:

```bash
.venv/bin/python -m pytest -v
```

Live integration sends a real iMessage and is skipped unless explicitly enabled:

```bash
IMESSAGE_ENABLE_LIVE_TESTS=1 \
IMESSAGE_LIVE_ALLOW_SEND=1 \
IMESSAGE_LIVE_TO=alice@example.com \
IMESSAGE_LOAD_DOTENV=1 .venv/bin/python -m pytest -v -m live_integration
```

The same variables can live in private `.env`; set `IMESSAGE_LOAD_DOTENV=1` to let the live test read it. This keeps default `pytest` from sending a real iMessage just because `.env` exists.

## Boundaries

- Do not send real iMessages unless the user clearly asked for a real send and the command includes `--confirm-send`.
- Do not read message content without `--confirm-read`, and only for conversations the user explicitly asked about.
- Reads are strictly read-only: never write to `chat.db`.
- Do not add SMS fallback unless the user explicitly asks and a new RFC covers the behavior.
- Do not commit private recipient handles or message bodies.
