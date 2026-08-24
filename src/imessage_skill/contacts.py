from __future__ import annotations

import shutil
import subprocess
from typing import Protocol


class ContactResolutionError(Exception):
    pass


RESOLVE_SCRIPT = """
on run {query}
  tell application "Contacts"
    set output to ""
    set matched to (every person whose first name contains query or last name contains query or name contains query)
    repeat with p in matched
      repeat with ph in phones of p
        set output to output & (value of ph) & linefeed
      end repeat
      repeat with em in emails of p
        set output to output & (value of em) & linefeed
      end repeat
    end repeat
    return output
  end tell
end run
""".strip()


class Runner(Protocol):
    def __call__(self, command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        ...


def subprocess_runner(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def osascript_available() -> bool:
    return shutil.which("osascript") is not None


def resolve_name(
    query: str,
    *,
    runner: Runner = subprocess_runner,
    timeout: int = 30,
) -> list[str]:
    """Resolve a contact display name to phone/email handles via the Contacts app.

    Returns a list of raw handle strings (phones and emails). May be empty
    when no contact matches. Raises ContactResolutionError when the
    AppleScript bridge itself fails.
    """
    query = query.strip()
    if not query:
        raise ContactResolutionError("contact name must not be empty")
    if not osascript_available():
        raise ContactResolutionError("osascript is not available on this system")

    # "--" stops osascript option parsing so a dash-prefixed query is passed to
    # the run handler, never interpreted as an osascript flag (e.g. -e).
    result = runner(["osascript", "-e", RESOLVE_SCRIPT, "--", query], timeout)
    if result.returncode != 0:
        raise ContactResolutionError(
            f"contact lookup failed: {result.stderr.strip() or 'unknown AppleScript error'}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
