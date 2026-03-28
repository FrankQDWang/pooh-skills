#!/usr/bin/env python3
"""Minimal validator for repo-health summary JSON."""

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
    "overall_health",
    "coverage_status",
    "summary_line",
    "skill_runs",
}

REQUIRED_RUN = {"domain", "skill_name", "status", "summary_path", "severity_counts"}


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

    if data.get("skill") != "repo-health-orchestrator":
        print("Unexpected skill field", file=sys.stderr)
        return 2

    runs = data.get("skill_runs")
    if not isinstance(runs, list):
        print("skill_runs must be a list", file=sys.stderr)
        return 2

    for idx, run in enumerate(runs):
        miss = REQUIRED_RUN - set(run)
        if miss:
            print(f"skill_runs[{idx}] missing keys: {sorted(miss)}", file=sys.stderr)
            return 2

    print(f"Validated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
