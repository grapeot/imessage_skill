from __future__ import annotations

import pytest

from imessage_skill import messages_db as mdb


def test_ns_iso_roundtrip() -> None:
    ns = mdb.iso_to_ns("2024-08-30T12:00:00+00:00")
    back = mdb.ns_to_iso(ns)
    assert back is not None
    assert back.startswith("2024-08-30T12:00:00")


def test_ns_to_iso_none() -> None:
    assert mdb.ns_to_iso(None) is None


def test_iso_to_ns_invalid_raises() -> None:
    with pytest.raises(mdb.MessagesDbError):
        mdb.iso_to_ns("not-a-date")


def test_iso_to_ns_date_only() -> None:
    ns = mdb.iso_to_ns("2024-08-30")
    back = mdb.ns_to_iso(ns)
    assert back is not None
    assert back.startswith("2024-08-30")


def test_parse_attribution_body_utf16_bom() -> None:
    blob = b"\xff\xfe" + "hello".encode("utf-16-le")
    assert mdb.parse_attribution_body(blob) == "hello"


def test_parse_attribution_body_streamtyped_single_byte_len() -> None:
    blob = b"\x01\x2b" + b"\x05world" + b"\x86\x84"
    assert mdb.parse_attribution_body(blob) == "world"


def test_parse_attribution_body_streamtyped_two_byte_len() -> None:
    blob = b"\x01\x2b" + b"\x81\x05world" + b"\x86\x84"
    assert mdb.parse_attribution_body(blob) == "world"


def test_parse_attribution_body_utf8_fallback() -> None:
    assert mdb.parse_attribution_body(b"just plain text") == "just plain text"


def test_parse_attribution_body_empty() -> None:
    assert mdb.parse_attribution_body(None) == ""
    assert mdb.parse_attribution_body(b"") == ""


def test_match_handles_us_aware(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        handles = mdb.load_handles(conn)
        matched = mdb.match_handles("(206) 458-5315", handles)
        assert any(r["id"] == "+12064585315" for r in matched)
    finally:
        conn.close()


def test_match_handles_exact_email(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        handles = mdb.load_handles(conn)
        matched = mdb.match_handles("alice@example.com", handles)
        assert any(r["id"] == "alice@example.com" for r in matched)
    finally:
        conn.close()


def test_match_handles_no_match(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        handles = mdb.load_handles(conn)
        assert mdb.match_handles("+19999999999", handles) == []
    finally:
        conn.close()


def test_read_history_all(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        recs = mdb.read_history(conn, "+12064585315")
        assert [r.text for r in recs] == ["hello there", "world"]
        assert [r.is_from_me for r in recs] == [False, True]
    finally:
        conn.close()


def test_read_history_direction(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        incoming = mdb.read_history(conn, "+12064585315", direction="in")
        outgoing = mdb.read_history(conn, "+12064585315", direction="out")
        assert [r.text for r in incoming] == ["hello there"]
        assert [r.text for r in outgoing] == ["world"]
    finally:
        conn.close()


def test_read_history_email_handle(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        recs = mdb.read_history(conn, "alice@example.com")
        assert [r.text for r in recs] == ["from alice"]
    finally:
        conn.close()


def test_read_history_time_window(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        since = mdb.iso_to_ns("2024-09-01")
        recs = mdb.read_history(conn, "+12064585315", since_ns=since)
        assert recs == []
        until = mdb.iso_to_ns("2024-08-30T12:00:03+00:00")
        recs2 = mdb.read_history(conn, "+12064585315", until_ns=until)
        assert [r.text for r in recs2] == ["hello there"]
    finally:
        conn.close()


def test_count_history(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        assert mdb.count_history(conn, "+12064585315") == 2
        assert mdb.count_history(conn, "+12064585315", direction="in") == 1
        assert mdb.count_history(conn, "+12064585315", direction="out") == 1
    finally:
        conn.close()


def test_search_messages(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        recs = mdb.search_messages(conn, "alice")
        assert [r.text for r in recs] == ["from alice"]
        assert mdb.count_search(conn, "alice") == 1
    finally:
        conn.close()


def test_search_messages_case_insensitive(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        recs = mdb.search_messages(conn, "HELLO THERE")
        assert [r.text for r in recs] == ["hello there"]
    finally:
        conn.close()


def test_search_empty_query_raises(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        with pytest.raises(mdb.MessagesDbError):
            mdb.search_messages(conn, "   ")
    finally:
        conn.close()


def test_search_respects_time_window(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        # m1 "hello there" is a plain-text row on 2024-08-30; a since=2024-09-01
        # window must exclude it (regression: time clause used to bind only to the
        # attributedBody branch due to OR/AND precedence).
        since = mdb.iso_to_ns("2024-09-01")
        assert mdb.count_search(conn, "hello", since_ns=since) == 0
        # m3 "from alice" is on 2024-09-01; an until=2024-08-31 window excludes it.
        until = mdb.iso_to_ns("2024-08-31")
        assert mdb.count_search(conn, "alice", until_ns=until) == 0
        # No window: both match.
        assert mdb.count_search(conn, "hello") == 1
        assert mdb.count_search(conn, "alice") == 1
    finally:
        conn.close()


def test_search_direction_filter(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        # m1 "hello there" is incoming (is_from_me=0).
        assert [r.text for r in mdb.search_messages(conn, "hello", direction="in")] == ["hello there"]
        assert mdb.search_messages(conn, "hello", direction="out") == []
        # m2 "world" is outgoing (is_from_me=1).
        assert [r.text for r in mdb.search_messages(conn, "world", direction="out")] == ["world"]
        assert mdb.count_search(conn, "world", direction="in") == 0
    finally:
        conn.close()


def test_list_chats(sample_db) -> None:
    conn = mdb.open_readonly(sample_db)
    try:
        chats = mdb.list_chats(conn)
        assert len(chats) == 2
        ids = {c.chat_id for c in chats}
        assert ids == {1, 2}
        assert mdb.count_chats(conn) == 2
    finally:
        conn.close()


def test_open_readonly_missing_path(tmp_path) -> None:
    with pytest.raises(mdb.MessagesDbError):
        mdb.open_readonly(tmp_path / "nope.db")
