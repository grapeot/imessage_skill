# iMessage Skill

AI-first macOS iMessage CLI. The repository is self-contained: a pure-Python package, a command-line entry point, offline tests, and a plain Markdown skill contract at `skills/skill_imessage.md`.

It does two things:

- **Send** outbound iMessages through the signed-in `Messages.app` account.
- **Read** local message history from `~/Library/Messages/chat.db` in read-only mode.

It does **not** modify messages, create groups, fall back to SMS, or run as a background daemon.

## What It Does

Send:
- Sends iMessage messages through the signed-in macOS `Messages.app` account.
- Accepts an explicit iMessage handle such as an Apple ID email address or phone number.
- Dry-runs by default for agent review; requires `--confirm-send` for real sends.

Read:
- Reads a conversation with a contact (`read`), full-text searches history (`search`), or lists recent conversations (`chats`).
- Decodes message bodies from the `attributedBody` BLOB (Apple `streamtyped` format) — the `text` column is mostly empty.
- Dry-runs by default (reports match counts only); requires `--confirm-read` to return message content.
- Opens the database read-only and never writes to it.

## Install

From this repository root:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

This installs the `imessage-send` console script and the `imessage_skill` Python package.

## Configure

No configuration is required for dry-runs or ordinary CLI use when the target handle is passed with `--to`.

For live integration tests, copy `.env.example` to `.env` and put the private recipient handle there:

```bash
IMESSAGE_LIVE_TO=alice@example.com
IMESSAGE_ENABLE_LIVE_TESTS=1
IMESSAGE_LIVE_ALLOW_SEND=1
```

Do not commit `.env`. Public examples must use fake handles.

## macOS Permission Setup

The Mac must be signed in to iMessage in `Messages.app`. Two separate permission surfaces are involved:

- **Sending (Automation).** The first real send from a launcher (Terminal, OpenCode, Python, …) may trigger a macOS Automation prompt asking whether that app can control Messages. Approve it once; subsequent sends from the same launcher should not prompt per message. If automation fails, check `System Settings → Privacy & Security → Automation` and confirm the launcher is allowed to control Messages.
- **Reading (Full Disk Access).** Reading `~/Library/Messages/chat.db` requires the launcher to be able to read that file. On recent macOS this usually means granting **Full Disk Access** (`System Settings → Privacy & Security → Full Disk Access`) to the terminal or agent host. If the database is not accessible, the CLI returns a clean error instead of crashing. `imessage-send doctor messages-db` checks this.

## Use the CLI

Dry-run a send:

```bash
imessage-send send --to alice@example.com --body "Hello from an agent" --dry-run --format json
```

Send for real after review:

```bash
imessage-send send --to alice@example.com --body "Hello from an agent" --confirm-send --format json
```

Read the body from a file:

```bash
imessage-send send --to alice@example.com --body-file body.txt --dry-run --format json
```

Read a conversation (dry-run reports the match count; add `--confirm-read` for content):

```bash
imessage-send read --to +15555550123 --since 2026-08-01 --until 2026-08-24 --format json
imessage-send read --to +15555550123 --confirm-read --limit 50 --format json
imessage-send read --name "Alice" --direction in --confirm-read --format json
```

Search across history:

```bash
imessage-send search --query "invoice" --since 2026-01-01 --confirm-read --format json
```

List recent conversations:

```bash
imessage-send chats --limit 20 --confirm-read --format json
```

Check the local automation surface and database readability without sending or reading content:

```bash
imessage-send doctor applescript --format json
imessage-send doctor messages-db --format json
```

## Install the Agent Skill

This project uses a plain Markdown skill contract, not a Codex or Claude Code packaged skill format.

1. Put `skills/skill_imessage.md` somewhere your agent can discover, usually a global or workspace `skills/` directory.
2. Look at the workspace root guidance files such as `AGENTS.md`, `CLAUDE.md`, or equivalent.
3. If those files point to a skill index or discovery document, add this skill there.
4. If no discovery file exists, add a short note to the root guidance file telling the agent to read `skills/skill_imessage.md` for iMessage send/read tasks.

Example guidance:

```text
For macOS iMessage sending and reading, read skills/skill_imessage.md and follow its CLI contract. Private contact aliases live outside the public skill repository.
```

## Test

Default tests are offline:

```bash
.venv/bin/python -m pytest -v
```

Live integration is opt-in and sends a real iMessage:

```bash
IMESSAGE_ENABLE_LIVE_TESTS=1 \
IMESSAGE_LIVE_ALLOW_SEND=1 \
IMESSAGE_LIVE_TO=alice@example.com \
IMESSAGE_LOAD_DOTENV=1 .venv/bin/python -m pytest -v -m live_integration
```

You can also put those variables in private `.env` and run only:

```bash
IMESSAGE_LOAD_DOTENV=1 .venv/bin/python -m pytest -v -m live_integration
```

Run the live test only when a Mac user is ready to approve any first-time macOS Automation prompt.

## Privacy

Do not commit `.env`, private handles, contact maps, message bodies, screenshots, chat exports, local Messages databases, token caches, or real automation logs. This repository is designed to be publishable with only fake examples.
