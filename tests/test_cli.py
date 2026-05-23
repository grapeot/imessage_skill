from __future__ import annotations

import json
from pathlib import Path

import pytest

from imessage_skill.cli import main


def read_json(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    captured = capsys.readouterr()
    return json.loads(captured.out)


def test_send_dry_run_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([
        "send",
        "--to",
        " alice@example.com ",
        "--body",
        " hello ",
        "--dry-run",
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["to"] == "alice@example.com"
    assert payload["body"] == "hello"


def test_send_defaults_to_dry_run_without_confirm(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["send", "--to", "alice@example.com", "--body", "hello", "--format", "json"])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["dry_run"] is True


def test_send_body_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text("hello from file\n", encoding="utf-8")

    exit_code = main([
        "send",
        "--to",
        "alice@example.com",
        "--body-file",
        str(body_file),
        "--dry-run",
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["body"] == "hello from file"


def test_empty_body_returns_error(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([
        "send",
        "--to",
        "alice@example.com",
        "--body",
        "  ",
        "--dry-run",
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 2
    assert payload["ok"] is False
    assert "body" in str(payload["error"])
