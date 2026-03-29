#!/usr/bin/env python3
"""Structural validator for contract-hardgate summary JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_TOP = {
    "repo_profile",
    "overall_verdict",
    "gate_states",
    "findings",
    "dependency_status",
    "bootstrap_actions",
    "dependency_failures",
}
REQUIRED_GATE = {"gate", "state", "severity", "confidence", "summary"}
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
    "domain",
    "gate",
    "severity",
    "confidence",
    "current_state",
    "target_state",
    "title",
    "evidence_summary",
    "decision",
    "change_shape",
    "validation",
    "merge_gate",
    "autofix_allowed",
}
VALID_DEPENDENCY_STATUS = {"ready", "auto-installed", "blocked"}


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    missing = REQUIRED_TOP - set(data)
    if missing:
        return fail(f"Missing top-level keys: {sorted(missing)}")

    dependency_status = data["dependency_status"]
    if dependency_status not in VALID_DEPENDENCY_STATUS:
        return fail(f"Unsupported dependency_status: {dependency_status}")

    if not isinstance(data["bootstrap_actions"], list):
        return fail("bootstrap_actions must be a list")
    for idx, action in enumerate(data["bootstrap_actions"]):
        if not isinstance(action, dict):
            return fail(f"bootstrap_actions[{idx}] must be an object")
        missing_action = REQUIRED_BOOTSTRAP_ACTION - set(action)
        if missing_action:
            return fail(f"bootstrap_actions[{idx}] missing keys: {sorted(missing_action)}")

    if not isinstance(data["dependency_failures"], list):
        return fail("dependency_failures must be a list")
    for idx, failure in enumerate(data["dependency_failures"]):
        if not isinstance(failure, dict):
            return fail(f"dependency_failures[{idx}] must be an object")
        missing_failure = REQUIRED_DEPENDENCY_FAILURE - set(failure)
        if missing_failure:
            return fail(f"dependency_failures[{idx}] missing keys: {sorted(missing_failure)}")

    if dependency_status == "blocked" and not data["dependency_failures"]:
        return fail("dependency_status=blocked requires at least one dependency_failure")

    if not isinstance(data["gate_states"], list):
        return fail("gate_states must be a list")
    for idx, gate in enumerate(data["gate_states"]):
        if not isinstance(gate, dict):
            return fail(f"gate_states[{idx}] must be an object")
        missing_gate = REQUIRED_GATE - set(gate)
        if missing_gate:
            return fail(f"gate_states[{idx}] missing keys: {sorted(missing_gate)}")

    if not isinstance(data["findings"], list):
        return fail("findings must be a list")
    for idx, finding in enumerate(data["findings"]):
        if not isinstance(finding, dict):
            return fail(f"findings[{idx}] must be an object")
        missing_finding = REQUIRED_FINDING - set(finding)
        if missing_finding:
            return fail(f"findings[{idx}] missing keys: {sorted(missing_finding)}")

    print(f"Validated {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
