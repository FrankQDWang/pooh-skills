#!/usr/bin/env python3
"""Lightweight validation for the controlled cleanup summary JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REQUIRED_TOP_LEVEL = {
    "repo_root",
    "generated_at",
    "repo_profile",
    "counts",
    "findings",
    "dependency_status",
    "bootstrap_actions",
    "dependency_failures",
}
REQUIRED_FINDING_KEYS = {"category", "severity", "confidence", "path", "summary", "evidence"}
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
VALID_CATEGORIES = {
    "scan-blocker",
    "evidence-gap",
    "deprecated-surface",
    "compatibility-shim",
    "expired-removal-target",
    "marker-gap",
    "stale-doc-reference",
    "feature-flag-debt",
    "dynamic-entrypoint-risk",
    "cleanup-opportunity",
}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_DEPENDENCY_STATUS = {"ready", "auto-installed", "blocked"}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate controlled-cleanup summary JSON.")
    parser.add_argument("--summary", required=True, help="Path to JSON summary.")
    return parser.parse_args(argv)


def fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    path = Path(args.summary)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return fail(f"could not parse summary: {exc}")

    missing = REQUIRED_TOP_LEVEL - set(payload.keys())
    if missing:
        return fail(f"missing top-level keys: {sorted(missing)}")

    findings = payload.get("findings")
    if not isinstance(findings, list):
        return fail("findings must be a list")

    dependency_status = payload.get("dependency_status")
    if dependency_status not in VALID_DEPENDENCY_STATUS:
        return fail(f"invalid dependency_status: {dependency_status}")

    bootstrap_actions = payload.get("bootstrap_actions")
    if not isinstance(bootstrap_actions, list):
        return fail("bootstrap_actions must be a list")
    for idx, action in enumerate(bootstrap_actions):
        if not isinstance(action, dict):
            return fail(f"bootstrap_actions[{idx}] must be an object")
        missing_action = REQUIRED_BOOTSTRAP_ACTION - set(action)
        if missing_action:
            return fail(f"bootstrap_actions[{idx}] missing keys: {sorted(missing_action)}")

    dependency_failures = payload.get("dependency_failures")
    if not isinstance(dependency_failures, list):
        return fail("dependency_failures must be a list")
    for idx, failure in enumerate(dependency_failures):
        if not isinstance(failure, dict):
            return fail(f"dependency_failures[{idx}] must be an object")
        missing_failure = REQUIRED_DEPENDENCY_FAILURE - set(failure)
        if missing_failure:
            return fail(f"dependency_failures[{idx}] missing keys: {sorted(missing_failure)}")

    if dependency_status == "blocked" and not dependency_failures:
        return fail("dependency_status=blocked requires at least one dependency_failure")

    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            return fail(f"finding #{idx} is not an object")
        missing_keys = REQUIRED_FINDING_KEYS - set(finding.keys())
        if missing_keys:
            return fail(f"finding #{idx} missing keys: {sorted(missing_keys)}")
        if finding["category"] not in VALID_CATEGORIES:
            return fail(f"finding #{idx} has invalid category: {finding['category']}")
        if finding["severity"] not in VALID_SEVERITIES:
            return fail(f"finding #{idx} has invalid severity: {finding['severity']}")
        if finding["confidence"] not in VALID_CONFIDENCE:
            return fail(f"finding #{idx} has invalid confidence: {finding['confidence']}")
        if not isinstance(finding["evidence"], list):
            return fail(f"finding #{idx} evidence must be a list")

    counts = payload.get("counts")
    if not isinstance(counts, dict) or "total" not in counts or "by_category" not in counts:
        return fail("counts must contain total and by_category")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
