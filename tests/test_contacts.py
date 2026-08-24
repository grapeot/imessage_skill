from __future__ import annotations

import subprocess

import pytest

from imessage_skill import contacts as c
from imessage_skill.contacts import ContactResolutionError, resolve_name


class FakeRunner:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self._stdout = stdout
        self._returncode = returncode
        self._stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        return subprocess.CompletedProcess(
            args=command, returncode=self._returncode, stdout=self._stdout, stderr=self._stderr
        )


@pytest.fixture
def always_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "osascript_available", lambda: True)


def test_resolve_name_returns_handles(always_available) -> None:
    runner = FakeRunner("+15555550123\nalice@example.com\n")
    result = resolve_name("Alice", runner=runner)
    assert result == ["+15555550123", "alice@example.com"]
    assert runner.calls[0][0] == "osascript"


def test_resolve_name_strips_blank_lines(always_available) -> None:
    runner = FakeRunner("\n  \n+15555550123\n")
    assert resolve_name("Alice", runner=runner) == ["+15555550123"]


def test_resolve_name_empty_query_raises() -> None:
    with pytest.raises(ContactResolutionError):
        resolve_name("   ", runner=FakeRunner(""))


def test_resolve_name_failure_raises(always_available) -> None:
    runner = FakeRunner("", returncode=1, stderr="error: something")
    with pytest.raises(ContactResolutionError, match="contact lookup failed"):
        resolve_name("Alice", runner=runner)


def test_resolve_name_no_matches_returns_empty(always_available) -> None:
    runner = FakeRunner("")
    assert resolve_name("Nobody", runner=runner) == []
