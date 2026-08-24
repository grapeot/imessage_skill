from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from imessage_skill import __version__
from imessage_skill.applescript import (
    check_applescript,
    osascript_available,
    send_message,
)
from imessage_skill.contacts import ContactResolutionError, resolve_name
from imessage_skill.messages_db import (
    MessagesDbError,
    count_chats,
    count_history,
    count_search,
    default_db_path,
    iso_to_ns,
    list_chats,
    load_handles,
    match_handles,
    open_readonly,
    read_history,
    search_messages,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload, exit_code = args.func(args)
    except (UserFacingError, MessagesDbError, ContactResolutionError) as exc:
        payload = {"ok": False, "error": str(exc)}
        exit_code = 2

    emit(payload, args.format)
    return exit_code


class UserFacingError(Exception):
    pass


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer (>= 1)")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="imessage-send")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    send_parser = subparsers.add_parser("send", help="send an iMessage")
    send_parser.add_argument("--to", required=True, help="iMessage handle: Apple ID email or phone")
    body_group = send_parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="message body")
    body_group.add_argument("--body-file", type=Path, help="path to UTF-8 text body")
    mode_group = send_parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="print payload without sending")
    mode_group.add_argument("--confirm-send", action="store_true", help="send the iMessage for real")
    send_parser.add_argument("--timeout", type=int, default=30, help="osascript timeout in seconds")
    send_parser.add_argument("--format", choices=["json", "text"], default="text")
    send_parser.set_defaults(func=handle_send)

    read_parser = subparsers.add_parser(
        "read", help="read message history with a contact (requires --confirm-read for content)"
    )
    target_group = read_parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--to", help="contact handle: phone or email")
    target_group.add_argument("--name", help="contact display name (resolved via Contacts app)")
    _add_read_filters(read_parser)
    read_parser.set_defaults(func=handle_read)

    search_parser = subparsers.add_parser(
        "search", help="full-text search across message history (requires --confirm-read for content)"
    )
    search_parser.add_argument("--query", required=True, help="case-insensitive substring to search")
    _add_read_filters(search_parser, include_target=False)
    search_parser.set_defaults(func=handle_search)

    chats_parser = subparsers.add_parser(
        "chats", help="list recent conversations (requires --confirm-read for handles)"
    )
    chats_parser.add_argument("--limit", type=positive_int, default=20, help="max conversations to list (>= 1)")
    chats_parser.add_argument("--db", type=Path, default=None, help="path to chat.db")
    chats_parser.add_argument(
        "--confirm-read", action="store_true", help="actually read the local Messages database"
    )
    chats_parser.add_argument("--format", choices=["json", "text"], default="text")
    chats_parser.set_defaults(func=handle_chats)

    doctor_parser = subparsers.add_parser("doctor", help="diagnose local setup")
    doctor_subparsers = doctor_parser.add_subparsers(dest="doctor_command", required=True)
    applescript_parser = doctor_subparsers.add_parser("applescript", help="check Messages scripting")
    applescript_parser.add_argument("--timeout", type=int, default=15)
    applescript_parser.add_argument("--format", choices=["json", "text"], default="text")
    applescript_parser.set_defaults(func=handle_doctor_applescript)
    messages_parser = doctor_subparsers.add_parser("messages-db", help="check local Messages database")
    messages_parser.add_argument("--db", type=Path, default=None, help="path to chat.db")
    messages_parser.add_argument("--format", choices=["json", "text"], default="text")
    messages_parser.set_defaults(func=handle_doctor_messages_db)

    return parser


def _add_read_filters(parser: argparse.ArgumentParser, include_target: bool = True) -> None:
    if include_target:
        pass
    parser.add_argument("--since", help="start of time window (inclusive), ISO-8601 or YYYY-MM-DD")
    parser.add_argument("--until", help="end of time window (inclusive), ISO-8601 or YYYY-MM-DD")
    parser.add_argument("--limit", type=positive_int, default=50, help="max messages to return (>= 1)")
    parser.add_argument("--direction", choices=["in", "out", "all"], default="all")
    parser.add_argument("--db", type=Path, default=None, help="path to chat.db")
    parser.add_argument(
        "--confirm-read", action="store_true", help="actually read the local Messages database"
    )
    parser.add_argument("--format", choices=["json", "text"], default="text")


def open_db(args: argparse.Namespace):
    db_path = args.db or default_db_path()
    return open_readonly(db_path), db_path


