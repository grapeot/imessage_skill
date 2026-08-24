from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from imessage_skill.messages_db import iso_to_ns


def _build_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE handle (id TEXT, uncanonicalized_id TEXT, service TEXT);
        CREATE TABLE message (
            guid TEXT, text TEXT, attributedBody BLOB, date INTEGER,
            is_from_me INTEGER, handle_id INTEGER, service TEXT, is_empty INTEGER
        );
        CREATE TABLE chat (chat_identifier TEXT, display_name TEXT, service_name TEXT);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        """
    )
    conn.execute(
        "INSERT INTO handle (id, uncanonicalized_id, service) VALUES (?, ?, ?)",
        ("+12064585315", "+12064585315", "iMessage"),
    )
    conn.execute(
        "INSERT INTO handle (id, uncanonicalized_id, service) VALUES (?, ?, ?)",
        ("alice@example.com", "alice@example.com", "iMessage"),
    )
    conn.execute(
        "INSERT INTO chat (chat_identifier, display_name, service_name) VALUES (?, ?, ?)",
        ("+12064585315", "", "iMessage"),
    )
    conn.execute(
        "INSERT INTO chat (chat_identifier, display_name, service_name) VALUES (?, ?, ?)",
        ("alice@example.com", "Alice", "iMessage"),
    )
    streamtyped = b"\x01\x2b" + b"\x05world" + b"\x86\x84"
    conn.execute(
        "INSERT INTO message (guid, text, attributedBody, date, is_from_me, handle_id, service, is_empty) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("g1", "hello there", None, iso_to_ns("2024-08-30T12:00:00+00:00"), 0, 1, "iMessage", 0),
    )
    conn.execute(
        "INSERT INTO message (guid, text, attributedBody, date, is_from_me, handle_id, service, is_empty) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("g2", None, streamtyped, iso_to_ns("2024-08-30T12:00:05+00:00"), 1, 1, "iMessage", 0),
    )
    conn.execute(
        "INSERT INTO message (guid, text, attributedBody, date, is_from_me, handle_id, service, is_empty) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("g3", "from alice", None, iso_to_ns("2024-09-01T08:00:00+00:00"), 0, 2, "iMessage", 0),
    )
    conn.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 1)")
    conn.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 2)")
    conn.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (2, 3)")
    conn.execute("INSERT INTO chat_handle_join (chat_id, handle_id) VALUES (1, 1)")
    conn.execute("INSERT INTO chat_handle_join (chat_id, handle_id) VALUES (2, 2)")
    conn.commit()
    conn.close()


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    path = tmp_path / "chat.db"
    _build_db(path)
    return path
