#!/usr/bin/env python3
"""Validate llm-api-freshness-summary.json produced by the skill.

This is a lightweight validator that checks the shape used by the skill's summary
schema without requiring external dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, List

ALLOWED_MODES = {"verified", "local-scan-only"}
ALLOWED_FINDING_KINDS = {
    "scan-blocker",
    "provider-ambiguous",
    "docs-unverified",
    "local-suspicion",
    "sdk-stale",
    "endpoint-stale",
    "request-schema-drift",
    "response-shape-drift",
    "tool-calling-drift",
    "streaming-drift",
    "structured-output-drift",
    "model-stale",
    "auth-config-drift",
    "compat-layer-drift",
    "wrapper-pass-through-risk",
}
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_STATUS = {"present", "possible", "unknown"}
ALLOWED_DOC_STATUSES = {"verified", "ambiguous", "failed", "skipped"}
STRICT_VERIFIED_FORBIDDEN_KINDS = {
    "scan-blocker",
    "provider-ambiguous",
    "docs-unverified",
    "local-suspicion",
}
STRICT_VERIFIED_FORBIDDEN_LIMITATION_SNIPPETS = (
    "not verified",
    "unverified",
    "local signal collector only",
    "local-scan-only",
)


def add_error(errors: List[str], message: str) -> None:
    errors.append(message)


def expect_type(value: Any, expected_type: type | tuple[type, ...], path: str, errors: List[str]) -> bool:
    if not isinstance(value, expected_type):
        add_error(errors, f"{path}: expected {expected_type}, got {type(value).__name__}")
        return False
    return True


def expect_keys(obj: dict, required: Iterable[str], path: str, errors: List[str]) -> None:
    missing = [key for key in required if key not in obj]
    for key in missing:
        add_error(errors, f"{path}: missing required key '{key}'")


def validate_string_list(value: Any, path: str, errors: List[str]) -> None:
    if not expect_type(value, list, path, errors):
        return
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            add_error(errors, f"{path}[{idx}]: expected string, got {type(item).__name__}")


def validate_evidence_list(value: Any, path: str, errors: List[str]) -> None:
    if not expect_type(value, list, path, errors):
        return
    for idx, item in enumerate(value):
        item_path = f"{path}[{idx}]"
        if not expect_type(item, dict, item_path, errors):
            continue
        expect_keys(item, ["path", "line", "snippet"], item_path, errors)
        if "path" in item and not isinstance(item["path"], str):
            add_error(errors, f"{item_path}.path: expected string")
        if "line" in item and not isinstance(item["line"], int):
            add_error(errors, f"{item_path}.line: expected integer")
        if "snippet" in item and not isinstance(item["snippet"], str):
            add_error(errors, f"{item_path}.snippet: expected string")


def validate_doc_verification(entries: Any, errors: List[str]) -> None:
    if not expect_type(entries, list, "doc_verification", errors):
        return
    for idx, entry in enumerate(entries):
        path = f"doc_verification[{idx}]"
        if not expect_type(entry, dict, path, errors):
            continue
        expect_keys(entry, ["provider", "library", "library_id", "language", "version_hint", "queries", "status", "notes"], path, errors)
        if "status" in entry and entry["status"] not in ALLOWED_DOC_STATUSES:
            add_error(errors, f"{path}.status: invalid value {entry['status']!r}")
        if "queries" in entry:
            validate_string_list(entry["queries"], f"{path}.queries", errors)


def validate_findings(entries: Any, errors: List[str]) -> None:
    if not expect_type(entries, list, "findings", errors):
        return
    for idx, entry in enumerate(entries):
        path = f"findings[{idx}]"
        if not expect_type(entry, dict, path, errors):
            continue
        expect_keys(
            entry,
            [
                "id",
                "provider",
                "kind",
                "severity",
                "confidence",
                "status",
                "scope",
                "title",
                "stale_usage",
                "current_expectation",
                "evidence",
                "recommended_change_shape",
                "docs_verified",
                "autofix_allowed",
                "notes",
            ],
            path,
            errors,
        )
        if "kind" in entry and entry["kind"] not in ALLOWED_FINDING_KINDS:
            add_error(errors, f"{path}.kind: invalid value {entry['kind']!r}")
        if "severity" in entry and entry["severity"] not in ALLOWED_SEVERITIES:
            add_error(errors, f"{path}.severity: invalid value {entry['severity']!r}")
        if "confidence" in entry and entry["confidence"] not in ALLOWED_CONFIDENCE:
            add_error(errors, f"{path}.confidence: invalid value {entry['confidence']!r}")
        if "status" in entry and entry["status"] not in ALLOWED_STATUS:
            add_error(errors, f"{path}.status: invalid value {entry['status']!r}")
        if "scope" in entry:
            validate_string_list(entry["scope"], f"{path}.scope", errors)
        if "evidence" in entry:
            validate_evidence_list(entry["evidence"], f"{path}.evidence", errors)
        if "docs_verified" in entry and not isinstance(entry["docs_verified"], bool):
            add_error(errors, f"{path}.docs_verified: expected boolean")
        if "autofix_allowed" in entry and not isinstance(entry["autofix_allowed"], bool):
            add_error(errors, f"{path}.autofix_allowed: expected boolean")


def validate_repo_profile(profile: Any, errors: List[str]) -> None:
    path = "repo_profile"
    if not expect_type(profile, dict, path, errors):
        return
    expect_keys(
        profile,
        [
            "repo_root",
            "files_scanned",
            "languages",
            "providers_detected",
            "provider_scores",
            "wrappers_detected",
            "version_hints",
            "model_hints",
            "base_url_hints",
        ],
        path,
        errors,
    )
    if "files_scanned" in profile and not isinstance(profile["files_scanned"], int):
        add_error(errors, "repo_profile.files_scanned: expected integer")
    for key in ["languages", "providers_detected", "wrappers_detected"]:
        if key in profile:
            validate_string_list(profile[key], f"repo_profile.{key}", errors)
    for key in ["provider_scores", "version_hints", "model_hints", "base_url_hints"]:
        if key in profile and not isinstance(profile[key], dict):
            add_error(errors, f"repo_profile.{key}: expected object")
        elif key in profile:
            for sub_key, sub_value in profile[key].items():
                if not isinstance(sub_key, str):
                    add_error(errors, f"repo_profile.{key}: non-string key encountered")
                if key == "provider_scores":
                    if not isinstance(sub_value, int):
                        add_error(errors, f"repo_profile.provider_scores[{sub_key!r}]: expected integer")
                else:
                    validate_string_list(sub_value, f"repo_profile.{key}[{sub_key!r}]", errors)


def validate_priorities(value: Any, errors: List[str]) -> None:
    path = "priorities"
    if not expect_type(value, dict, path, errors):
        return
    expect_keys(value, ["now", "next", "later"], path, errors)
    for key in ["now", "next", "later"]:
        if key in value:
            validate_string_list(value[key], f"priorities.{key}", errors)


def validate_verified_contract(data: dict, errors: List[str]) -> None:
    if data.get("mode") != "verified":
        return

    doc_verification = data.get("doc_verification")
    if not isinstance(doc_verification, list) or not doc_verification:
        add_error(errors, "summary.mode=verified requires a non-empty doc_verification array")
    elif not any(isinstance(entry, dict) and entry.get("status") == "verified" for entry in doc_verification):
        add_error(errors, "summary.mode=verified requires at least one doc_verification entry with status='verified'")

    findings = data.get("findings")
    if isinstance(findings, list):
        for idx, finding in enumerate(findings):
            if not isinstance(finding, dict):
                continue
            kind = finding.get("kind")
            if kind in STRICT_VERIFIED_FORBIDDEN_KINDS:
                add_error(errors, f"findings[{idx}].kind: {kind!r} is not allowed when summary.mode='verified'")
            if finding.get("docs_verified") is not True:
                add_error(errors, f"findings[{idx}].docs_verified: must be true when summary.mode='verified'")

    scan_limitations = data.get("scan_limitations")
    if isinstance(scan_limitations, list):
        for idx, item in enumerate(scan_limitations):
            if not isinstance(item, str):
                continue
            lowered = item.lower()
            if any(snippet in lowered for snippet in STRICT_VERIFIED_FORBIDDEN_LIMITATION_SNIPPETS):
                add_error(
                    errors,
                    f"scan_limitations[{idx}]: incompatible with summary.mode='verified' because it still describes unverified docs",
                )


def validate_summary(data: Any) -> List[str]:
    errors: List[str] = []
    if not expect_type(data, dict, "summary", errors):
        return errors
    expect_keys(
        data,
        ["skill", "version", "generated_at", "mode", "repo_profile", "doc_verification", "findings", "priorities", "scan_limitations"],
        "summary",
        errors,
    )
    if data.get("skill") != "llm-api-freshness-guard":
        add_error(errors, "summary.skill: must be 'llm-api-freshness-guard'")
    if "mode" in data and data["mode"] not in ALLOWED_MODES:
        add_error(errors, f"summary.mode: invalid value {data['mode']!r}")
    if "repo_profile" in data:
        validate_repo_profile(data["repo_profile"], errors)
    if "doc_verification" in data:
        validate_doc_verification(data["doc_verification"], errors)
    if "findings" in data:
        validate_findings(data["findings"], errors)
    if "priorities" in data:
        validate_priorities(data["priorities"], errors)
    if "scan_limitations" in data:
        validate_string_list(data["scan_limitations"], "scan_limitations", errors)
    validate_verified_contract(data, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate llm-api-freshness-summary.json")
    parser.add_argument("summary_json", help="Path to .repo-harness/llm-api-freshness-summary.json")
    args = parser.parse_args()

    path = Path(args.summary_json).expanduser().resolve()
    if not path.exists():
        print(f"error: file does not exist: {path}", file=sys.stderr)
        return 2

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"error: failed to parse JSON: {exc}", file=sys.stderr)
        return 2

    errors = validate_summary(data)
    if errors:
        print("invalid summary:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("summary is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
