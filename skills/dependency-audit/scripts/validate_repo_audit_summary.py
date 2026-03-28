#!/usr/bin/env python3
"""Structural validator for dependency-audit summary JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_TOP = {"repo_profile", "tool_coverage", "overall_verdict", "findings"}
REQUIRED_PROFILE = {"languages", "monorepo_shape", "package_managers"}
REQUIRED_TOOL_COVERAGE = {"chosen_tools", "skipped_tools"}
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
