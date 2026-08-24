# RFC: Read-Only Access to Local iMessage History

## Decision

Add read-only access to the local Messages database (`~/Library/Messages/chat.db`) to the skill, exposed as three CLI subcommands: `read`, `search`, and `chats`. The parser is implemented natively in Python (a port of imsg's `TypedStreamParser`), so the skill remains a pure-Python, dependency-free package with no external binary requirement.

## Why

- The agent needs to look up past conversations (e.g., "what did the Vancouver limo company charge us?") without the user copying messages by hand.
- The Messages AppleScript dictionary is send-only; there is no scripting API for reading history, so direct SQLite access is the only viable route.
- `imsg` (openclaw/imsg, Swift) does the same job, but it is a prebuilt binary whose resource bundles must sit next to the executable. A ~50-line Python port keeps the skill self-contained, testable, and publishable.

## Data Model

- `handle(id, uncanonicalized_id, service)` — one row per contact address.
- `message(guid, text, attributedBody, date, is_from_me, handle_id, service, is_empty, ...)` — `date` is **nanoseconds since 2001-01-01 UTC** (Apple epoch).
- `chat(ROWID, chat_identifier, display_name, service_name)` and the join tables `chat_message_join`, `chat_handle_join`.

Key facts that shaped the implementation:

- The `text` column is mostly empty; the body lives in the `attributedBody` BLOB.
- `attributedBody` is an Apple `streamtyped` / NSKeyedArchiver payload, **not** a standard plist. Decoding strategy (port of imsg's `TypedStreamParser`):
  1. Fast path: UTF-16LE BOM (`0xFF 0xFE`) → decode the rest as UTF-16LE.
  2. Marker path: scan for `0x01 0x2B` … `0x86 0x84` segments; strip a BER-style length prefix (1 byte, or `0x81 NN`, or `0x82 NN NN`); keep the longest decodable candidate.
  3. Fallback: UTF-8 decode with replacement.
- Leading control characters are trimmed from decoded text.

## Handle Matching

Phone matching is digit-based and US-aware: an 11-digit number with a leading `1` is compared against its 10-digit form, so `(206) 458-5315` matches `+12064585315`. Email handles match case-insensitively by string equality. `tel:` prefixes are stripped.

## CLI Contract

```bash
# Dry-run (default): resolves the handle, reports how many messages match, prints no content
imessage-send read --to +15555550123 --since 2024-08-01 --until 2024-09-02 --format json
imessage-send read --name "Alice" --direction in --format json

# Confirmed read: returns message content
imessage-send read --to +15555550123 --confirm-read --limit 50 --format json

# Full-text search across all history (same gate)
imessage-send search --query "invoice" --since 2024-01-01 --confirm-read --format json

# List recent conversations (same gate)
imessage-send chats --limit 20 --confirm-read --format json
```

- `--since` / `--until` accept ISO-8601 or `YYYY-MM-DD`; naive values are interpreted in the local timezone.
- `--direction` filters by `is_from_me` (`in`, `out`, `all`).
- `--db` overrides the database path (used by tests; defaults to `~/Library/Messages/chat.db`).
- `read` returns `match_count` in dry-run mode and `messages` (guid, ISO date, direction, handle, service, text, chat id) in confirmed mode. Results are de-duplicated by guid and capped at `--limit`.

## Safety Model

- **Dry-run is the default.** Without `--confirm-read`, the CLI only reports counts and resolved handles; no message content is printed. This mirrors the `--confirm-send` gate for the send path.
- The database is opened **read-only** (`file:...?mode=ro`); the skill never writes to `chat.db`.
- `--confirm-read` is the agent's explicit authorization to surface message content. Per the workspace rules, the agent must confirm with the user before reading a conversation the user did not explicitly ask about.
- No message content is ever written to logs, fixtures, or committed files. Public docs and tests use fake handles only.
- The Contacts lookup (`--name`) passes the query to `osascript` with a `--` option-terminator so a dash-prefixed query cannot be parsed as an osascript flag (see `docs/rfc.md`, "osascript argument injection").

## macOS Permission Model

- Sending: one-time macOS **Automation** prompt for the launcher to control Messages (see `docs/rfc.md`).
- Reading: the launcher (terminal/agent host) must be able to read `~/Library/Messages/chat.db`. On recent macOS this usually means granting **Full Disk Access** (System Settings → Privacy & Security → Full Disk Access) to the terminal or agent host. If the file is not accessible, the CLI returns a clean `MessagesDbError` instead of crashing.

## Alternatives Considered

- **Ship `imsg` as a dependency**: rejected — binary + resource-bundle placement is fragile across machines, and it makes the skill no longer pure Python.
- **AppleScript reading**: rejected — the Messages dictionary exposes no read/history API.
- **Copy the DB first, then parse**: rejected — an extra copy step for no benefit; read-only SQLite access is safe and atomic enough for this use case.

## Testing Strategy

- Synthetic `chat.db` fixture (see `tests/conftest.py`) covering: plain `text` rows, `attributedBody` streamtyped blobs (single- and two-byte length prefixes), UTF-16LE BOM payloads, and empty bodies.
- Unit tests for epoch conversion, handle matching (US-aware digit normalization), and the parser's fallbacks.
- CLI tests exercise dry-run vs confirmed behavior for `read`, `search`, and `chats` against the synthetic DB via `--db`.
- No live test reads the user's real database; the read path is verified against fixtures only.
