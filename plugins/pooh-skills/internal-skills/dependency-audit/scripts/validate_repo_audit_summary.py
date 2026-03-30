#!/usr/bin/env python3
"""Structural validator for dependency-audit summary JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_TOP = {
    "repo_profile",
    "tool_coverage",
    "overall_verdict",
    "findings",
    "dependency_status",
    "bootstrap_actions",
    "dependency_failures",
}
REQUIRED_PROFILE = {"languages", "monorepo_shape", "package_managers"}
REQUIRED_TOOL_COVERAGE = {"chosen_tools", "skipped_tools"}
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
    "tool",
    "category",
    "severity",
    "confidence",
    "scope",
    "title",
    "evidence_summary",
    "decision",
    "recommended_change_shape",
    "validation_checks",
    "autofix_allowed",
}

VALID_VERDICTS = {
    "scan-blocked",
    "baseline-needed",
    "cleanup-first",
    "boundary-hardening",
    "incremental-governance",
    "well-governed",
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

    profile = data["repo_profile"]
    if not isinstance(profile, dict):
        return fail("repo_profile must be an object")
    missing_profile = REQUIRED_PROFILE - set(profile)
    if missing_profile:
        return fail(f"Missing repo_profile keys: {sorted(missing_profile)}")

    tool_coverage = data["tool_coverage"]
    if not isinstance(tool_coverage, dict):
        return fail("tool_coverage must be an object")
    missing_tools = REQUIRED_TOOL_COVERAGE - set(tool_coverage)
    if missing_tools:
        return fail(f"Missing tool_coverage keys: {sorted(missing_tools)}")

    if data["overall_verdict"] not in VALID_VERDICTS:
        return fail(f"Unsupported overall_verdict: {data['overall_verdict']}")

    dependency_status = data["dependency_status"]
    if dependency_status not in VALID_DEPENDENCY_STATUS:
        return fail(f"Unsupported dependency_status: {dependency_status}")

    bootstrap_actions = data["bootstrap_actions"]
    if not isinstance(bootstrap_actions, list):
        return fail("bootstrap_actions must be a list")
    for idx, action in enumerate(bootstrap_actions):
        if not isinstance(action, dict):
            return fail(f"bootstrap_actions[{idx}] must be an object")
        missing_action = REQUIRED_BOOTSTRAP_ACTION - set(action)
        if missing_action:
            return fail(f"bootstrap_actions[{idx}] missing keys: {sorted(missing_action)}")

    dependency_failures = data["dependency_failures"]
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

    findings = data["findings"]
    if not isinstance(findings, list):
        return fail("findings must be a list")
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            return fail(f"finding[{idx}] must be an object")
        missing_finding = REQUIRED_FINDING - set(finding)
        if missing_finding:
            return fail(f"finding[{idx}] missing keys: {sorted(missing_finding)}")

    print(f"Validated {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
