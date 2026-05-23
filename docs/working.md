# Working Notes

## Changelog

### 2026-05-23

- Created the publishable iMessage skill project skeleton.
- Defined the send-only AppleScript bridge and CLI safety model.
- Added offline tests and a gated live integration test plan.
- Verified default tests: 6 passed, 1 live integration test skipped by design.
- Verified `ruff check .` passes.
- Ran a public-repo privacy scan for private handles; no matches found.
- Added private `.env` loading for the live integration test to avoid leaking handles into shell history.
- Verified live integration test: 1 passed, 6 deselected.

## Lessons Learned

- Use `participant` rather than `buddy` for direct iMessage handles.
- Keep contact aliases outside the public repository; this repo should only know about explicit handles supplied at runtime.
- Avoid UI scripting for remote use because Automation permission is easier to stabilize than Accessibility plus focused-window control.
