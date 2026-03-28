#!/usr/bin/env python3
"""Minimal validator for pythonic-ddd-drift summary JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_TOP = {
    "schema_version",
    "skill",
    "generated_at",
    "repo_root",
    "overall_verdict",
    "summary_line",
    "severity_counts",
    "coverage",
    "findings",
}

REQUIRED_FINDING = {
    "id",
    "category",
    "severity",
    "confidence",
    "title",
    "path",
    "line",
    "evidence",
    "recommendation",
    "merge_gate",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    path = Path(args.summary)
    data = json.loads(path.read_text(encoding="utf-8"))

    missing = REQUIRED_TOP - set(data)
    if missing:
        print(f"Missing top-level keys: {sorted(missing)}", file=sys.stderr)
        return 2

    if data.get("skill") != "pythonic-ddd-drift-audit":
        print("Unexpected skill field", file=sys.stderr)
        return 2

    if not isinstance(data.get("findings"), list):
        print("findings must be a list", file=sys.stderr)
        return 2

    for idx, finding in enumerate(data["findings"]):
        missing_f = REQUIRED_FINDING - set(finding)
        if missing_f:
            print(f"Finding #{idx} missing keys: {sorted(missing_f)}", file=sys.stderr)
            return 2

    print(f"Validated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
