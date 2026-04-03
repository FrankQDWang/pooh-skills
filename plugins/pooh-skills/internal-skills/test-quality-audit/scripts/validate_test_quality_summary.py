#!/usr/bin/env python3
"""Validate test-quality-audit summary JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_TOP = {
    "schema_version",
    "skill",
    "status",
    "verdict",
    "repo_scope",
    "summary",
    "summary_line",
    "coverage",
    "categories",
    "findings",
    "top_actions",
    "run_id",
    "generated_at",
    "repo_root",
    "overall_verdict",
    "rollup_bucket",
    "dependency_status",
    "dependency_failures",
    "bootstrap_actions",
    "severity_counts",
    "summary_path",
    "report_path",
    "agent_brief_path",
}
VALID_STATUS = {"complete", "blocked", "not-applicable"}
VALID_VERDICTS = {"scan-blocked", "watch", "clean", "not-applicable"}
VALID_CATEGORY_IDS = {
    "ci-test-gate",
    "placeholder-test-quality",
    "skip-retry-governance",
    "mock-discipline",
    "failure-path-evidence",
}
VALID_CATEGORY_STATES = {"clean", "watch", "blocked", "not-applicable"}
VALID_FINDING_CATEGORIES = {
    "missing-ci-gate",
    "placeholder-test",
    "skip-retry-sprawl",
    "internal-mock-drift",
    "missing-failure-path-evidence",
    "scan-blocker",
}
VALID_SEVERITY = {"critical", "high", "medium", "low"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_DEPENDENCY_STATUS = {"ready", "auto-installed", "blocked"}
VALID_ROLLUP_BUCKETS = {"blocked", "red", "yellow", "green", "not-applicable"}
REQUIRED_COVERAGE = {
    "source_files_detected",
    "test_files_scanned",
    "ci_configs_scanned",
    "foreign_runtime_source_files_excluded",
    "foreign_runtime_test_files_excluded",
    "ci_gate_hits",
    "placeholder_hits",
    "skip_retry_hits",
    "internal_mock_hits",
    "failure_path_hits",
    "surface_source",
}
VALID_SURFACE_SOURCES = {"git-index", "filesystem-fallback"}


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--summary":
        return fail("usage: validate_test_quality_summary.py --summary /path/to/summary.json")
    path = Path(sys.argv[2])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return fail(f"could not parse summary: {exc}")

    missing = REQUIRED_TOP - set(data)
    if missing:
        return fail(f"missing top-level keys: {sorted(missing)}")
    if data.get("skill") != "test-quality-audit":
        return fail("skill must be `test-quality-audit`")
    if data.get("status") not in VALID_STATUS:
        return fail(f"invalid status: {data.get('status')}")
    if data.get("verdict") not in VALID_VERDICTS:
        return fail(f"invalid verdict: {data.get('verdict')}")
    if data.get("overall_verdict") not in VALID_VERDICTS:
        return fail(f"invalid overall_verdict: {data.get('overall_verdict')}")
    if data.get("rollup_bucket") not in VALID_ROLLUP_BUCKETS:
        return fail(f"invalid rollup_bucket: {data.get('rollup_bucket')}")
    if data.get("dependency_status") not in VALID_DEPENDENCY_STATUS:
        return fail(f"invalid dependency_status: {data.get('dependency_status')}")

    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        return fail("coverage must be an object")
    missing_coverage = REQUIRED_COVERAGE - set(coverage)
    if missing_coverage:
        return fail(f"coverage missing keys: {sorted(missing_coverage)}")
    if coverage.get("surface_source") not in VALID_SURFACE_SOURCES:
        return fail(f"coverage.surface_source invalid: {coverage.get('surface_source')}")
    for key in (
        "source_files_detected",
        "test_files_scanned",
        "ci_configs_scanned",
        "foreign_runtime_source_files_excluded",
        "foreign_runtime_test_files_excluded",
        "ci_gate_hits",
        "placeholder_hits",
        "skip_retry_hits",
        "internal_mock_hits",
        "failure_path_hits",
    ):
        if not isinstance(coverage.get(key), int):
            return fail(f"coverage.{key} must be an integer")

    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        return fail("categories must be a non-empty list")
    seen_ids: set[str] = set()
    for idx, category in enumerate(categories):
        if not isinstance(category, dict):
            return fail(f"category #{idx} must be an object")
        category_id = category.get("id")
        if category_id not in VALID_CATEGORY_IDS:
            return fail(f"category #{idx} has invalid id: {category_id}")
        if category_id in seen_ids:
            return fail(f"duplicate category id: {category_id}")
        seen_ids.add(category_id)
        if category.get("state") not in VALID_CATEGORY_STATES:
            return fail(f"category {category_id} has invalid state: {category.get('state')}")
        if category.get("confidence") not in VALID_CONFIDENCE:
            return fail(f"category {category_id} has invalid confidence: {category.get('confidence')}")
        if not isinstance(category.get("evidence"), list):
            return fail(f"category {category_id} evidence must be a list")

    findings = data.get("findings")
    if not isinstance(findings, list):
        return fail("findings must be a list")
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            return fail(f"finding #{idx} must be an object")
        if finding.get("category") not in VALID_FINDING_CATEGORIES:
            return fail(f"finding #{idx} has invalid category: {finding.get('category')}")
        if finding.get("severity") not in VALID_SEVERITY:
            return fail(f"finding #{idx} has invalid severity: {finding.get('severity')}")
        if finding.get("confidence") not in VALID_CONFIDENCE:
            return fail(f"finding #{idx} has invalid confidence: {finding.get('confidence')}")
        for key in ("id", "title", "path", "evidence_summary", "recommended_change_shape"):
            if not isinstance(finding.get(key), str) or not str(finding.get(key)).strip():
                return fail(f"finding #{idx} missing non-empty string `{key}`")
        if not isinstance(finding.get("line"), int) or finding.get("line", 0) < 1:
            return fail(f"finding #{idx} must provide a positive integer line")

    severity_counts = data.get("severity_counts")
    if not isinstance(severity_counts, dict):
        return fail("severity_counts must be an object")
    for key in ("critical", "high", "medium", "low"):
        if not isinstance(severity_counts.get(key), int):
            return fail(f"severity_counts.{key} must be an integer")

    if not isinstance(data.get("top_actions"), list):
        return fail("top_actions must be a list")
    if not isinstance(data.get("bootstrap_actions"), list):
        return fail("bootstrap_actions must be a list")
    if not isinstance(data.get("dependency_failures"), list):
        return fail("dependency_failures must be a list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
