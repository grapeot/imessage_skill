# Working Notes

## Changelog

### 2026-08-24 (RFC consolidation)

- Merged `docs/rfc.md` (send path) and `docs/rfc_read.md` (read path) into a single `docs/rfc.md` covering both paths plus shared concerns (privacy, macOS permissions, alternatives). Rewrote the prose for consistency; restructured into Send Path / Read Path / Shared Concerns sections.
- Fact-drift audit (independent sub-agent pass): no dropped or altered technical facts; only language and structure changed.
- Removed `docs/rfc_read.md`; updated `AGENTS.md` project-structure and maintenance references.

### 2026-08-24 (read-path correctness fixes)

- Fixed search time-window SQL precedence: wrapped the `text OR attributedBody` candidate predicate in parentheses so `--since`/`--until` now constrain both branches, not just the `attributedBody` one.
- Wired `--direction` through the search path (`search_messages` / `count_search` / `handle_search`); it was previously accepted but ignored.
- `--limit` now rejects non-positive values via a `positive_int` argparse type on `read`/`search`/`chats`, so `LIMIT -1` (unlimited) can no longer be reached from the CLI.
- Added regression tests: search time-window, search direction (unit + CLI), and negative/zero limit rejection.
- Verified: 48 passed, 1 live integration skipped; `ruff check .` clean.

### 2026-08-24 (security fix)

- Fixed osascript argument injection: `build_send_command` and the Contacts `resolve_name` lookup now insert a `--` option-terminator after the `-e <script>` argument, so a dash-prefixed handle/body/query is delivered to the `on run` handler as data instead of being parsed by `osascript` as its own flag (e.g. `-e <script>`). Verified empirically on macOS.
- Added regression test `test_build_send_command_terminates_options_before_user_data`.
- Documented the fix under "osascript argument injection" in `docs/rfc.md` and `docs/rfc_read.md`.

### 2026-08-24

- Added read-only access to local iMessage history: `read`, `search`, and `chats` subcommands.
- Implemented a native Python port of imsg's `TypedStreamParser` (`messages_db.py`) to decode `attributedBody` BLOBs (UTF-16LE BOM fast path, `streamtyped` marker segments with BER-style length prefixes, UTF-8 fallback). No external binary dependency.
- Added `contacts.py` for display-name → handle resolution via the Contacts app (osascript), injectable runner for tests.
- Added `--confirm-read` gate: read commands default to dry-run (counts only); content requires explicit confirmation. `--db` allows an injectable database path for tests.
- Added `doctor messages-db` to check local database readability.
- Added `tests/conftest.py` synthetic `chat.db` fixture and `tests/test_messages_db.py`, `tests/test_contacts.py`; extended `tests/test_cli.py` for read/search/chats.
- Verified default suite: 42 passed, 1 live integration skipped. `ruff check .` clean.
- Verified read path against the real `~/Library/Messages/chat.db` (dry-run + confirmed read) — streamtyped parser decodes real multi-line SMS correctly.
- Wrote `docs/rfc_read.md`; updated `docs/prd.md`, `docs/test.md`, `skills/skill_imessage.md`, `README.md`, `AGENTS.md`, and the workspace overlay.
- Bumped version 0.1.0 → 0.2.0.

### 2026-05-23

- Created the publishable iMessage skill project skeleton.
- Defined the send-only AppleScript bridge and CLI safety model.
- Added offline tests and a gated live integration test plan.
- Verified default tests: 6 passed, 1 live integration test skipped by design.
- Verified `ruff check .` passes.
- Ran a public-repo privacy scan for private handles; no matches found.
- Added private `.env` loading for the live integration test to avoid leaking handles into shell history.
- Verified live integration test: 1 passed, 6 deselected.
- Added `IMESSAGE_LOAD_DOTENV=1` gate so default tests stay side-effect free even when private `.env` exists.
- Re-verified default tests: 6 passed, 1 live integration test skipped by design.
- Re-verified explicit live integration: 1 passed, 6 deselected.

## Lessons Learned

- Use `participant` rather than `buddy` for direct iMessage handles.
- Keep contact aliases outside the public repository; this repo should only know about explicit handles supplied at runtime.
- Avoid UI scripting for remote use because Automation permission is easier to stabilize than Accessibility plus focused-window control.
- The `text` column in `chat.db` is mostly empty; the body lives in the `attributedBody` BLOB, which is an Apple `streamtyped`/NSKeyedArchiver payload, **not** a standard plist. `plistlib` cannot parse it.
- `message.date` is nanoseconds since the Apple epoch (2001-01-01 UTC), not Unix time.
- `imsg` (openclaw/imsg, Swift) works, but its resource bundles (`PhoneNumberKit`, `SQLite.swift`) must sit next to the binary or it fatal-errors. A native Python port keeps the skill self-contained and testable.
- Phone handles are stored in multiple formats; match on digits with a US-aware rule (strip a leading `1` from 11-digit numbers) rather than exact string equality.
- Reading `~/Library/Messages/chat.db` typically requires the launcher to have Full Disk Access on recent macOS; the CLI should fail with a clean error, not a stack trace.
- `osascript` parses trailing dash-prefixed arguments as its own options even when passed via a Python list (no shell involved). Always insert `--` after the `-e <script>` argument before any user-controlled value, or a handle like `-e <script>` becomes executable AppleScript.
