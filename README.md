# iMessage Skill

AI-first macOS iMessage sending from a local CLI. The repository is self-contained: it provides a Python package, a command-line entry point, tests, and a plain Markdown skill contract at `skills/skill_imessage.md`.

This is a send-only tool. It does not read Messages, query Contacts, scrape chat history, or manage address books.

## What It Does

- Sends iMessage messages through the signed-in macOS `Messages.app` account.
- Accepts an explicit iMessage handle such as an Apple ID email address or phone number.
- Dry-runs by default for agent review.
- Requires `--confirm-send` for real outbound messages.
- Runs offline tests by default and an explicit opt-in live integration test when a Mac user is ready to approve permissions.

## Install

From this repository root:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

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

The Mac must be signed in to iMessage in `Messages.app`. The first real send from Terminal, OpenCode, Python, or another launcher may trigger a macOS Automation permission prompt asking whether that app can control Messages. Approve it once. Subsequent sends from the same launcher should not require per-message approval.

If automation fails, check `System Settings -> Privacy & Security -> Automation` and confirm the launcher is allowed to control Messages.

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

Check the local Messages automation surface without sending:

```bash
imessage-send doctor applescript --format json
```

## Install the Agent Skill

This project uses a plain Markdown skill contract, not a Codex or Claude Code packaged skill format.

1. Put `skills/skill_imessage.md` somewhere your agent can discover, usually a global or workspace `skills/` directory.
2. Look at the workspace root guidance files such as `AGENTS.md`, `CLAUDE.md`, or equivalent.
3. If those files point to a skill index or discovery document, add this skill there.
4. If no discovery file exists, add a short note to the root guidance file telling the agent to read `skills/skill_imessage.md` for iMessage sending tasks.

Example guidance:

```text
For macOS iMessage sending, read skills/skill_imessage.md and follow its CLI contract. Private contact aliases live outside the public skill repository.
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
.venv/bin/python -m pytest -v -m live_integration
```

You can also put those variables in private `.env` and run only:

```bash
.venv/bin/python -m pytest -v -m live_integration
```

Run the live test only when a Mac user is ready to approve any first-time macOS Automation prompt.

## Privacy

Do not commit `.env`, private handles, contact maps, message bodies, screenshots, chat exports, local Messages databases, token caches, or real automation logs. This repository is designed to be publishable with only fake examples.
