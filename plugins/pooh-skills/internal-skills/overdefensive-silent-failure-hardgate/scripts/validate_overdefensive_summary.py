#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_TOP = {
    "schema_version": str,
    "skill": str,
    "generated_at": str,
    "repo_root": str,
    "overall_verdict": str,
    "summary_line": str,
    "severity_counts": dict,
    "coverage": dict,
    "findings": list,
    "dependency_status": str,
    "bootstrap_actions": list,
    "dependency_failures": list,
}

REQUIRED_COVERAGE = {
    "files_scanned": int,
    "python_files": int,
    "ts_files": int,
    "js_files": int,
}

REQUIRED_SEVERITY = {
    "critical": int,
    "high": int,
    "medium": int,
    "low": int,
}

REQUIRED_FINDING = {
    "id": str,
    "category": str,
    "severity": str,
    "confidence": str,
    "language": str,
    "title": str,
    "path": str,
    "line": int,
    "evidence": list,
    "recommendation": str,
    "merge_gate": str,
}

ALLOWED_SKILL = "overdefensive-silent-failure-hardgate"
ALLOWED_VERDICTS = {
    "not-applicable",
    "scan-blocked",
    "silent-failure-risk",
    "contract-softened",
    "observable-degrade",
    "fail-loud",
}
ALLOWED_DEP_STATUS = {"ready", "auto-installed", "blocked"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate overdefensive summary JSON")
    parser.add_argument("--summary", required=True, help="Path to summary JSON")
    return parser.parse_args()


def fail(message: str) -> int:
    print(f"Validation failed: {message}", file=sys.stderr)
    return 1


def expect_type(obj: dict, key: str, expected: type) -> str | None:
    if key not in obj:
        return f"missing key `{key}`"
    if not isinstance(obj[key], expected):
        return f"key `{key}` expected {expected.__name__}, got {type(obj[key]).__name__}"
    return None


def main() -> int:
    args = parse_args()
    path = Path(args.summary)
    if not path.exists():
        return fail(f"file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"invalid JSON: {exc}")

    for key, typ in REQUIRED_TOP.items():
        msg = expect_type(data, key, typ)
        if msg:
            return fail(msg)

    if data["skill"] != ALLOWED_SKILL:
        return fail(f"skill must be `{ALLOWED_SKILL}`")

    if data["overall_verdict"] not in ALLOWED_VERDICTS:
        return fail(f"unexpected overall_verdict `{data['overall_verdict']}`")

    if data["dependency_status"] not in ALLOWED_DEP_STATUS:
        return fail(f"unexpected dependency_status `{data['dependency_status']}`")

    coverage = data["coverage"]
    for key, typ in REQUIRED_COVERAGE.items():
        msg = expect_type(coverage, key, typ)
        if msg:
            return fail(f"coverage: {msg}")

    severity = data["severity_counts"]
    for key, typ in REQUIRED_SEVERITY.items():
        msg = expect_type(severity, key, typ)
        if msg:
            return fail(f"severity_counts: {msg}")

    if not isinstance(data.get("scan_blockers", []), list):
        return fail("scan_blockers must be a list if present")

    for idx, finding in enumerate(data["findings"], start=1):
        if not isinstance(finding, dict):
            return fail(f"finding #{idx} must be an object")
        for key, typ in REQUIRED_FINDING.items():
            msg = expect_type(finding, key, typ)
            if msg:
                return fail(f"finding #{idx}: {msg}")
        if finding["severity"] not in {"critical", "high", "medium", "low"}:
            return fail(f"finding #{idx}: invalid severity `{finding['severity']}`")
        if finding["confidence"] not in {"high", "medium", "low"}:
            return fail(f"finding #{idx}: invalid confidence `{finding['confidence']}`")
        if finding["merge_gate"] not in {
            "block-now",
            "block-changed-files",
            "warn-only",
            "allow-with-explicit-contract",
            "unverified",
        }:
            return fail(f"finding #{idx}: invalid merge_gate `{finding['merge_gate']}`")

    print(f"Summary is valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
