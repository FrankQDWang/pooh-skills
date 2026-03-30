#!/usr/bin/env python3
"""Validate the machine-readable summary produced by error-governance-hardgate."""

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
    "coverage",
    "severity_counts",
    "gate_states",
    "findings",
    "top_actions",
    "dependency_status",
    "bootstrap_actions",
    "dependency_failures",
}
REQUIRED_COVERAGE = {
    "files_scanned",
    "relevant_files",
    "openapi_surfaces",
    "asyncapi_surfaces",
    "catalogs_found",
    "generated_type_surfaces",
}
REQUIRED_SEVERITY = {"critical", "high", "medium", "low"}
REQUIRED_GATE = {"name", "status", "summary"}
REQUIRED_FINDING = {
    "id",
    "category",
    "severity",
    "confidence",
    "scope",
    "title",
    "path",
    "line",
    "evidence_summary",
    "decision",
    "recommended_change_shape",
    "validation_checks",
    "merge_gate",
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
ALLOWED_VERDICTS = {"healthy", "watch", "blocked", "partial", "not-applicable"}
ALLOWED_GATE_STATUS = {"pass", "watch", "fail", "not-applicable", "unverified"}
ALLOWED_SEVERITY = {"critical", "high", "medium", "low"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_MERGE_GATE = {"block-now", "fix-before-release", "fix-next", "watch", "document-only"}
ALLOWED_DEPENDENCY_STATUS = {"ready", "auto-installed", "blocked"}


def fail(message: str) -> int:
    print(f"Validation failed: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate error-governance summary JSON")
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    path = Path(args.summary)
    if not path.exists():
        return fail(f"file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    missing = REQUIRED_TOP - set(data)
    if missing:
        return fail(f"missing top-level keys: {sorted(missing)}")

    if data.get("skill") != "error-governance-hardgate":
        return fail("skill must be `error-governance-hardgate`")
    if data.get("overall_verdict") not in ALLOWED_VERDICTS:
        return fail(f"unexpected overall_verdict `{data.get('overall_verdict')}`")
    if data.get("dependency_status") not in ALLOWED_DEPENDENCY_STATUS:
        return fail(f"unexpected dependency_status `{data.get('dependency_status')}`")

    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        return fail("coverage must be an object")
    missing_coverage = REQUIRED_COVERAGE - set(coverage)
    if missing_coverage:
        return fail(f"coverage missing keys: {sorted(missing_coverage)}")
    if not all(isinstance(coverage[key], int) for key in REQUIRED_COVERAGE):
        return fail("coverage values must all be integers")

    severity = data.get("severity_counts")
    if not isinstance(severity, dict):
        return fail("severity_counts must be an object")
    missing_severity = REQUIRED_SEVERITY - set(severity)
    if missing_severity:
        return fail(f"severity_counts missing keys: {sorted(missing_severity)}")
    if not all(isinstance(severity[key], int) for key in REQUIRED_SEVERITY):
        return fail("severity_counts values must all be integers")

    gate_states = data.get("gate_states")
    if not isinstance(gate_states, list) or not gate_states:
        return fail("gate_states must be a non-empty list")
    for idx, gate in enumerate(gate_states):
        if not isinstance(gate, dict):
            return fail(f"gate_states[{idx}] must be an object")
        missing_gate = REQUIRED_GATE - set(gate)
        if missing_gate:
            return fail(f"gate_states[{idx}] missing keys: {sorted(missing_gate)}")
        if gate.get("status") not in ALLOWED_GATE_STATUS:
            return fail(f"gate_states[{idx}] has invalid status `{gate.get('status')}`")

    findings = data.get("findings")
    if not isinstance(findings, list):
        return fail("findings must be a list")
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            return fail(f"findings[{idx}] must be an object")
        missing_finding = REQUIRED_FINDING - set(finding)
        if missing_finding:
            return fail(f"findings[{idx}] missing keys: {sorted(missing_finding)}")
        if finding.get("severity") not in ALLOWED_SEVERITY:
            return fail(f"findings[{idx}] has invalid severity `{finding.get('severity')}`")
        if finding.get("confidence") not in ALLOWED_CONFIDENCE:
            return fail(f"findings[{idx}] has invalid confidence `{finding.get('confidence')}`")
        if finding.get("merge_gate") not in ALLOWED_MERGE_GATE:
            return fail(f"findings[{idx}] has invalid merge_gate `{finding.get('merge_gate')}`")
        if not isinstance(finding.get("validation_checks"), list):
            return fail(f"findings[{idx}].validation_checks must be a list")

    if not isinstance(data.get("top_actions"), list):
        return fail("top_actions must be a list")

    bootstrap_actions = data.get("bootstrap_actions")
    if not isinstance(bootstrap_actions, list):
        return fail("bootstrap_actions must be a list")
    for idx, action in enumerate(bootstrap_actions):
        if not isinstance(action, dict):
            return fail(f"bootstrap_actions[{idx}] must be an object")
        missing_action = REQUIRED_BOOTSTRAP_ACTION - set(action)
        if missing_action:
            return fail(f"bootstrap_actions[{idx}] missing keys: {sorted(missing_action)}")

    dependency_failures = data.get("dependency_failures")
    if not isinstance(dependency_failures, list):
        return fail("dependency_failures must be a list")
    for idx, failure in enumerate(dependency_failures):
        if not isinstance(failure, dict):
            return fail(f"dependency_failures[{idx}] must be an object")
        missing_failure = REQUIRED_DEPENDENCY_FAILURE - set(failure)
        if missing_failure:
            return fail(f"dependency_failures[{idx}] missing keys: {sorted(missing_failure)}")

    if data.get("dependency_status") == "blocked" and not dependency_failures:
        return fail("dependency_status=blocked requires at least one dependency_failure")

    print(f"Validated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
