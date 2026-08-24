# RFC: macOS iMessage Send Bridge

Companion RFC for the read path: `docs/rfc_read.md` (read-only `chat.db` access, `streamtyped` body decoding, `--confirm-read` gate). This document covers the send path only.

## Decision

Use `osascript` to call the native Messages AppleScript dictionary. The Python package owns argument parsing, safety checks, dry-run output, subprocess execution, and JSON envelopes. AppleScript owns only the final send operation.

## AppleScript Contract

The send operation uses `participant`, not `buddy`:

```applescript
on run {targetHandle, targetMessage}
  tell application "Messages"
    set targetAccount to first account whose service type = iMessage
    set targetParticipant to participant targetHandle of targetAccount
    send targetMessage to targetParticipant
  end tell
end run
```

`participant` is the right abstraction for direct handles. `buddy` can behave like a historical/contact-backed object and is more likely to fail for handles that have not appeared in prior conversations.

## CLI Contract

The stable user-facing command is:

```bash
imessage-send send --to alice@example.com --body "Hello" --dry-run --format json
imessage-send send --to alice@example.com --body "Hello" --confirm-send --format json
```

The package module entry point is also stable:

```bash
.venv/bin/python -m imessage_skill.cli send --to alice@example.com --body "Hello" --dry-run
```

## Safety Model

Dry-run is side-effect free. Real sends require `--confirm-send`. The CLI does not add its own per-recipient allowlist because contact aliasing is workspace-specific and belongs outside this publishable repository.

### osascript argument injection

User-controlled values (handle, message body, contact query) are passed to `osascript` as trailing arguments to the `on run` handler. Without a guard, a value starting with `-` is parsed by `osascript` itself as an option — e.g. a handle of `-e <script>` would be evaluated as AppleScript. Every osascript invocation therefore inserts `--` after the `-e <script>` argument to terminate option parsing, so all subsequent values reach the run handler as data. Verified empirically: without `--`, a dash-prefixed argument is consumed by osascript's option parser; with `--`, it is delivered to the handler intact.

## Privacy Model

The public repo never stores real handles. Live test targets live in `.env`, which is gitignored. Workspace-specific contact aliases can point to this repo's skill document while storing private aliases in a separate private skill file.

## macOS Permission Model

The first real send from a launcher may trigger a macOS Automation prompt. This should be a one-time approval for that launcher to control Messages, not a per-message approval. UI scripting is intentionally avoided because it adds focus and Accessibility dependencies.

## Alternatives Considered

Direct Messages database writes were rejected because they are private, brittle, and unsafe. For the **send** path, Contacts lookup was rejected because the caller can provide the handle and private aliasing belongs in the workspace; the **read** path does resolve display names via Contacts, but only to locate a handle for local history lookup (see `docs/rfc_read.md`). UI scripting was rejected because it is less stable for a remote agent workflow.
