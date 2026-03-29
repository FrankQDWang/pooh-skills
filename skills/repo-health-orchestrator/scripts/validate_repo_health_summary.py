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
    "dependency_status",
    "bootstrap_actions",
    "dependency_failures",
}

REQUIRED_RUN = {
    "domain",
    "skill_name",
    "status",
    "summary_path",
    "severity_counts",
    "dependency_status",
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

    if data.get("skill") != "repo-health-orchestrator":
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
        miss = REQUIRED_BOOTSTRAP_ACTION - set(action)
        if miss:
            print(f"bootstrap_actions[{idx}] missing keys: {sorted(miss)}", file=sys.stderr)
            return 2

    dependency_failures = data.get("dependency_failures")
    if not isinstance(dependency_failures, list):
        print("dependency_failures must be a list", file=sys.stderr)
        return 2
    for idx, failure in enumerate(dependency_failures):
        if not isinstance(failure, dict):
            print(f"dependency_failures[{idx}] must be an object", file=sys.stderr)
            return 2
        miss = REQUIRED_DEPENDENCY_FAILURE - set(failure)
        if miss:
            print(f"dependency_failures[{idx}] missing keys: {sorted(miss)}", file=sys.stderr)
            return 2

    if dependency_status == "blocked" and not dependency_failures:
        print("dependency_status=blocked requires at least one dependency_failure", file=sys.stderr)
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
        run_dependency_status = run.get("dependency_status")
        if run_dependency_status not in VALID_DEPENDENCY_STATUS:
            print(f"skill_runs[{idx}] has unsupported dependency_status: {run_dependency_status!r}", file=sys.stderr)
            return 2

    print(f"Validated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
