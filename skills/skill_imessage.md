# iMessage Skill

## Purpose

Use this skill to send outbound iMessage messages from a macOS machine through `Messages.app`. This is the canonical agent contract for this repository.

This is a plain Markdown skill document, not a vendor-specific packaged skill format. Agents should read it when the user asks to send an iMessage from a Mac.

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

## Doctor

Check that `osascript` is available and that the Messages scripting dictionary exposes iMessage accounts:

```bash
.venv/bin/python -m imessage_skill.cli doctor applescript --format json
```

This command should not send a message. It may still touch the macOS scripting surface and can expose permission issues.

## Contacts and Aliases

This public repository does not store private contact aliases. If the user says "send老孟 an iMessage", resolve that alias from private workspace guidance first, then pass the resolved handle to this CLI with `--to`.

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
.venv/bin/python -m pytest -v -m live_integration
```

The same variables can live in private `.env`; the live test reads it if present.

## Boundaries

- Do not send real iMessages unless the user clearly asked for a real send and the command includes `--confirm-send`.
- Do not read Messages history.
- Do not read Contacts.
- Do not add SMS fallback unless the user explicitly asks and a new RFC covers the behavior.
- Do not commit private recipient handles or message bodies.
