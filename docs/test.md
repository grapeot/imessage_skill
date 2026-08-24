# Test Strategy

## Offline Unit Tests

Default tests cover pure Python behavior:

Send path:
- CLI dry-run output.
- Required `--confirm-send` behavior.
- Body and body-file validation.
- AppleScript command construction.
- JSON envelope shape.

Read path:
- Apple-epoch ↔ ISO-8601 conversion (`iso_to_ns` / `ns_to_iso`), including date-only inputs and invalid-input errors.
- `attributedBody` decoding: UTF-16LE BOM fast path, `streamtyped` marker segments with single- and two-byte length prefixes, UTF-8 fallback, and empty/None inputs.
- US-aware digit-based handle matching (e.g. `(206) 458-5315` matches `+12064585315`), exact email matching, and no-match cases.
- `read_history` / `count_history` with direction and time-window filters.
- `search_messages` / `count_search` case-insensitivity and empty-query errors.
- `list_chats` / `count_chats`.
- Contact name resolution with an injected fake runner (no real Contacts app, no osascript subprocess).
- CLI dry-run vs `--confirm-read` for `read`, `search`, and `chats`, run against a synthetic `chat.db` via `--db`.

Run:

```bash
.venv/bin/python -m pytest -v
```

## Synthetic Database Fixture

`tests/conftest.py` builds a minimal `chat.db` in a temp dir with the exact tables the reader queries (`handle`, `message`, `chat`, `chat_message_join`, `chat_handle_join`). It contains:

- A phone handle (`+12064585315`) and an email handle (`alice@example.com`).
- A plain-`text` message, an `attributedBody`-only message (streamtyped blob), and a second-conversation message.
- Two chats wired through the join tables.

This lets every read-path test run deterministically without touching the user's real `~/Library/Messages/chat.db`.

## Mocked Integration Tests

Subprocess execution is injectable. Tests can replace the runner and assert that real sends would call `osascript` with the expected script and arguments without touching Messages. Contact resolution is tested the same way by injecting a fake runner that returns canned phone/email output.

## Live Integration Test

The live test sends one real iMessage and is skipped unless all opt-in gates are set:

```bash
IMESSAGE_ENABLE_LIVE_TESTS=1 \
IMESSAGE_LIVE_ALLOW_SEND=1 \
IMESSAGE_LIVE_TO=alice@example.com \
IMESSAGE_LOAD_DOTENV=1 .venv/bin/python -m pytest -v -m live_integration
```

The test target belongs in private environment, not in tracked files. The first run may require the Mac user to approve Automation permissions.

The live test reads a private `.env` file from the repository root only when `IMESSAGE_LOAD_DOTENV=1` is set. This avoids putting private handles in shell history while keeping default `pytest` side-effect free.

## Manual Verification

After the live test runs, verify that the recipient received exactly one message containing the generated unique token. Do not commit screenshots or transcripts.

For the read path, a developer can sanity-check against their own machine with an explicit `--db` copy (never the live path in tests):

```bash
.venv/bin/python -m imessage_skill.cli read --to +15555550123 --confirm-read --limit 5 --format json
```
