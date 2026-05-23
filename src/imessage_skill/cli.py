from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from imessage_skill import __version__
from imessage_skill.applescript import (
    check_applescript,
    osascript_available,
    send_message,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload, exit_code = args.func(args)
    except UserFacingError as exc:
        payload = {"ok": False, "error": str(exc)}
        exit_code = 2

    emit(payload, args.format)
    return exit_code


class UserFacingError(Exception):
    pass


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

    doctor_parser = subparsers.add_parser("doctor", help="diagnose local setup")
    doctor_subparsers = doctor_parser.add_subparsers(dest="doctor_command", required=True)
    applescript_parser = doctor_subparsers.add_parser("applescript", help="check Messages scripting")
    applescript_parser.add_argument("--timeout", type=int, default=15)
    applescript_parser.add_argument("--format", choices=["json", "text"], default="text")
    applescript_parser.set_defaults(func=handle_doctor_applescript)

    return parser


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

    if payload.get("ok"):
        if payload.get("dry_run"):
            print(f"dry-run: would send iMessage to {payload['to']}")
        else:
            print("sent iMessage")
        return

    print(f"error: {payload.get('error') or payload.get('stderr') or 'unknown failure'}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
