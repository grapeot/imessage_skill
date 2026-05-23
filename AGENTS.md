# iMessage Skill

## Project Role

This repository provides an AI-first macOS iMessage sending skill: a Python library, CLI, and plain Markdown skill contract for sending iMessage messages from a Mac through `Messages.app`.

It is not a message reader, contact manager, chat archive tool, or broad Messages automation framework. The only supported operation is sending a user-approved outbound iMessage to an explicit handle.

## Project Structure

- `README.md`: public installation and usage guide for humans and agents.
- `docs/prd.md`: product scope, requirements, and success criteria.
- `docs/rfc.md`: architecture, AppleScript bridge, privacy, and permission decisions.
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
- Live tests require `IMESSAGE_ENABLE_LIVE_TESTS=1`, `IMESSAGE_LIVE_ALLOW_SEND=1`, and `IMESSAGE_LIVE_TO`.
- The CLI must not read Contacts or Messages history. Handle resolution belongs to private workspace guidance outside this public repository.
- Do not add received-message reading, contact discovery, group messaging, or background sync behavior without a new RFC.

## Maintenance

- Update `docs/working.md` after meaningful design or implementation changes.
- Keep `docs/rfc.md`, `docs/test.md`, and `skills/skill_imessage.md` aligned with CLI contract changes.
- This directory is an independent git repository. Commit from this repository root, not from a parent workspace.
