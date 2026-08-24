# iMessage Skill

## Project Role

This repository provides an AI-first macOS iMessage skill: a Python library, CLI, and plain Markdown skill contract for sending iMessage messages from a Mac through `Messages.app` and for reading local message history from `~/Library/Messages/chat.db`.

Two supported operations:

- **Send**: a user-approved outbound iMessage to an explicit handle, through the Messages AppleScript bridge.
- **Read**: read-only inspection of local history (`read`, `search`, `chats`), gated by `--confirm-read`.

It is not a message editor, contact manager, chat archive tool, or broad Messages automation framework. The read path never writes to `chat.db`.

## Project Structure

- `README.md`: public installation and usage guide for humans and agents.
- `docs/prd.md`: product scope, requirements, and success criteria.
- `docs/rfc.md`: single architecture RFC covering both the send path (AppleScript bridge) and the read path (read-only `chat.db` access, `streamtyped` body decoding, `--confirm-read` gate), plus shared privacy and permission decisions.
- `docs/test.md`: offline, mocked, and live integration test strategy.
- `docs/working.md`: changelog and lessons learned.
- `skills/skill_imessage.md`: canonical agent skill contract.
- `src/imessage_skill/`: reusable Python package.
- `scripts/`: stable wrappers for humans and agents.
- `tests/`: default offline tests plus opt-in live integration tests.

## Environment Rules

- Use the project virtual environment: `uv venv .venv`, then `source .venv/bin/activate`.
- Install dependencies with `uv pip install -e '.[dev]'`; do not use bare `pip install`.
- Never commit `.env`, private handles, contact maps, message bodies, screenshots, chat exports, SQLite data, token caches, or real automation logs.
- This repository is intended to be publishable. Public docs, examples, and fixtures must use fake handles such as `alice@example.com` or `+15555550123`.
- The Python code reads environment variables after shell resolution. It must not call 1Password or any private contact store directly.

## Safety Boundaries

- Real sends require `--confirm-send`; dry-run is the default safe workflow.
- Read commands default to dry-run (counts only, no content). Message content requires `--confirm-read`.
- The read path opens `chat.db` strictly read-only (`mode=ro`); it must never write to the database.
- Contact name resolution (`--name`) queries the local Contacts app read-only; it is used only to locate handles for history lookup. Private alias-to-handle mappings still belong in workspace guidance, not in this repository.
- Live tests require `IMESSAGE_ENABLE_LIVE_TESTS=1`, `IMESSAGE_LIVE_ALLOW_SEND=1`, and `IMESSAGE_LIVE_TO`.
- Do not add message modification, group messaging, SMS fallback, or background sync behavior without a new RFC.

## Maintenance

- Update `docs/working.md` after meaningful design or implementation changes.
- Keep `docs/rfc.md`, `docs/test.md`, and `skills/skill_imessage.md` aligned with CLI contract changes.
- This directory is an independent git repository. Commit from this repository root, not from a parent workspace.
