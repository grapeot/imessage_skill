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


def test_read_dry_run(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    exit_code = main([
        "read",
        "--to",
        "+12064585315",
        "--db",
        str(sample_db),
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["match_count"] == 2
    assert "messages" not in payload


def test_read_confirm(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    exit_code = main([
        "read",
        "--to",
        "+12064585315",
        "--db",
        str(sample_db),
        "--confirm-read",
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["dry_run"] is False
    assert payload["count"] == 2
    assert [m["text"] for m in payload["messages"]] == ["hello there", "world"]


def test_read_direction(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    exit_code = main([
        "read",
        "--to",
        "+12064585315",
        "--db",
        str(sample_db),
        "--direction",
        "out",
        "--confirm-read",
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["count"] == 1
    assert payload["messages"][0]["text"] == "world"


def test_read_name_no_contact(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sample_db: Path,
) -> None:
    monkeypatch.setattr("imessage_skill.cli.resolve_name", lambda name, **kw: [])
    exit_code = main([
        "read",
        "--name",
        "Nobody",
        "--db",
        str(sample_db),
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    # No matching contact -> clean error, no crash, and no DB read attempted.
    assert exit_code == 2
    assert payload["ok"] is False
    assert "no contact" in str(payload["error"])


def test_search_dry_run(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    exit_code = main([
        "search",
        "--query",
        "alice",
        "--db",
        str(sample_db),
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["match_count"] == 1
    assert "messages" not in payload


def test_search_confirm(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    exit_code = main([
        "search",
        "--query",
        "alice",
        "--db",
        str(sample_db),
        "--confirm-read",
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["dry_run"] is False
    assert payload["count"] == 1
    assert payload["messages"][0]["text"] == "from alice"


def test_chats_dry_run(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    exit_code = main([
        "chats",
        "--db",
        str(sample_db),
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["chat_count"] == 2


def test_chats_confirm(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    exit_code = main([
        "chats",
        "--db",
        str(sample_db),
        "--confirm-read",
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["dry_run"] is False
    assert payload["count"] == 2
    assert {c["chat_id"] for c in payload["chats"]} == {1, 2}


def test_read_negative_limit_rejected(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([
            "read",
            "--to",
            "+12064585315",
            "--db",
            str(sample_db),
            "--limit",
            "-1",
            "--format",
            "json",
        ])
    assert exc_info.value.code == 2


def test_read_zero_limit_rejected(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([
            "read",
            "--to",
            "+12064585315",
            "--db",
            str(sample_db),
            "--limit",
            "0",
            "--format",
            "json",
        ])
    assert exc_info.value.code == 2


def test_search_direction_out(capsys: pytest.CaptureFixture[str], sample_db: Path) -> None:
    exit_code = main([
        "search",
        "--query",
        "world",
        "--db",
        str(sample_db),
        "--direction",
        "out",
        "--confirm-read",
        "--format",
        "json",
    ])
    payload = read_json(capsys)
    assert exit_code == 0
    assert payload["count"] == 1
    assert payload["messages"][0]["text"] == "world"
    assert payload["resolved"]["direction"] == "out"


def test_read_missing_db_errors(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    exit_code = main([
        "read",
        "--to",
        "+12064585315",
        "--db",
        str(tmp_path / "missing.db"),
        "--format",
        "json",
    ])

    payload = read_json(capsys)
    assert exit_code == 2
    assert payload["ok"] is False
