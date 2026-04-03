#!/usr/bin/env python3
"""Deterministic regression fixtures for controlled-cleanup-hardgate verdict layering."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO_ROOT / "skills" / "controlled-cleanup-hardgate" / "scripts"
RUNTIME_BIN = REPO_ROOT / "skills" / ".pooh-runtime" / "bin"
VALIDATE_SCRIPT = SKILL_SCRIPTS / "validate_cleanup_summary.py"

for path in (SKILL_SCRIPTS, RUNTIME_BIN):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_cleanup_scan import Finding, human_verdict_label, infer_verdict, render_human_report  # noqa: E402
from runtime_contract import normalize_child_summary  # noqa: E402


@dataclass(frozen=True)
class Case:
    name: str
    findings: tuple[Finding, ...]
    expected_verdict: str
    expected_bucket: str
    expected_human_label: str


def make_finding(*, category: str, severity: str, summary: str) -> Finding:
    return Finding(
        category=category,
        severity=severity,
        confidence="high",
        path="src/legacy.py",
        line=10,
        language="Python",
        summary=summary,
        cue=None,
        replacement="src/new_path.py",
        removal_target=None,
        evidence=["fixture evidence"],
    )


def build_summary(findings: tuple[Finding, ...], verdict: str, summary_line: str) -> dict[str, object]:
    counts = Counter(item.category for item in findings)
    severity_counts = {level: 0 for level in ("critical", "high", "medium", "low")}
    for item in findings:
        severity_counts[item.severity] += 1
    return {
        "repo_root": "/fixture/repo",
        "generated_at": "2026-04-03T00:00:00Z",
        "overall_verdict": verdict,
        "summary_line": summary_line,
        "repo_profile": {
            "languages": ["Python"],
            "manifests": ["pyproject.toml"],
            "docs_roots": [],
            "tool_hints": ["python"],
        },
        "severity_counts": severity_counts,
        "counts": {
            "total": len(findings),
            "by_category": dict(sorted(counts.items())),
        },
        "tool_runs": [],
        "findings": [item.to_dict() for item in findings],
        "notes": [],
    }


def assert_case(case: Case) -> None:
    tempdir = Path(tempfile.mkdtemp(prefix=f"controlled-cleanup-{case.name}-"))
    try:
        summary_path = tempdir / "summary.json"
        report_path = tempdir / "report.md"
        brief_path = tempdir / "agent-brief.md"
        verdict, summary_line = infer_verdict(list(case.findings))
        if verdict != case.expected_verdict:
            raise RuntimeError(f"{case.name}: expected verdict {case.expected_verdict}, got {verdict}")

        raw_summary = build_summary(case.findings, verdict, summary_line)
        normalized = normalize_child_summary(
            {
                "skill": "controlled-cleanup-hardgate",
                "run_id": f"cleanup-{case.name}",
                "repo_root": "/fixture/repo",
                "report_path": str(report_path),
                "agent_brief_path": str(brief_path),
                "dependency_status": "ready",
                "bootstrap_actions": [],
                "dependency_failures": [],
            },
            summary_path,
            raw_summary,
        )
        summary_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        subprocess.run(
            ["python3", str(VALIDATE_SCRIPT), "--summary", str(summary_path)],
            check=True,
            cwd=REPO_ROOT,
        )

        if normalized["rollup_bucket"] != case.expected_bucket:
            raise RuntimeError(
                f"{case.name}: expected rollup_bucket={case.expected_bucket}, got {normalized['rollup_bucket']}"
            )

        report = render_human_report(normalized)
        expected_human_line = f"- verdict: `{case.expected_human_label}`"
        if expected_human_line not in report:
            raise RuntimeError(f"{case.name}: missing human verdict line {expected_human_line!r}")
        expected_machine_line = f"- machine_overall_verdict: `{case.expected_verdict}`"
        if expected_machine_line not in report:
            raise RuntimeError(f"{case.name}: missing machine verdict line {expected_machine_line!r}")
        if human_verdict_label(case.expected_verdict) != case.expected_human_label:
            raise RuntimeError(f"{case.name}: human_verdict_label drifted for {case.expected_verdict}")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def main() -> int:
    cases = [
        Case(
            name="blocked-cleanup",
            findings=(
                make_finding(
                    category="compatibility-shim",
                    severity="high",
                    summary="Compatibility shim still sits on the active path.",
                ),
                make_finding(
                    category="stale-doc-reference",
                    severity="high",
                    summary="Docs still point at the old surface after the migration window.",
                ),
            ),
            expected_verdict="not-ready",
            expected_bucket="red",
            expected_human_label="not ready",
        ),
        Case(
            name="partial-cleanup",
            findings=(
                make_finding(
                    category="stale-doc-reference",
                    severity="medium",
                    summary="Docs still point to the deprecated surface.",
                ),
            ),
            expected_verdict="partially-ready",
            expected_bucket="yellow",
            expected_human_label="partially ready",
        ),
        Case(
            name="ready-cleanup",
            findings=(),
            expected_verdict="ready-for-controlled-deletion",
            expected_bucket="green",
            expected_human_label="ready for controlled deletion",
        ),
    ]
    for case in cases:
        assert_case(case)
    print("Controlled-cleanup fixture regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
