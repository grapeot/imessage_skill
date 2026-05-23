from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from imessage_skill.cli import main


pytestmark = pytest.mark.live_integration


def test_send_live_imessage_to_configured_handle(capsys: pytest.CaptureFixture[str]) -> None:
    if os.environ.get("IMESSAGE_LOAD_DOTENV") == "1":
        load_dotenv_if_present()

    if os.environ.get("IMESSAGE_ENABLE_LIVE_TESTS") != "1":
        pytest.skip("set IMESSAGE_ENABLE_LIVE_TESTS=1 to enable live iMessage tests")
    if os.environ.get("IMESSAGE_LIVE_ALLOW_SEND") != "1":
        pytest.skip("set IMESSAGE_LIVE_ALLOW_SEND=1 to allow real outbound iMessage")

    target = os.environ.get("IMESSAGE_LIVE_TO")
    if not target:
        pytest.skip("set IMESSAGE_LIVE_TO to a private iMessage handle")

    message = os.environ.get("IMESSAGE_LIVE_MESSAGE") or f"iMessage skill live test {uuid4()}"

    exit_code = main([
        "send",
        "--to",
        target,
        "--body",
        message,
        "--confirm-send",
        "--format",
        "json",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.out + captured.err


def load_dotenv_if_present() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