def resolve_time_window(args: argparse.Namespace) -> tuple[int | None, int | None]:
    since_ns = iso_to_ns(args.since) if args.since else None
    until_ns = iso_to_ns(args.until) if args.until else None
    return since_ns, until_ns


def handle_send(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    message = load_message(args.body, args.body_file)
    handle = normalize_handle(args.to)

    if args.dry_run or not args.confirm_send:
        return {
            "ok": True,
            "dry_run": True,
            "would_send": True,
            "transport": "imessage",
            "to": handle,
            "body": message,
            "body_length": len(message),
        }, 0

    if not osascript_available():
        raise UserFacingError("osascript is not available on this system")

    result = send_message(handle, message, timeout=args.timeout)
    payload = {
        "ok": result.returncode == 0,
        "dry_run": False,
        "transport": "imessage",
        "to": handle,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    return payload, 0 if result.returncode == 0 else 1


def handle_read(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    conn, db_path = open_db(args)
    try:
        since_ns, until_ns = resolve_time_window(args)

        if args.to:
            handles = [args.to.strip()]
            name_used = None
        else:
            name_used = args.name
            handles = resolve_name(args.name)
            if not handles:
                raise UserFacingError(
                    f"no contact matching {args.name!r} found in Contacts; "
                    "try --to with a phone number or email"
                )

        all_handle_rows = load_handles(conn)
        matched: list[str] = []
        for h in handles:
            for row in match_handles(h, all_handle_rows):
                if row["id"] not in matched:
                    matched.append(row["id"])

        if not args.confirm_read:
            count = sum(count_history(conn, h, since_ns, until_ns, args.direction) for h in matched)
            return {
                "ok": True,
                "dry_run": True,
                "command": "read",
                "db": str(db_path),
                "resolved": {
                    "name": name_used,
                    "requested_handles": handles,
                    "matched_handles": matched,
                    "since": args.since,
                    "until": args.until,
                    "direction": args.direction,
                    "limit": args.limit,
                },
                "match_count": count,
                "hint": "re-run with --confirm-read to read message content",
            }, 0

        messages: list[dict[str, Any]] = []
        for h in matched:
            for rec in read_history(conn, h, since_ns, until_ns, args.limit, args.direction):
                messages.append(asdict(rec))
        # de-duplicate by guid (a handle can appear in multiple matched rows)
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for m in messages:
            if m["guid"] in seen:
                continue
            seen.add(m["guid"])
            deduped.append(m)
        deduped.sort(key=lambda m: m["date"] or "")
        deduped = deduped[: args.limit]

        return {
            "ok": True,
            "dry_run": False,
            "command": "read",
            "db": str(db_path),
            "resolved": {
                "name": name_used,
                "requested_handles": handles,
                "matched_handles": matched,
                "since": args.since,
                "until": args.until,
                "direction": args.direction,
                "limit": args.limit,
            },
            "count": len(deduped),
            "messages": deduped,
        }, 0
    finally:
        conn.close()


def handle_search(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    conn, db_path = open_db(args)
    try:
        since_ns, until_ns = resolve_time_window(args)

        if not args.confirm_read:
            count = count_search(conn, args.query, since_ns, until_ns, direction=args.direction)
            return {
                "ok": True,
                "dry_run": True,
                "command": "search",
                "db": str(db_path),
                "resolved": {
                    "query": args.query,
                    "since": args.since,
                    "until": args.until,
                    "limit": args.limit,
                    "direction": args.direction,
                },
                "match_count": count,
                "hint": "re-run with --confirm-read to read matching messages",
            }, 0

        records = search_messages(conn, args.query, since_ns, until_ns, args.limit, direction=args.direction)
        return {
            "ok": True,
            "dry_run": False,
            "command": "search",
            "db": str(db_path),
            "resolved": {
                "query": args.query,
                "since": args.since,
                "until": args.until,
                "limit": args.limit,
                "direction": args.direction,
            },
            "count": len(records),
            "messages": [asdict(r) for r in records],
        }, 0
    finally:
        conn.close()


def handle_chats(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    conn, db_path = open_db(args)
    try:
        if not args.confirm_read:
            return {
                "ok": True,
                "dry_run": True,
                "command": "chats",
                "db": str(db_path),
                "resolved": {"limit": args.limit},
                "chat_count": count_chats(conn),
                "hint": "re-run with --confirm-read to list conversations",
            }, 0

        chats = list_chats(conn, args.limit)
        return {
            "ok": True,
            "dry_run": False,
            "command": "chats",
            "db": str(db_path),
            "resolved": {"limit": args.limit},
            "count": len(chats),
            "chats": [asdict(c) for c in chats],
        }, 0
    finally:
        conn.close()


def handle_doctor_applescript(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if not osascript_available():
        return {"ok": False, "osascript_available": False}, 1

    result = check_applescript(timeout=args.timeout)
    account_count = parse_int(result.stdout)
    payload = {
        "ok": result.returncode == 0 and account_count is not None and account_count > 0,
        "osascript_available": True,
        "imessage_account_count": account_count,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    return payload, 0 if payload["ok"] else 1


def handle_doctor_messages_db(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    db_path = args.db or default_db_path()
    try:
        conn = open_readonly(db_path)
    except MessagesDbError as exc:
        return {"ok": False, "error": str(exc), "db": str(db_path)}, 1
    try:
        total = conn.execute("SELECT COUNT(*) FROM message").fetchone()[0]
        chats = count_chats(conn)
        return {
            "ok": True,
            "db": str(db_path),
            "message_count": total,
            "chat_count": chats,
        }, 0
    finally:
        conn.close()


def load_message(body: str | None, body_file: Path | None) -> str:
    if body_file is not None:
        try:
            body = body_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise UserFacingError(f"failed to read body file: {exc}") from exc

    if body is None:
        raise UserFacingError("message body is required")

    normalized = body.strip()
    if not normalized:
        raise UserFacingError("message body must not be empty")
    return normalized


def normalize_handle(handle: str) -> str:
    normalized = handle.strip()
    if not normalized:
        raise UserFacingError("recipient handle must not be empty")
    return normalized


def parse_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        return None


def emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if not payload.get("ok"):
        print(f"error: {payload.get('error') or 'unknown failure'}", file=sys.stderr)
        return

    if payload.get("command") == "read":
        _emit_read(payload)
    elif payload.get("command") == "search":
        _emit_search(payload)
    elif payload.get("command") == "chats":
        _emit_chats(payload)
    elif payload.get("dry_run"):
        print(f"dry-run: would send iMessage to {payload['to']}")
    else:
        print("sent iMessage")


def _emit_read(payload: dict[str, Any]) -> None:
    resolved = payload["resolved"]
    if payload.get("dry_run"):
        handles = ", ".join(resolved["matched_handles"]) or "(none matched in Messages DB)"
        window = _window_text(resolved)
        print(f"dry-run: {payload['match_count']} message(s) match {handles} {window}")
        print(payload["hint"])
        return
    window = _window_text(resolved)
    print(f"{payload['count']} message(s) {window}")
    for m in payload["messages"]:
        direction = "OUT" if m["is_from_me"] else "IN "
        service = f" [{m['service']}]" if m.get("service") else ""
        print(f"[{m['date']}] {direction} {m['handle']}{service}: {m['text']}")


def _emit_search(payload: dict[str, Any]) -> None:
    resolved = payload["resolved"]
    if payload.get("dry_run"):
        window = _window_text(resolved)
        print(f"dry-run: {payload['match_count']} message(s) match {resolved['query']!r} {window}")
        print(payload["hint"])
        return
    window = _window_text(resolved)
    print(f"{payload['count']} message(s) matching {resolved['query']!r} {window}")
    for m in payload["messages"]:
        direction = "OUT" if m["is_from_me"] else "IN "
        service = f" [{m['service']}]" if m.get("service") else ""
        print(f"[{m['date']}] {direction} {m['handle']}{service}: {m['text']}")


def _emit_chats(payload: dict[str, Any]) -> None:
    if payload.get("dry_run"):
        print(f"dry-run: {payload['chat_count']} conversation(s) in database")
        print(payload["hint"])
        return
    print(f"{payload['count']} conversation(s)")
    for c in payload["chats"]:
        name = f" {c['display_name']}" if c["display_name"] else ""
        service = f" [{c['service']}]" if c.get("service") else ""
        print(f"[{c['last_message_at']}] chat_id={c['chat_id']}{name}{service}: {', '.join(c['participants'])}")


def _window_text(resolved: dict[str, Any]) -> str:
    parts = []
    if resolved.get("since"):
        parts.append(f"since {resolved['since']}")
    if resolved.get("until"):
        parts.append(f"until {resolved['until']}")
    return f"({', '.join(parts)})" if parts else ""


if __name__ == "__main__":
    raise SystemExit(main())
