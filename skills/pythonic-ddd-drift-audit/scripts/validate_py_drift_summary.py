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
    "dependency_status",
    "bootstrap_actions",
    "dependency_failures",
}
REQUIRED_BOOTSTRAP_ACTION = {"name", "kind", "status", "command", "details"}
REQUIRED_DEPENDENCY_FAILURE = {
    "name",
    "kind",
    "required_for",
    "attempted_command",
    "failure_reason",
    "blocked_by_security",
    "blocked_by_permissions",
    "blocked_by_network",
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
VALID_DEPENDENCY_STATUS = {"ready", "auto-installed", "blocked"}


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

    dependency_status = data.get("dependency_status")
    if dependency_status not in VALID_DEPENDENCY_STATUS:
        print(f"Unsupported dependency_status: {dependency_status!r}", file=sys.stderr)
        return 2

    bootstrap_actions = data.get("bootstrap_actions")
    if not isinstance(bootstrap_actions, list):
        print("bootstrap_actions must be a list", file=sys.stderr)
        return 2
    for idx, action in enumerate(bootstrap_actions):
        if not isinstance(action, dict):
            print(f"bootstrap_actions[{idx}] must be an object", file=sys.stderr)
            return 2
        missing_action = REQUIRED_BOOTSTRAP_ACTION - set(action)
        if missing_action:
            print(f"bootstrap_actions[{idx}] missing keys: {sorted(missing_action)}", file=sys.stderr)
            return 2

    dependency_failures = data.get("dependency_failures")
    if not isinstance(dependency_failures, list):
        print("dependency_failures must be a list", file=sys.stderr)
        return 2
    for idx, failure in enumerate(dependency_failures):
        if not isinstance(failure, dict):
            print(f"dependency_failures[{idx}] must be an object", file=sys.stderr)
            return 2
        missing_failure = REQUIRED_DEPENDENCY_FAILURE - set(failure)
        if missing_failure:
            print(f"dependency_failures[{idx}] missing keys: {sorted(missing_failure)}", file=sys.stderr)
            return 2

    if dependency_status == "blocked" and not dependency_failures:
        print("dependency_status=blocked requires at least one dependency_failure", file=sys.stderr)
        return 2

    if not isinstance(data.get("findings"), list):
        print("findings must be a list", file=sys.stderr)
        return 2

    for idx, finding in enumerate(data["findings"]):
        if not isinstance(finding, dict):
            print(f"Finding #{idx} must be an object", file=sys.stderr)
            return 2
        missing_f = REQUIRED_FINDING - set(finding)
        if missing_f:
            print(f"Finding #{idx} missing keys: {sorted(missing_f)}", file=sys.stderr)
            return 2

    print(f"Validated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
