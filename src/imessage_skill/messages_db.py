from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

_START_MARKER = b"\x01\x2b"
_END_MARKER = b"\x86\x84"


class MessagesDbError(Exception):
    pass


@dataclass(frozen=True)
class MessageRecord:
    guid: str
    date: str | None
    is_from_me: bool
    handle: str | None
    service: str | None
    text: str
    chat_id: int | None
    chat_identifier: str | None


@dataclass(frozen=True)
class ChatRecord:
    chat_id: int
    identifier: str
    display_name: str
    service: str | None
    participants: tuple[str, ...]
    last_message_at: str | None


def default_db_path() -> Path:
    return Path.home() / "Library" / "Messages" / "chat.db"


def open_readonly(path: str | Path) -> sqlite3.Connection:
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise MessagesDbError(f"Messages database not found: {resolved}")
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def ns_to_iso(ns: int | float | None) -> str | None:
    if ns is None:
        return None
    return (APPLE_EPOCH + timedelta(microseconds=int(ns) // 1000)).isoformat()


def iso_to_ns(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MessagesDbError(f"invalid date {value!r}; use ISO-8601 or YYYY-MM-DD") from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return int((parsed - APPLE_EPOCH).total_seconds() * 1_000_000_000)


def _trim_leading_control(text: str) -> str:
    index = 0
    while index < len(text):
        code = ord(text[index])
        if code < 0x20 or 0x7F <= code <= 0x9F:
            index += 1
        else:
            break
    return text[index:]


def _find_sequence(needle: bytes, haystack: bytes, start: int) -> int | None:
    if start < 0 or start >= len(haystack):
        return None
    limit = len(haystack) - len(needle)
    if limit < start:
        return None
    index = start
    while index <= limit:
        if haystack[index : index + len(needle)] == needle:
            return index
        index += 1
    return None


def _decode_segment(segment: bytes) -> str:
    if not segment:
        return ""
    first = segment[0]
    structured_prefixes: list[int] = []
    if first < 0x80 and first == len(segment) - 1:
        structured_prefixes.append(1)
    if first == 0x81 and len(segment) >= 2:
        structured_prefixes.append(2)
    if first == 0x82 and len(segment) >= 3:
        structured_prefixes.append(3)

    best_structured = ""
    any_structured_valid = False
    for prefix_len in structured_prefixes:
        body = segment[prefix_len:]
        try:
            candidate = _trim_leading_control(body.decode("utf-8"))
        except UnicodeDecodeError:
            continue
        any_structured_valid = True
        if len(candidate) > len(best_structured):
            best_structured = candidate
    if any_structured_valid:
        return best_structured

    try:
        return _trim_leading_control(segment.decode("utf-8"))
    except UnicodeDecodeError:
        return ""


def parse_attribution_body(data: bytes | None) -> str:
    """Decode an attributedBody BLOB (Apple typedstream / NSKeyedArchiver payload).

    Port of imsg's TypedStreamParser: UTF-16LE BOM fast path, then
    0x01 0x2B ... 0x86 0x84 marker segments with BER-style length prefixes,
    then a lossy UTF-8 fallback.
    """
    if not data:
        return ""
    if len(data) >= 2 and data[0] == 0xFF and data[1] == 0xFE:
        try:
            return _trim_leading_control(data[2:].decode("utf-16-le"))
        except UnicodeDecodeError:
            pass
    best = ""
    index = 0
    while index + 1 < len(data):
        if data[index : index + 2] == _START_MARKER:
            slice_start = index + 2
            slice_end = _find_sequence(_END_MARKER, data, slice_start)
            if slice_end is not None:
                candidate = _decode_segment(data[slice_start:slice_end])
                if len(candidate) > len(best):
                    best = candidate
        index += 1
    if best:
        return best
    return _trim_leading_control(data.decode("utf-8", errors="replace"))


def extract_text(row: sqlite3.Row) -> str:
    text = row["text"]
    if text:
        return text
    return parse_attribution_body(row["attributedBody"])


def load_handles(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT ROWID, id, uncanonicalized_id, service FROM handle").fetchall()


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _us_digit_form(digits: str) -> str:
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def match_handles(query: str, handles: list[sqlite3.Row]) -> list[sqlite3.Row]:
    """Match a query (phone or email) against handle rows.

    Phone matching is digit-based and US-aware: an 11-digit number with a
    leading 1 is compared against its 10-digit form, so "(206) 458-5315"
    matches "+12064585315".
    """
    q = query.strip().lower()
    if q.startswith("tel:"):
        q = q[4:]
    q_digits = _us_digit_form(_digits(q))
    matched: list[sqlite3.Row] = []
    for row in handles:
        for field in (row["id"], row["uncanonicalized_id"]):
            if not field:
                continue
            if field.lower() == q:
                matched.append(row)
                break
            if q_digits and _us_digit_form(_digits(field)) == q_digits:
                matched.append(row)
                break
    return matched


def find_chats_for_handle(
    conn: sqlite3.Connection, handle: str, limit: int = 50
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT c.ROWID AS chat_id, c.chat_identifier, c.display_name, c.service_name,
               (SELECT MAX(m.date) FROM chat_message_join cmj
                JOIN message m ON m.ROWID = cmj.message_id
                WHERE cmj.chat_id = c.ROWID) AS last_date
        FROM chat c
        WHERE c.ROWID IN (
            SELECT chj.chat_id FROM chat_handle_join chj
            JOIN handle h ON h.ROWID = chj.handle_id
            WHERE h.id = ? OR h.uncanonicalized_id = ?
        )
        ORDER BY last_date DESC
        LIMIT ?
        """,
        (handle, handle, limit),
    ).fetchall()


def _time_clause(since_ns: int | None, until_ns: int | None) -> tuple[str, list[int]]:
    parts: list[str] = []
    params: list[int] = []
    if since_ns is not None:
        parts.append("m.date >= ?")
        params.append(since_ns)
    if until_ns is not None:
        parts.append("m.date <= ?")
        params.append(until_ns)
    clause = (" AND " + " AND ".join(parts)) if parts else ""
    return clause, params


def _direction_clause(direction: str) -> str:
    if direction == "in":
        return " AND m.is_from_me = 0"
    if direction == "out":
        return " AND m.is_from_me = 1"
    return ""


def _message_row_to_record(row: sqlite3.Row) -> MessageRecord:
    return MessageRecord(
        guid=row["guid"],
        date=ns_to_iso(row["date"]),
        is_from_me=bool(row["is_from_me"]),
        handle=row["handle"],
        service=row["service"],
        text=extract_text(row),
        chat_id=row["chat_id"],
        chat_identifier=row["chat_identifier"],
    )


_MESSAGE_COLUMNS = """
    m.guid, m.date, m.is_from_me, m.service, m.text, m.attributedBody,
    h.id AS handle, c.ROWID AS chat_id, c.chat_identifier
"""


def read_history(
    conn: sqlite3.Connection,
    handle: str,
    since_ns: int | None = None,
    until_ns: int | None = None,
    limit: int = 50,
    direction: str = "all",
) -> list[MessageRecord]:
    clause, params = _time_clause(since_ns, until_ns)
    sql = f"""
        SELECT {_MESSAGE_COLUMNS}
        FROM message m
        JOIN handle h ON h.ROWID = m.handle_id
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        JOIN chat c ON c.ROWID = cmj.chat_id
        WHERE (h.id = ? OR h.uncanonicalized_id = ?)
        {clause}
        {_direction_clause(direction)}
        ORDER BY m.date ASC
        LIMIT ?
    """
    rows = conn.execute(sql, [handle, handle, *params, limit]).fetchall()
    records = [_message_row_to_record(r) for r in rows]
    return [r for r in records if r.text]


def count_history(
    conn: sqlite3.Connection,
    handle: str,
    since_ns: int | None = None,
    until_ns: int | None = None,
    direction: str = "all",
) -> int:
    clause, params = _time_clause(since_ns, until_ns)
    sql = f"""
        SELECT COUNT(*) AS n
        FROM message m
        JOIN handle h ON h.ROWID = m.handle_id
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        JOIN chat c ON c.ROWID = cmj.chat_id
        WHERE (h.id = ? OR h.uncanonicalized_id = ?)
        {clause}
        {_direction_clause(direction)}
    """
    return conn.execute(sql, [handle, handle, *params]).fetchone()["n"]


def _iter_candidate_rows(
    conn: sqlite3.Connection,
    since_ns: int | None,
    until_ns: int | None,
    direction: str = "all",
) -> Iterator[sqlite3.Row]:
    clause, params = _time_clause(since_ns, until_ns)
    sql = f"""
        SELECT {_MESSAGE_COLUMNS}
        FROM message m
        LEFT JOIN handle h ON h.ROWID = m.handle_id
        LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        LEFT JOIN chat c ON c.ROWID = cmj.chat_id
        WHERE ((m.text IS NOT NULL AND m.text != '')
           OR (m.attributedBody IS NOT NULL AND m.is_empty = 0))
        {clause}
        {_direction_clause(direction)}
        ORDER BY m.date ASC
    """
    yield from conn.execute(sql, params)


def search_messages(
    conn: sqlite3.Connection,
    query: str,
    since_ns: int | None = None,
    until_ns: int | None = None,
    limit: int = 50,
    direction: str = "all",
) -> list[MessageRecord]:
    needle = query.strip().lower()
    if not needle:
        raise MessagesDbError("search query must not be empty")
    results: list[MessageRecord] = []
    for row in _iter_candidate_rows(conn, since_ns, until_ns, direction):
        record = _message_row_to_record(row)
        if needle in record.text.lower():
            results.append(record)
            if len(results) >= limit:
                break
    return results


def count_search(
    conn: sqlite3.Connection,
    query: str,
    since_ns: int | None = None,
    until_ns: int | None = None,
    direction: str = "all",
) -> int:
    needle = query.strip().lower()
    if not needle:
        raise MessagesDbError("search query must not be empty")
    count = 0
    for row in _iter_candidate_rows(conn, since_ns, until_ns, direction):
        if needle in extract_text(row).lower():
            count += 1
    return count


def list_chats(conn: sqlite3.Connection, limit: int = 20) -> list[ChatRecord]:
    chats = conn.execute(
        """
        SELECT c.ROWID AS chat_id, c.chat_identifier, c.display_name, c.service_name,
               (SELECT MAX(m.date) FROM chat_message_join cmj
                JOIN message m ON m.ROWID = cmj.message_id
                WHERE cmj.chat_id = c.ROWID) AS last_date
        FROM chat c
        WHERE last_date IS NOT NULL
        ORDER BY last_date DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    records: list[ChatRecord] = []
    for chat in chats:
        participants = tuple(
            row[0]
            for row in conn.execute(
                """
                SELECT h.id FROM chat_handle_join chj
                JOIN handle h ON h.ROWID = chj.handle_id
                WHERE chj.chat_id = ?
                ORDER BY h.id
                """,
                (chat["chat_id"],),
            )
        )
        records.append(
            ChatRecord(
                chat_id=chat["chat_id"],
                identifier=chat["chat_identifier"] or str(chat["chat_id"]),
                display_name=chat["display_name"] or "",
                service=chat["service_name"],
                participants=participants,
                last_message_at=ns_to_iso(chat["last_date"]),
            )
        )
    return records


def count_chats(conn: sqlite3.Connection) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) AS n FROM chat c
        WHERE (SELECT MAX(m.date) FROM chat_message_join cmj
               JOIN message m ON m.ROWID = cmj.message_id
               WHERE cmj.chat_id = c.ROWID) IS NOT NULL
        """
    ).fetchone()["n"]
