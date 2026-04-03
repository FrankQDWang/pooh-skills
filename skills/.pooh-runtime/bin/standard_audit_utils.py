#!/usr/bin/env python3
"""Shared helpers for the new report-only audit skills."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0.0"
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "coverage",
    ".repo-harness",
    ".pooh-runtime",
    "vendor",
    "target",
    "out",
    ".idea",
    ".vscode",
}
TEXT_EXTS = {
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".md",
    ".mdx",
    ".rst",
    ".sh",
}
ALLOWED_CATEGORY_STATES = {
    "missing",
    "theater",
    "partial",
    "enforced",
    "hardened",
    "unverified",
    "blocked",
    "not-applicable",
}
ALLOWED_VERDICTS = {"hardened", "enforced", "partial", "scan-blocked", "not-applicable"}
ALLOWED_GATE_STATUS = {"pass", "watch", "fail", "not-applicable", "unverified"}
ALLOWED_SEVERITY = {"critical", "high", "medium", "low"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_MERGE_GATES = {"block-now", "fix-before-release", "fix-next", "watch", "document-only"}
ALLOWED_DEPENDENCY_STATUS = {"ready", "auto-installed", "blocked"}
ALLOWED_ROLLUP_BUCKETS = {"blocked", "red", "yellow", "green", "not-applicable"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def rel(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


def is_skipped(rel_path: Path) -> bool:
    return any(part in SKIP_DIRS for part in rel_path.parts)


def iter_text_files(repo: Path, suffixes: set[str] | None = None) -> list[Path]:
    wanted = suffixes or TEXT_EXTS
    files: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(repo)
        if is_skipped(rel_path):
            continue
        if path.suffix.lower() in wanted or path.name in {"package.json", "pnpm-lock.yaml", "pyproject.toml", "uv.lock", ".npmrc"}:
            files.append(path)
    return sorted(files)


def workflow_files(repo: Path) -> list[Path]:
    workflow_root = repo / ".github" / "workflows"
    if not workflow_root.is_dir():
        return []
    return sorted(path for path in workflow_root.iterdir() if path.is_file() and path.suffix.lower() in {".yml", ".yaml"})


def package_managers(repo: Path) -> list[str]:
    managers: list[str] = []
    if (repo / "uv.lock").exists() or (repo / "pyproject.toml").exists():
        managers.append("uv")
    if (repo / "pnpm-lock.yaml").exists() or (repo / "package.json").exists():
        managers.append("pnpm")
    return managers


def find_named_files(repo: Path, names: set[str]) -> list[Path]:
    return sorted(path for path in iter_text_files(repo) if path.name in names)


def collect_matches(
    repo: Path,
    pattern: re.Pattern[str],
    *,
    suffixes: set[str] | None = None,
    names: set[str] | None = None,
    limit: int = 8,
) -> list[str]:
    matches: list[str] = []
    for path in iter_text_files(repo, suffixes=suffixes):
        if names is not None and path.name not in names:
            continue
        for line_no, line in enumerate(read_text(path).splitlines(), start=1):
            if pattern.search(line):
                matches.append(f"{rel(path, repo)}:{line_no} {line.strip()[:180]}")
                if len(matches) >= limit:
                    return matches
    return matches


def first_match_location(
    repo: Path,
    pattern: re.Pattern[str],
    *,
    suffixes: set[str] | None = None,
    names: set[str] | None = None,
) -> tuple[str, int, str] | None:
    for path in iter_text_files(repo, suffixes=suffixes):
        if names is not None and path.name not in names:
            continue
        for line_no, line in enumerate(read_text(path).splitlines(), start=1):
            if pattern.search(line):
                return rel(path, repo), line_no, line.strip()[:180]
    return None


def any_match(
    repo: Path,
    pattern: re.Pattern[str],
    *,
    suffixes: set[str] | None = None,
    names: set[str] | None = None,
) -> bool:
    return bool(collect_matches(repo, pattern, suffixes=suffixes, names=names, limit=1))


def count_matches(
    repo: Path,
    pattern: re.Pattern[str],
    *,
    suffixes: set[str] | None = None,
    names: set[str] | None = None,
) -> int:
    total = 0
    for path in iter_text_files(repo, suffixes=suffixes):
        if names is not None and path.name not in names:
            continue
        total += sum(1 for line in read_text(path).splitlines() if pattern.search(line))
    return total


def category_entry(
    category_id: str,
    title: str,
    state: str,
    confidence: str,
    evidence: list[str],
    notes: str = "",
) -> dict[str, Any]:
    return {
        "id": category_id,
        "title": title,
        "state": state,
        "confidence": confidence,
        "evidence": evidence[:8],
        "notes": notes,
    }


def finding_entry(
    category: str,
    severity: str,
    confidence: str,
    title: str,
    path: str,
    line: int,
    evidence_summary: str,
    recommended_change_shape: str,
    *,
    merge_gate: str = "watch",
    scope: str = "repo",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "id": "",
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "scope": scope,
        "title": title,
        "path": path,
        "line": line,
        "evidence_summary": evidence_summary,
        "recommended_change_shape": recommended_change_shape,
        "validation_checks": [],
        "merge_gate": merge_gate,
        "notes": notes,
    }


def normalize_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, finding in enumerate(findings, start=1):
        item = dict(finding)
        item["id"] = str(item.get("id") or f"{item.get('category', 'finding')}-{index:02d}")
        item["validation_checks"] = [str(value) for value in item.get("validation_checks") or []]
        normalized.append(item)
    return normalized


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(str(item.get("severity") or "low") for item in findings)
    return {
        "critical": int(counter.get("critical", 0)),
        "high": int(counter.get("high", 0)),
        "medium": int(counter.get("medium", 0)),
        "low": int(counter.get("low", 0)),
    }


def overall_verdict(categories: list[dict[str, Any]]) -> str:
    states = [str(item.get("state") or "missing") for item in categories if item.get("state") != "not-applicable"]
    if not states:
        return "not-applicable"
    if any(state == "blocked" for state in states):
        return "scan-blocked"
    if any(state in {"missing", "theater", "partial", "unverified"} for state in states):
        return "partial"
    if all(state == "hardened" for state in states):
        return "hardened"
    return "enforced"


def status_for_verdict(verdict: str) -> str:
    if verdict == "scan-blocked":
        return "blocked"
    if verdict == "not-applicable":
        return "not-applicable"
    return "complete"


def gate_status_for_category(category_state: str) -> str:
    if category_state == "hardened":
        return "pass"
    if category_state == "enforced":
        return "pass"
    if category_state == "not-applicable":
        return "not-applicable"
    if category_state == "unverified":
        return "unverified"
    if category_state == "blocked":
        return "fail"
    return "watch"


def gate_states(categories: list[dict[str, Any]]) -> list[dict[str, str]]:
    states: list[dict[str, str]] = []
    for category in categories:
        evidence = category.get("evidence") or []
        summary = category.get("notes") or (evidence[0] if evidence else "No direct evidence recorded.")
        states.append(
            {
                "name": str(category.get("id") or ""),
                "status": gate_status_for_category(str(category.get("state") or "missing")),
                "summary": str(summary),
            }
        )
    return states


def top_categories(findings: list[dict[str, Any]], limit: int = 4) -> list[str]:
    counter = Counter(str(item.get("category") or "") for item in findings if item.get("category"))
    return [name for name, _ in counter.most_common(limit)]


def build_summary(
    *,
    skill: str,
    repo: Path,
    repo_scope: str,
    coverage: dict[str, Any],
    categories: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    top_actions: list[str],
    summary_line: str,
    blocked_reason: str | None = None,
) -> dict[str, Any]:
    normalized_categories = [dict(item) for item in categories]
    normalized_findings = normalize_findings(findings)
    verdict = overall_verdict(normalized_categories)
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": skill,
        "generated_at": utc_now(),
        "repo_root": str(repo.resolve()),
        "repo_scope": repo_scope,
        "package_managers": package_managers(repo),
        "status": status_for_verdict(verdict),
        "verdict": verdict,
        "overall_verdict": verdict,
        "summary": summary_line,
        "summary_line": summary_line,
        "blocked_reason": blocked_reason,
        "coverage": coverage,
        "categories": normalized_categories,
        "gate_states": gate_states(normalized_categories),
        "findings": normalized_findings,
        "severity_counts": severity_counts(normalized_findings),
        "top_actions": top_actions[:3],
        "top_categories": top_categories(normalized_findings),
    }


def render_standard_report(
    title: str,
    summary: dict[str, Any],
    *,
    focus_label: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        "## 1. Executive summary",
        f"- Overall verdict: `{summary['overall_verdict']}`",
        f"- One-line diagnosis: `{summary['summary_line']}`",
        f"- Repo scope: `{summary['repo_scope']}`",
        f"- Package managers: `{', '.join(summary.get('package_managers') or ['none'])}`",
        "",
        f"## 2. {focus_label}",
        "",
    ]
    for category in summary["categories"]:
        lines.extend(
            [
                f"### {category['title']}",
                f"- State: `{category['state']}`",
                f"- Confidence: `{category['confidence']}`",
            ]
        )
        evidence = category.get("evidence") or []
        if evidence:
            lines.append("- Evidence:")
            lines.extend(f"  - `{item}`" for item in evidence[:5])
        if category.get("notes"):
            lines.append(f"- Notes: {category['notes']}")
        lines.append("")

    lines.extend(["## 3. Highest-risk findings", ""])
    if not summary["findings"]:
        lines.append("No material findings surfaced from the current local evidence set.")
        lines.append("")
    else:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_findings = sorted(summary["findings"], key=lambda item: (order[item["severity"]], item["path"], item["line"]))
        for finding in sorted_findings[:6]:
            lines.extend(
                [
                    f"### {finding['title']}",
                    f"- Category: `{finding['category']}`",
                    f"- Severity: `{finding['severity']}`",
                    f"- Confidence: `{finding['confidence']}`",
                    f"- Evidence: `{finding['path']}:{finding['line']}`",
                    "",
                    finding["evidence_summary"],
                    "",
                    f"Recommended shape: {finding['recommended_change_shape']}",
                    "",
                ]
            )

    lines.extend(["## 4. Ordered action queue", ""])
    for action in summary.get("top_actions") or ["No additional action is required beyond preserving the current control surface."]:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def render_standard_brief(
    title: str,
    summary: dict[str, Any],
    *,
    target_shape: list[str],
    validation_gates: list[str],
) -> str:
    lines = [
        f"# {title} Agent Brief",
        "",
        f"- overall_verdict: `{summary['overall_verdict']}`",
        f"- summary_line: `{summary['summary_line']}`",
        "",
        "## Target shape",
        "",
    ]
    for item in target_shape:
        lines.append(f"- {item}")
    lines.extend(["", "## Validation gates", ""])
    for item in validation_gates:
        lines.append(f"- {item}")
    lines.extend(["", "## Immediate actions", ""])
    for action in summary.get("top_actions") or ["Preserve the current control surface."]:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def validate_standard_summary(
    path: Path,
    *,
    skill_name: str,
    category_ids: set[str],
    coverage_keys: set[str],
) -> tuple[bool, str]:
    if not path.exists():
        return False, f"file not found: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"JSON parse error: {exc}"

    required_top = {
        "schema_version",
        "run_id",
        "skill",
        "domain",
        "generated_at",
        "repo_root",
        "rollup_bucket",
        "repo_scope",
        "package_managers",
        "status",
        "verdict",
        "overall_verdict",
        "summary",
        "summary_line",
        "coverage",
        "categories",
        "gate_states",
        "findings",
        "severity_counts",
        "top_actions",
        "dependency_status",
        "bootstrap_actions",
        "dependency_failures",
        "summary_path",
        "report_path",
        "agent_brief_path",
    }
    missing = required_top - set(data)
    if missing:
        return False, f"missing top-level keys: {sorted(missing)}"
    if data.get("skill") != skill_name:
        return False, f"skill must be `{skill_name}`"
    if data.get("overall_verdict") not in ALLOWED_VERDICTS:
        return False, f"unexpected overall_verdict `{data.get('overall_verdict')}`"
    if data.get("rollup_bucket") not in ALLOWED_ROLLUP_BUCKETS:
        return False, f"unexpected rollup_bucket `{data.get('rollup_bucket')}`"
    if data.get("dependency_status") not in ALLOWED_DEPENDENCY_STATUS:
        return False, f"unexpected dependency_status `{data.get('dependency_status')}`"

    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        return False, "coverage must be an object"
    missing_coverage = coverage_keys - set(coverage)
    if missing_coverage:
        return False, f"coverage missing keys: {sorted(missing_coverage)}"

    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        return False, "categories must be a non-empty list"
    for idx, category in enumerate(categories):
        if not isinstance(category, dict):
            return False, f"categories[{idx}] must be an object"
        for key in ("id", "title", "state", "confidence", "evidence"):
            if key not in category:
                return False, f"categories[{idx}] missing key `{key}`"
        if category["id"] not in category_ids:
            return False, f"categories[{idx}] has invalid id `{category['id']}`"
        if category["state"] not in ALLOWED_CATEGORY_STATES:
            return False, f"categories[{idx}] has invalid state `{category['state']}`"
        if category["confidence"] not in ALLOWED_CONFIDENCE:
            return False, f"categories[{idx}] has invalid confidence `{category['confidence']}`"
        if not isinstance(category["evidence"], list):
            return False, f"categories[{idx}].evidence must be a list"

    gate_states_payload = data.get("gate_states")
    if not isinstance(gate_states_payload, list) or not gate_states_payload:
        return False, "gate_states must be a non-empty list"
    for idx, gate in enumerate(gate_states_payload):
        if not isinstance(gate, dict):
            return False, f"gate_states[{idx}] must be an object"
        for key in ("name", "status", "summary"):
            if key not in gate:
                return False, f"gate_states[{idx}] missing key `{key}`"
        if gate["status"] not in ALLOWED_GATE_STATUS:
            return False, f"gate_states[{idx}] has invalid status `{gate['status']}`"

    findings = data.get("findings")
    if not isinstance(findings, list):
        return False, "findings must be a list"
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            return False, f"findings[{idx}] must be an object"
        for key in (
            "id",
            "category",
            "severity",
            "confidence",
            "scope",
            "title",
            "path",
            "line",
            "evidence_summary",
            "recommended_change_shape",
            "validation_checks",
            "merge_gate",
        ):
            if key not in finding:
                return False, f"findings[{idx}] missing key `{key}`"
        if finding["category"] not in category_ids:
            return False, f"findings[{idx}] has invalid category `{finding['category']}`"
        if finding["severity"] not in ALLOWED_SEVERITY:
            return False, f"findings[{idx}] has invalid severity `{finding['severity']}`"
        if finding["confidence"] not in ALLOWED_CONFIDENCE:
            return False, f"findings[{idx}] has invalid confidence `{finding['confidence']}`"
        if finding["merge_gate"] not in ALLOWED_MERGE_GATES:
            return False, f"findings[{idx}] has invalid merge_gate `{finding['merge_gate']}`"
        if not isinstance(finding["validation_checks"], list):
            return False, f"findings[{idx}].validation_checks must be a list"

    severity = data.get("severity_counts")
    if not isinstance(severity, dict):
        return False, "severity_counts must be an object"
    for key in ("critical", "high", "medium", "low"):
        if not isinstance(severity.get(key), int):
            return False, f"severity_counts.{key} must be an integer"

    if not isinstance(data.get("top_actions"), list):
        return False, "top_actions must be a list"
    if not isinstance(data.get("bootstrap_actions"), list):
        return False, "bootstrap_actions must be a list"
    if not isinstance(data.get("dependency_failures"), list):
        return False, "dependency_failures must be a list"

    return True, f"Validated {path}"
