#!/usr/bin/env python3
"""Deterministic regression fixtures for repo-health aggregation and synthesis."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ORCH_SCRIPTS = REPO_ROOT / "skills" / "repo-health-orchestrator" / "scripts"


@dataclass(frozen=True)
class Case:
    name: str
    runs: dict[str, dict | None]
    expected_overall_health: str
    expected_coverage_status: str


def positive_summary(skill_name: str, verdict: str) -> dict:
    return {
        "skill": skill_name,
        "dependency_status": "ready",
        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "findings": [],
        "overall_verdict": verdict,
    }


def watch_summary(skill_name: str, verdict: str = "watch") -> dict:
    payload = positive_summary(skill_name, verdict)
    payload["severity_counts"] = {"critical": 0, "high": 0, "medium": 1, "low": 0}
    payload["findings"] = [{"severity": "medium", "category": "watch"}]
    return payload


def blocked_summary(skill_name: str, verdict: str = "scan-blocked") -> dict:
    payload = positive_summary(skill_name, verdict)
    payload["dependency_status"] = "blocked"
    payload["dependency_failures"] = [
        {
            "name": "context7",
            "kind": "mcp",
            "required_for": skill_name,
            "attempted_command": "context7 lookup",
            "failure_reason": "Context7 unavailable",
            "blocked_by_security": False,
            "blocked_by_permissions": False,
            "blocked_by_network": False,
        }
    ]
    return payload


SKILL_BY_DOMAIN = {
    "structure": "dependency-audit",
    "contracts": "signature-contract-hardgate",
    "durable-agents": "pydantic-ai-temporal-hardgate",
    "llm-api-freshness": "llm-api-freshness-guard",
    "cleanup": "controlled-cleanup-hardgate",
    "distributed-side-effects": "distributed-side-effect-hardgate",
    "pythonic-ddd-drift": "pythonic-ddd-drift-audit",
}

SUMMARY_NAME_BY_DOMAIN = {
    "structure": "repo-audit-summary.json",
    "contracts": "contract-hardgate-summary.json",
    "durable-agents": "pydantic-temporal-summary.json",
    "llm-api-freshness": "llm-api-freshness-summary.json",
    "cleanup": "controlled-cleanup-summary.json",
    "distributed-side-effects": "distributed-side-effect-summary.json",
    "pythonic-ddd-drift": "pythonic-ddd-drift-summary.json",
}

REPORT_NAME_BY_DOMAIN = {
    "structure": "repo-audit-report.md",
    "contracts": "contract-hardgate-human-report.md",
    "durable-agents": "pydantic-temporal-human-report.md",
    "llm-api-freshness": "llm-api-freshness-report.md",
    "cleanup": "controlled-cleanup-report.md",
    "distributed-side-effects": "distributed-side-effect-report.md",
    "pythonic-ddd-drift": "pythonic-ddd-drift-report.md",
}

BRIEF_NAME_BY_DOMAIN = {
    "structure": "repo-audit-agent-brief.md",
    "contracts": "contract-hardgate-agent-brief.md",
    "durable-agents": "pydantic-temporal-agent-brief.md",
    "llm-api-freshness": "llm-api-freshness-agent-brief.md",
    "cleanup": "controlled-cleanup-agent-brief.md",
    "distributed-side-effects": "distributed-side-effect-agent-brief.md",
    "pythonic-ddd-drift": "pythonic-ddd-drift-agent-brief.md",
}


def make_cases() -> list[Case]:
    healthy = {
        domain: positive_summary(skill, "healthy" if domain != "llm-api-freshness" else "verified")
        for domain, skill in SKILL_BY_DOMAIN.items()
    }
    all_not_applicable = {
        domain: positive_summary(skill, "not-applicable")
        for domain, skill in SKILL_BY_DOMAIN.items()
    }
    blocked = dict(healthy)
    blocked["llm-api-freshness"] = blocked_summary("llm-api-freshness-guard")
    missing = dict(healthy)
    missing["cleanup"] = None
    invalid = dict(healthy)
    invalid["contracts"] = {"invalid_json": True}
    watched = dict(healthy)
    watched["pythonic-ddd-drift"] = watch_summary("pythonic-ddd-drift-audit")
    return [
        Case("healthy-complete", healthy, "healthy", "complete"),
        Case("all-not-applicable", all_not_applicable, "not-applicable", "complete"),
        Case("blocked-child", blocked, "blocked", "complete"),
        Case("missing-child-summary", missing, "watch", "partial"),
        Case("invalid-child-summary", invalid, "watch", "partial"),
        Case("watch-signal", watched, "watch", "complete"),
    ]


def write_case_files(repo_dir: Path, harness_dir: Path, case: Case) -> None:
    for domain, payload in case.runs.items():
        summary_name = SUMMARY_NAME_BY_DOMAIN[domain]
        report_name = REPORT_NAME_BY_DOMAIN[domain]
        brief_name = BRIEF_NAME_BY_DOMAIN[domain]
        if payload is None:
            continue
        if payload.get("invalid_json"):
            (harness_dir / summary_name).write_text("{invalid\n", encoding="utf-8")
        else:
            (harness_dir / summary_name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (harness_dir / report_name).write_text(f"# {domain}\n\nreport\n", encoding="utf-8")
        (harness_dir / brief_name).write_text(f"# {domain}\n\nbrief\n", encoding="utf-8")


def run_case(case: Case) -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix=f"repo-health-{case.name}-"))
    try:
        repo_dir = tmpdir / "repo"
        harness_dir = repo_dir / ".repo-harness"
        repo_dir.mkdir(parents=True, exist_ok=True)
        harness_dir.mkdir(parents=True, exist_ok=True)
        write_case_files(repo_dir, harness_dir, case)

        summary_path = harness_dir / "repo-health-summary.json"
        evidence_path = harness_dir / "repo-health-evidence.json"
        report_path = harness_dir / "repo-health-report.md"
        brief_path = harness_dir / "repo-health-agent-brief.md"

        subprocess.run(
            [
                "python3",
                str(ORCH_SCRIPTS / "aggregate_repo_health.py"),
                "--repo",
                str(repo_dir),
                "--harness-dir",
                str(harness_dir),
                "--out-json",
                str(summary_path),
            ],
            check=True,
            cwd=REPO_ROOT,
        )
        subprocess.run(
            [
                "python3",
                str(ORCH_SCRIPTS / "validate_repo_health_summary.py"),
                "--summary",
                str(summary_path),
            ],
            check=True,
            cwd=REPO_ROOT,
        )
        subprocess.run(
            [
                "python3",
                str(ORCH_SCRIPTS / "synthesize_repo_health.py"),
                "--repo",
                str(repo_dir),
                "--summary",
                str(summary_path),
                "--harness-dir",
                str(harness_dir),
                "--out-evidence",
                str(evidence_path),
                "--out-report",
                str(report_path),
                "--out-brief",
                str(brief_path),
            ],
            check=True,
            cwd=REPO_ROOT,
        )

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary["overall_health"] != case.expected_overall_health:
            raise RuntimeError(
                f"{case.name}: expected overall_health={case.expected_overall_health}, got {summary['overall_health']}"
            )
        if summary["coverage_status"] != case.expected_coverage_status:
            raise RuntimeError(
                f"{case.name}: expected coverage_status={case.expected_coverage_status}, got {summary['coverage_status']}"
            )
        if not evidence_path.exists() or not report_path.exists() or not brief_path.exists():
            raise RuntimeError(f"{case.name}: synthesis outputs were not produced")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> int:
    for case in make_cases():
        run_case(case)
    print("Repo-health fixture regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
