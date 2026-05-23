from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol


SEND_SCRIPT = """
on run {targetHandle, targetMessage}
  tell application "Messages"
    set targetAccount to first account whose service type = iMessage
    set targetParticipant to participant targetHandle of targetAccount
    send targetMessage to targetParticipant
  end tell
end run
""".strip()

DOCTOR_SCRIPT = """
tell application "Messages"
  set imAccounts to accounts whose service type = iMessage
  return count of imAccounts
end tell
""".strip()


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def __call__(self, command: list[str], timeout: int) -> CommandResult:
        """Run a command and return captured output."""
        ...


def subprocess_runner(command: list[str], timeout: int) -> CommandResult:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )


def build_send_command(handle: str, message: str) -> list[str]:
    return ["osascript", "-e", SEND_SCRIPT, handle, message]


def build_doctor_command() -> list[str]:
    return ["osascript", "-e", DOCTOR_SCRIPT]


def osascript_available() -> bool:
    return shutil.which("osascript") is not None


def send_message(
    handle: str,
    message: str,
    *,
    runner: Runner = subprocess_runner,
    timeout: int = 30,
) -> CommandResult:
    return runner(build_send_command(handle, message), timeout)


def check_applescript(
    *,
    runner: Runner = subprocess_runner,
    timeout: int = 15,
) -> CommandResult:
    return runner(build_doctor_command(), timeout)
