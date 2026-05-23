# Test Strategy

## Offline Unit Tests

Default tests cover pure Python behavior:

- CLI dry-run output.
- Required `--confirm-send` behavior.
- Body and body-file validation.
- AppleScript command construction.
- JSON envelope shape.

Run:

```bash
.venv/bin/python -m pytest -v
```

## Mocked Integration Tests

Subprocess execution is injectable. Tests can replace the runner and assert that real sends would call `osascript` with the expected script and arguments without touching Messages.

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
