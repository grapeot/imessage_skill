# RFC: iMessage Skill — Send and Read Architecture

This is the single design document for the iMessage skill. It covers both supported paths — the **send** bridge (outbound messages through the Messages AppleScript dictionary) and the **read** path (read-only inspection of local history from `chat.db`) — together with the decisions and constraints they share.

## Send Path

### Decision

The send path shells out to `osascript` to drive the native Messages AppleScript dictionary. The Python package owns everything around that call — argument parsing, safety checks, dry-run output, subprocess execution, and the JSON envelope — while AppleScript owns only the final send operation.

### AppleScript Contract

The send operation targets a `participant`, not a `buddy`:

```applescript
on run {targetHandle, targetMessage}
  tell application "Messages"
    set targetAccount to first account whose service type = iMessage
    set targetParticipant to participant targetHandle of targetAccount
    send targetMessage to targetParticipant
  end tell
end run
```

`participant` is the right abstraction for a direct handle. A `buddy` can behave like a historical, contact-backed object and is more likely to fail for a handle that has not appeared in prior conversations.

### CLI Contract

The stable user-facing command is:

```bash
imessage-send send --to alice@example.com --body "Hello" --dry-run --format json
imessage-send send --to alice@example.com --body "Hello" --confirm-send --format json
```

The package module entry point is also stable:

```bash
.venv/bin/python -m imessage_skill.cli send --to alice@example.com --body "Hello" --dry-run
```

### Safety Model

Dry-run is side-effect free. A real send requires `--confirm-send`. The CLI does not add its own per-recipient allowlist, because contact aliasing is workspace-specific and belongs outside this publishable repository.

### osascript Argument Injection

User-controlled values (handle, message body, contact query) reach `osascript` as trailing arguments to the `on run` handler. Without a guard, a value that starts with `-` is parsed by `osascript` itself as an option — for example, a handle of `-e <script>` would be evaluated as AppleScript. Every osascript invocation therefore inserts `--` after the `-e <script>` argument to terminate option parsing, so all subsequent values reach the run handler as data. This was verified empirically: without `--`, a dash-prefixed argument is consumed by osascript's option parser; with `--`, it is delivered to the handler intact.

## Read Path

### Decision

The read path opens the local Messages database (`~/Library/Messages/chat.db`) strictly read-only and exposes it through three CLI subcommands: `read`, `search`, and `chats`. The body parser is implemented natively in Python as a port of imsg's `TypedStreamParser`, so the skill stays a pure-Python, dependency-free package with no external binary requirement.

### Motivation

- The agent needs to look up past conversations (for example, "what did the Vancouver limo company charge us?") without the user copying messages by hand.
- The Messages AppleScript dictionary is send-only; there is no scripting API for reading history, so direct SQLite access is the only viable route.
- `imsg` (openclaw/imsg, a Swift tool) does the same job, but it ships as a prebuilt binary whose resource bundles must sit next to the executable. A ~50-line Python port keeps the skill self-contained, testable, and publishable.

### Data Model

- `handle(id, uncanonicalized_id, service)` — one row per contact address.
- `message(guid, text, attributedBody, date, is_from_me, handle_id, service, is_empty, ...)` — `date` is **nanoseconds since 2001-01-01 UTC** (the Apple epoch).
- `chat(ROWID, chat_identifier, display_name, service_name)`, joined to messages through `chat_message_join` and to handles through `chat_handle_join`.

Two facts shaped the implementation:

- The `text` column is mostly empty; the body lives in the `attributedBody` BLOB.
- `attributedBody` is an Apple `streamtyped` / NSKeyedArchiver payload, **not** a standard plist.

### Body Decoding

The `attributedBody` decoder (a port of imsg's `TypedStreamParser`) tries three strategies in order and keeps the best result:

1. **Fast path** — a UTF-16LE BOM (`0xFF 0xFE`) means the rest of the payload decodes directly as UTF-16LE.
2. **Marker path** — scan for `0x01 0x2B` … `0x86 0x84` segments, strip a BER-style length prefix (one byte, or `0x81 NN`, or `0x82 NN NN`), and keep the longest decodable candidate.
3. **Fallback** — UTF-8 decode with replacement.

Leading control characters are trimmed from the decoded text.

### Handle Matching

Phone matching is digit-based and US-aware: an 11-digit number with a leading `1` is compared against its 10-digit form, so `(206) 458-5315` matches `+12064585315`. Email handles match case-insensitively by string equality. `tel:` prefixes are stripped.

### CLI Contract

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

### Safety Model

- **Dry-run is the default.** Without `--confirm-read`, the CLI only reports counts and resolved handles; it prints no message content. This mirrors the `--confirm-send` gate on the send path.
- The database is opened **read-only** (`file:...?mode=ro`); the skill never writes to `chat.db`.
- `--confirm-read` is the agent's explicit authorization to surface message content. Per the workspace rules, the agent must confirm with the user before reading a conversation the user did not explicitly ask about.
- No message content is ever written to logs, fixtures, or committed files. Public docs and tests use fake handles only.
- The Contacts lookup (`--name`) passes the query to `osascript` with a `--` option-terminator so a dash-prefixed query cannot be parsed as an osascript flag (see "osascript Argument Injection" above).

### Testing Strategy

- A synthetic `chat.db` fixture (`tests/conftest.py`) covers plain `text` rows, `attributedBody` streamtyped blobs (single- and two-byte length prefixes), UTF-16LE BOM payloads, and empty bodies.
- Unit tests cover epoch conversion, handle matching (US-aware digit normalization), and the parser's fallbacks.
- CLI tests exercise dry-run versus confirmed behavior for `read`, `search`, and `chats` against the synthetic DB via `--db`.
- No live test reads the user's real database; the read path is verified against fixtures only.

## Shared Concerns

### Privacy Model

The public repo never stores real handles. Live test targets live in `.env`, which is gitignored. Workspace-specific contact aliases can point to this repo's skill document while keeping private aliases in a separate private skill file.

### macOS Permission Model

- **Sending** — the first real send from a launcher may trigger a one-time macOS **Automation** prompt approving that launcher to control Messages. It is not a per-message approval. UI scripting is intentionally avoided because it adds focus and Accessibility dependencies.
- **Reading** — the launcher (terminal or agent host) must be able to read `~/Library/Messages/chat.db`. On recent macOS this usually means granting **Full Disk Access** (System Settings → Privacy & Security → Full Disk Access) to the terminal or agent host. If the file is not accessible, the CLI returns a clean `MessagesDbError` instead of crashing.

### Alternatives Considered

- **Direct Messages database writes** (send path) — rejected: private, brittle, and unsafe.
- **Contacts lookup for send** — rejected: the caller can provide the handle directly, and private aliasing belongs in the workspace. (The read path does resolve display names via Contacts, but only to locate a handle for local history lookup.)
- **Ship `imsg` as a dependency** (read path) — rejected: the binary plus resource-bundle placement is fragile across machines, and it would make the skill no longer pure Python.
- **AppleScript reading** (read path) — rejected: the Messages dictionary exposes no read/history API.
- **Copy the database first, then parse** (read path) — rejected: an extra copy step for no benefit; read-only SQLite access is safe and atomic enough for this use case.
- **UI scripting** — rejected: less stable for a remote agent workflow.
