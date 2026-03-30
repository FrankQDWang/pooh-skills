#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ALLOWED_VERDICTS = {"scan-blocked", "not-applicable", "split-before-merge", "sprawling", "contained", "disciplined"}
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}
ALLOWED_CATEGORIES = {
    "scan-blocker",
    "oversized-file",
    "long-function",
    "hub-module",
    "mixed-responsibility",
    "export-surface-sprawl",
    "duplication-cluster",
    "god-module",
}
ALLOWED_GATES = {"block-now", "block-changed-files", "warn-only", "unverified"}
ALLOWED_DECISIONS = {"fix-scan", "split", "extract", "narrow", "separate", "deduplicate", "baseline", "defer"}


def fail(message: str) -> int:
    print(f"invalid summary: {message}", file=sys.stderr)
    return 1


def require_keys(obj: dict, keys: list[str], context: str) -> str | None:
    for key in keys:
        if key not in obj:
            return f"{context} missing required key: {key}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate module-shape-hardgate summary JSON.")
    parser.add_argument("--summary", required=True, help="Path to summary JSON.")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.exists():
        return fail(f"file not found: {summary_path}")

    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"JSON parse error: {exc}")

    err = require_keys(
        data,
        [
            "schema_version",
            "skill",
            "generated_at",
            "repo_root",
            "repo_profile",
            "threshold_profile",
            "overall_verdict",
            "summary_line",
            "coverage",
            "severity_counts",
            "findings",
            "dependency_status",
            "bootstrap_actions",
            "dependency_failures",
        ],
        "root",
    )
    if err:
        return fail(err)

    if data["skill"] != "module-shape-hardgate":
        return fail("skill must be module-shape-hardgate")
    if data["overall_verdict"] not in ALLOWED_VERDICTS:
        return fail("unexpected overall_verdict")
    if not isinstance(data["findings"], list):
        return fail("findings must be a list")

    for key in ("critical", "high", "medium", "low"):
        if key not in data["severity_counts"] or not isinstance(data["severity_counts"][key], int):
            return fail(f"severity_counts.{key} must be an integer")

    for idx, finding in enumerate(data["findings"]):
        err = require_keys(
            finding,
            [
                "id",
                "category",
                "severity",
                "confidence",
                "title",
                "path",
                "line",
                "evidence_summary",
                "recommendation",
                "merge_gate",
                "decision",
                "metrics",
            ],
            f"finding[{idx}]",
        )
        if err:
            return fail(err)
        if finding["category"] not in ALLOWED_CATEGORIES:
            return fail(f"finding[{idx}].category invalid")
        if finding["severity"] not in ALLOWED_SEVERITIES:
            return fail(f"finding[{idx}].severity invalid")
        if finding["merge_gate"] not in ALLOWED_GATES:
            return fail(f"finding[{idx}].merge_gate invalid")
        if finding["decision"] not in ALLOWED_DECISIONS:
            return fail(f"finding[{idx}].decision invalid")
        if not isinstance(finding["line"], int) or finding["line"] < 1:
            return fail(f"finding[{idx}].line must be a positive integer")

    print("module-shape-hardgate summary is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
