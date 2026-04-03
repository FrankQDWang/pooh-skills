#!/usr/bin/env python3
"""Validate llm-api-freshness-summary.json for the family-first contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ALLOWED_AUDIT_MODES = {"verified", "triage", "blocked", "not-applicable"}
ALLOWED_TARGET_SCOPE = {"repo", "diff", "file", "snippet"}
ALLOWED_RESOLUTION_LEVELS = {
    "provider-resolved",
    "family-resolved",
    "wrapper-resolved",
    "ambiguous",
}
ALLOWED_FAMILIES = {
    "openai-compatible",
    "anthropic-messages",
    "google-genai",
    "bedrock-hosted",
    "generic-wrapper",
    "custom-http-llm",
    "unknown",
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}
ALLOWED_DEPENDENCY_STATUS = {"ready", "auto-installed", "blocked"}
ALLOWED_ROLLUP_BUCKETS = {"blocked", "red", "yellow", "green", "not-applicable"}
ALLOWED_FINDING_KINDS = {
    "stale-surface",
    "deprecated-surface",
    "wrapper-provider-mismatch",
    "gateway-resolution-gap",
    "provider-ambiguous",
    "docs-unverified",
    "legacy-suspicion",
}
ALLOWED_VERIFICATION_STATUS = {"verified", "triage-only", "not-run", "blocked", "ambiguous"}
ALLOWED_DOC_STATUSES = {"verified", "ambiguous", "failed", "skipped"}
REQUIRED_TOP = {
    "run_id",
    "skill",
    "domain",
    "version",
    "generated_at",
    "audit_mode",
    "overall_verdict",
    "rollup_bucket",
    "target_scope",
    "repo_profile",
    "surface_resolution",
    "doc_verification",
    "findings",
    "priorities",
    "scan_limitations",
    "dependency_status",
    "bootstrap_actions",
    "dependency_failures",
    "summary_path",
    "report_path",
    "agent_brief_path",
}
REQUIRED_REPO_PROFILE = {
    "repo_root",
    "files_scanned",
    "languages",
    "package_managers",
    "surface_count",
    "wrapper_count",
    "provider_count",
}
REQUIRED_SURFACE = {
    "surface_id",
    "surface_family",
    "provider",
    "wrapper",
    "resolution_level",
    "confidence",
    "language",
    "primary_sdk",
    "version_hints",
    "model_hints",
    "base_url_hints",
    "evidence",
}
REQUIRED_DOC_ENTRY = {
    "surface_id",
    "surface_family",
    "provider",
    "wrapper",
    "library",
    "library_id",
    "language",
    "queries",
    "status",
    "checked_at",
    "source_ref",
    "notes",
}
REQUIRED_FINDING = {
    "id",
    "surface_id",
    "severity",
    "kind",
    "resolution_level",
    "surface_family",
    "provider",
    "wrapper",
    "title",
    "current_behavior",
    "current_expectation",
    "verification_status",
    "recommended_change_shape",
    "evidence",
}
REQUIRED_PRIORITIES = {"now", "next", "later"}
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


def add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def expect_type(value: Any, expected: type | tuple[type, ...], path: str, errors: list[str]) -> bool:
    if not isinstance(value, expected):
        add_error(errors, f"{path}: expected {expected}, got {type(value).__name__}")
        return False
    return True


def expect_keys(obj: dict[str, Any], required: Iterable[str], path: str, errors: list[str]) -> None:
    missing = [key for key in required if key not in obj]
    for key in missing:
        add_error(errors, f"{path}: missing required key '{key}'")


def validate_string_list(value: Any, path: str, errors: list[str]) -> None:
    if not expect_type(value, list, path, errors):
        return
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            add_error(errors, f"{path}[{idx}]: expected string")


def validate_evidence_list(value: Any, path: str, errors: list[str]) -> None:
    if not expect_type(value, list, path, errors):
        return
    for idx, item in enumerate(value):
        item_path = f"{path}[{idx}]"
        if not expect_type(item, dict, item_path, errors):
            continue
        expect_keys(item, {"path", "line", "snippet"}, item_path, errors)
        if "path" in item and not isinstance(item["path"], str):
            add_error(errors, f"{item_path}.path: expected string")
        if "line" in item and not isinstance(item["line"], int):
            add_error(errors, f"{item_path}.line: expected integer")
        if "snippet" in item and not isinstance(item["snippet"], str):
            add_error(errors, f"{item_path}.snippet: expected string")


def validate_repo_profile(value: Any, errors: list[str]) -> None:
    path = "repo_profile"
    if not expect_type(value, dict, path, errors):
        return
    expect_keys(value, REQUIRED_REPO_PROFILE, path, errors)
    for key in ("languages", "package_managers"):
        if key in value:
            validate_string_list(value[key], f"{path}.{key}", errors)
    for key in ("files_scanned", "surface_count", "wrapper_count", "provider_count"):
        if key in value and not isinstance(value[key], int):
            add_error(errors, f"{path}.{key}: expected integer")


def validate_surfaces(entries: Any, errors: list[str]) -> set[str]:
    path = "surface_resolution"
    surface_ids: set[str] = set()
    if not expect_type(entries, list, path, errors):
        return surface_ids
    for idx, entry in enumerate(entries):
        entry_path = f"{path}[{idx}]"
        if not expect_type(entry, dict, entry_path, errors):
            continue
        expect_keys(entry, REQUIRED_SURFACE, entry_path, errors)
        surface_id = entry.get("surface_id")
        if isinstance(surface_id, str):
            surface_ids.add(surface_id)
        else:
            add_error(errors, f"{entry_path}.surface_id: expected string")
        level = entry.get("resolution_level")
        if level not in ALLOWED_RESOLUTION_LEVELS:
            add_error(errors, f"{entry_path}.resolution_level: invalid value {level!r}")
        family = entry.get("surface_family")
        if family not in ALLOWED_FAMILIES:
            add_error(errors, f"{entry_path}.surface_family: invalid value {family!r}")
        confidence = entry.get("confidence")
        if confidence not in ALLOWED_CONFIDENCE:
            add_error(errors, f"{entry_path}.confidence: invalid value {confidence!r}")
        for key in ("version_hints", "model_hints", "base_url_hints"):
            if key in entry:
                validate_string_list(entry[key], f"{entry_path}.{key}", errors)
        if "evidence" in entry:
            validate_evidence_list(entry["evidence"], f"{entry_path}.evidence", errors)
        for key in ("provider", "wrapper"):
            if key in entry and entry[key] is not None and not isinstance(entry[key], str):
                add_error(errors, f"{entry_path}.{key}: expected string or null")
    return surface_ids


def validate_doc_verification(entries: Any, surface_ids: set[str], errors: list[str]) -> None:
    path = "doc_verification"
    if not expect_type(entries, list, path, errors):
        return
    for idx, entry in enumerate(entries):
        entry_path = f"{path}[{idx}]"
        if not expect_type(entry, dict, entry_path, errors):
            continue
        expect_keys(entry, REQUIRED_DOC_ENTRY, entry_path, errors)
        if entry.get("status") not in ALLOWED_DOC_STATUSES:
            add_error(errors, f"{entry_path}.status: invalid value {entry.get('status')!r}")
        if isinstance(entry.get("surface_id"), str) and surface_ids and entry["surface_id"] not in surface_ids:
            add_error(errors, f"{entry_path}.surface_id: unknown surface_id {entry['surface_id']!r}")
        if "queries" in entry:
            validate_string_list(entry["queries"], f"{entry_path}.queries", errors)
        for key in ("provider", "wrapper"):
            if key in entry and entry[key] is not None and not isinstance(entry[key], str):
                add_error(errors, f"{entry_path}.{key}: expected string or null")


def validate_findings(entries: Any, surface_ids: set[str], audit_mode: str, errors: list[str]) -> None:
    path = "findings"
    if not expect_type(entries, list, path, errors):
        return
    for idx, entry in enumerate(entries):
        entry_path = f"{path}[{idx}]"
        if not expect_type(entry, dict, entry_path, errors):
            continue
        expect_keys(entry, REQUIRED_FINDING, entry_path, errors)
        if entry.get("kind") not in ALLOWED_FINDING_KINDS:
            add_error(errors, f"{entry_path}.kind: invalid value {entry.get('kind')!r}")
        severity = entry.get("severity")
        if severity not in ALLOWED_SEVERITIES:
            add_error(errors, f"{entry_path}.severity: invalid value {severity!r}")
        if entry.get("resolution_level") not in ALLOWED_RESOLUTION_LEVELS:
            add_error(errors, f"{entry_path}.resolution_level: invalid value {entry.get('resolution_level')!r}")
        if entry.get("surface_family") not in ALLOWED_FAMILIES:
            add_error(errors, f"{entry_path}.surface_family: invalid value {entry.get('surface_family')!r}")
        if entry.get("verification_status") not in ALLOWED_VERIFICATION_STATUS:
            add_error(errors, f"{entry_path}.verification_status: invalid value {entry.get('verification_status')!r}")
        if isinstance(entry.get("surface_id"), str) and surface_ids and entry["surface_id"] not in surface_ids:
            add_error(errors, f"{entry_path}.surface_id: unknown surface_id {entry['surface_id']!r}")
        if "evidence" in entry:
            validate_evidence_list(entry["evidence"], f"{entry_path}.evidence", errors)
        for key in ("provider", "wrapper"):
            if key in entry and entry[key] is not None and not isinstance(entry[key], str):
                add_error(errors, f"{entry_path}.{key}: expected string or null")

        if audit_mode == "triage" and severity in {"critical", "high", "medium"}:
            add_error(errors, f"{entry_path}.severity: triage findings may not exceed 'low'")
        if entry.get("resolution_level") == "family-resolved" and severity in {"critical", "high"}:
            add_error(errors, f"{entry_path}.severity: family-resolved findings may not exceed 'medium'")
        if severity in {"critical", "high"} and entry.get("verification_status") != "verified":
            add_error(errors, f"{entry_path}.verification_status: high-severity findings require verified docs")
        if audit_mode == "verified" and entry.get("verification_status") == "not-run":
            add_error(errors, f"{entry_path}.verification_status: verified audit may not contain not-run findings")


def validate_priorities(value: Any, errors: list[str]) -> None:
    path = "priorities"
    if not expect_type(value, dict, path, errors):
        return
    expect_keys(value, REQUIRED_PRIORITIES, path, errors)
    for key in REQUIRED_PRIORITIES:
        if key in value:
            validate_string_list(value[key], f"{path}.{key}", errors)


def validate_bootstrap_actions(value: Any, errors: list[str]) -> None:
    path = "bootstrap_actions"
    if not expect_type(value, list, path, errors):
        return
    for idx, entry in enumerate(value):
        entry_path = f"{path}[{idx}]"
        if not expect_type(entry, dict, entry_path, errors):
            continue
        expect_keys(entry, REQUIRED_BOOTSTRAP_ACTION, entry_path, errors)


def validate_dependency_failures(value: Any, errors: list[str]) -> None:
    path = "dependency_failures"
    if not expect_type(value, list, path, errors):
        return
    for idx, entry in enumerate(value):
        entry_path = f"{path}[{idx}]"
        if not expect_type(entry, dict, entry_path, errors):
            continue
        expect_keys(entry, REQUIRED_DEPENDENCY_FAILURE, entry_path, errors)


def validate_summary(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expect_keys(data, REQUIRED_TOP, "summary", errors)
    if data.get("skill") != "llm-api-freshness-guard":
        add_error(errors, "summary.skill: must be 'llm-api-freshness-guard'")
    audit_mode = data.get("audit_mode")
    if audit_mode not in ALLOWED_AUDIT_MODES:
        add_error(errors, f"summary.audit_mode: invalid value {audit_mode!r}")
    if data.get("overall_verdict") != audit_mode:
        add_error(errors, "summary.overall_verdict must equal summary.audit_mode")
    if data.get("rollup_bucket") not in ALLOWED_ROLLUP_BUCKETS:
        add_error(errors, f"summary.rollup_bucket: invalid value {data.get('rollup_bucket')!r}")
    target_scope = data.get("target_scope")
    if target_scope not in ALLOWED_TARGET_SCOPE:
        add_error(errors, f"summary.target_scope: invalid value {target_scope!r}")
    dependency_status = data.get("dependency_status")
    if dependency_status not in ALLOWED_DEPENDENCY_STATUS:
        add_error(errors, f"summary.dependency_status: invalid value {dependency_status!r}")

    validate_repo_profile(data.get("repo_profile"), errors)
    surface_ids = validate_surfaces(data.get("surface_resolution"), errors)
    validate_doc_verification(data.get("doc_verification"), surface_ids, errors)
    validate_findings(data.get("findings"), surface_ids, str(audit_mode or ""), errors)
    validate_priorities(data.get("priorities"), errors)
    validate_string_list(data.get("scan_limitations"), "scan_limitations", errors)
    validate_bootstrap_actions(data.get("bootstrap_actions"), errors)
    validate_dependency_failures(data.get("dependency_failures"), errors)

    if dependency_status == "blocked" and not data.get("dependency_failures"):
        add_error(errors, "summary.dependency_status=blocked requires at least one dependency_failure")
    if audit_mode == "blocked" and dependency_status != "blocked":
        add_error(errors, "summary.audit_mode='blocked' requires dependency_status='blocked'")
    if audit_mode == "verified":
        doc_entries = data.get("doc_verification")
        if not isinstance(doc_entries, list) or not any(isinstance(entry, dict) and entry.get("status") == "verified" for entry in doc_entries):
            add_error(errors, "summary.audit_mode='verified' requires at least one doc_verification entry with status='verified'")
    if audit_mode == "not-applicable" and data.get("surface_resolution"):
        add_error(errors, "summary.audit_mode='not-applicable' should not contain surface_resolution entries")
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate llm-api-freshness-summary.json")
    parser.add_argument("summary_json", nargs="?", help="Path to the summary JSON")
    parser.add_argument("--summary", dest="summary_flag", help="Path to the summary JSON")
    args = parser.parse_args(argv)
    summary_path = args.summary_flag or args.summary_json
    if not summary_path:
        parser.error("summary path is required")

    path = Path(summary_path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_summary(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    print(f"Validated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
