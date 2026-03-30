#!/usr/bin/env python3
"""Fail when cleanup findings contain expired or incomplete removal metadata."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check deprecation removal targets.")
    parser.add_argument("--summary", required=True, help="Path to controlled-cleanup summary JSON.")
    parser.add_argument("--today", default=dt.date.today().isoformat(), help="Override current date (YYYY-MM-DD).")
    parser.add_argument("--strict", action="store_true", help="Also fail on missing replacement or removal target metadata.")
    return parser.parse_args(argv)


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    summary_path = Path(args.summary)
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"error: could not read summary: {exc}", file=sys.stderr)
        return 2

    today = parse_date(args.today)
    if today is None:
        print("error: --today must be YYYY-MM-DD", file=sys.stderr)
        return 2

    expired = []
    incomplete = []

    for finding in payload.get("findings", []):
        category = finding.get("category")
        removal_target = finding.get("removal_target")
        replacement = finding.get("replacement")

        if category == "expired-removal-target":
            expired.append(finding)
            continue

        removal_date = parse_date(removal_target)
        if removal_date and removal_date < today:
            expired.append(finding)

        if args.strict and category in {"deprecated-surface", "compatibility-shim", "marker-gap"}:
            if not replacement or not removal_target:
                incomplete.append(finding)

    if expired:
        print(f"expired removal targets: {len(expired)}", file=sys.stderr)
    if incomplete:
        print(f"incomplete deprecation metadata: {len(incomplete)}", file=sys.stderr)

    return 1 if expired or incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
