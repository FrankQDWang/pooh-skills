#!/usr/bin/env python3
"""Deterministic regression fixtures for full-fleet repo-health aggregation and synthesis."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
ORCH_SCRIPTS = REPO_ROOT / "skills" / "repo-health-orchestrator" / "scripts"
if str(ORCH_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ORCH_SCRIPTS))

from repo_health_catalog import DOMAIN_SPECS  # noqa: E402
from repo_health_catalog import agent_brief_path as child_agent_brief_path  # noqa: E402
from repo_health_catalog import report_path as child_report_path  # noqa: E402
from repo_health_catalog import summary_path as child_summary_path  # noqa: E402

RUN_ID = "repo-health-fixture-run"
INVALID_JSON = "__invalid_json__"


@dataclass(frozen=True)
class Case:
    name: str
    runs: dict[str, dict[str, Any] | None | str]
    expected_overall_health: str
    expected_coverage_status: str
    expected_missing_skills: tuple[str, ...] = ()
    expected_invalid_summaries: tuple[str, ...] = ()
    missing_reports: tuple[str, ...] = ()
    missing_briefs: tuple[str, ...] = ()
    expected_unknowns: tuple[tuple[str, str], ...] = ()
    bootstrap_payload: dict[str, Any] = field(
        default_factory=lambda: {
            "dependency_status": "ready",
            "bootstrap_actions": [],
            "dependency_failures": [],
        }
    )


def base_summary(skill_name: str, domain: str, verdict: str, rollup_bucket: str) -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "skill": skill_name,
        "domain": domain,
        "repo_root": "/fixture/repo",
        "generated_at": "2026-03-30T00:00:00+00:00",
        "dependency_status": "ready",
        "bootstrap_actions": [],
        "dependency_failures": [],
        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "findings": [],
        "overall_verdict": verdict,
        "rollup_bucket": rollup_bucket,
        "summary_path": f"/fixture/.repo-harness/skills/{skill_name}/summary.json",
        "report_path": f"/fixture/.repo-harness/skills/{skill_name}/report.md",
        "agent_brief_path": f"/fixture/.repo-harness/skills/{skill_name}/agent-brief.md",
    }


def positive_summary(skill_name: str, domain: str) -> dict[str, Any]:
    if domain == "llm-api-freshness":
        verdict = "verified"
    elif domain in {"secrets-and-hardcode", "test-quality"}:
        verdict = "clean"
    else:
        verdict = "healthy"
    return base_summary(skill_name, domain, verdict, "green")


def not_applicable_summary(skill_name: str, domain: str) -> dict[str, Any]:
    return base_summary(skill_name, domain, "not-applicable", "not-applicable")


def watch_summary(skill_name: str, domain: str, verdict: str = "watch") -> dict[str, Any]:
    payload = base_summary(skill_name, domain, verdict, "yellow")
    payload["severity_counts"] = {"critical": 0, "high": 0, "medium": 1, "low": 0}
    payload["findings"] = [{"severity": "medium", "category": "watch-signal"}]
    return payload


def blocked_summary(skill_name: str, domain: str) -> dict[str, Any]:
    payload = base_summary(skill_name, domain, "scan-blocked", "blocked")
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


def triage_freshness_summary() -> dict[str, Any]:
    return base_summary("llm-api-freshness-guard", "llm-api-freshness", "triage", "yellow")


def case_payloads() -> dict[str, dict[str, Any]]:
    return {
        spec.domain: positive_summary(spec.skill_name, spec.domain)
        for spec in DOMAIN_SPECS
    }


def make_cases() -> list[Case]:
    healthy = case_payloads()
    all_not_applicable = {
        spec.domain: not_applicable_summary(spec.skill_name, spec.domain)
        for spec in DOMAIN_SPECS
    }
    blocked = dict(healthy)
    blocked["error-governance"] = blocked_summary("error-governance-hardgate", "error-governance")
    missing = dict(healthy)
    missing["cleanup"] = None
    invalid = dict(healthy)
    invalid["contracts"] = INVALID_JSON
    watched = dict(healthy)
    watched["pythonic-ddd-drift"] = watch_summary("pythonic-ddd-drift-audit", "pythonic-ddd-drift")
    triaged = dict(healthy)
    triaged["llm-api-freshness"] = triage_freshness_summary()
    mismatched = dict(healthy)
    mismatched["module-shape"] = {
        **positive_summary("module-shape-hardgate", "module-shape"),
        "run_id": "different-run-id",
    }

    return [
        Case("healthy-complete", healthy, "healthy", "complete"),
        Case("all-not-applicable", all_not_applicable, "not-applicable", "complete"),
        Case("blocked-child", blocked, "blocked", "complete"),
        Case(
            "missing-child-summary",
            missing,
            "watch",
            "partial",
            expected_missing_skills=("controlled-cleanup-hardgate",),
        ),
        Case(
            "invalid-child-summary",
            invalid,
            "watch",
            "partial",
            expected_invalid_summaries=("signature-contract-hardgate",),
        ),
        Case("watch-signal", watched, "watch", "complete"),
        Case(
            "triage-freshness",
            triaged,
            "watch",
            "complete",
            expected_unknowns=(("llm-api-freshness", "trust-gap"),),
        ),
        Case(
            "run-id-mismatch",
            mismatched,
            "watch",
            "partial",
            expected_invalid_summaries=("module-shape-hardgate",),
        ),
        Case(
            "missing-child-report",
            healthy,
            "healthy",
            "complete",
            missing_reports=("silent-failure",),
            expected_unknowns=(("silent-failure", "missing-human-report"),),
        ),
        Case(
            "missing-child-brief",
            healthy,
            "healthy",
            "complete",
            missing_briefs=("module-shape",),
            expected_unknowns=(("module-shape", "missing-agent-brief"),),
        ),
    ]


def write_child_artifacts(repo_dir: Path, harness_dir: Path, case: Case) -> None:
    for spec in DOMAIN_SPECS:
        payload = case.runs[spec.domain]
        summary_file = child_summary_path(harness_dir, spec.domain)
        report_file = child_report_path(harness_dir, spec.domain)
        brief_file = child_agent_brief_path(harness_dir, spec.domain)

        summary_file.parent.mkdir(parents=True, exist_ok=True)
        if payload == INVALID_JSON:
            summary_file.write_text("{invalid\n", encoding="utf-8")
        elif payload is not None:
            prepared = dict(payload)
            prepared["repo_root"] = str(repo_dir)
            summary_file.write_text(json.dumps(prepared, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        if spec.domain not in set(case.missing_reports):
            report_file.write_text(f"# {spec.domain}\n\nreport\n", encoding="utf-8")
        if spec.domain not in set(case.missing_briefs):
            brief_file.write_text(f"# {spec.domain}\n\nbrief\n", encoding="utf-8")


def run_subprocess(command: list[str], *, cwd: Path) -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(command, check=True, cwd=cwd, env=env)


def assert_unknowns(case: Case, evidence: dict[str, Any]) -> None:
    actual = {(str(item["scope"]), str(item["kind"])) for item in evidence.get("unknowns", [])}
    expected = set(case.expected_unknowns)
    missing = expected - actual
    if missing:
        raise RuntimeError(f"{case.name}: missing expected unknowns {sorted(missing)}; actual={sorted(actual)}")


def run_case(case: Case) -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix=f"repo-health-{case.name}-"))
    try:
        repo_dir = tmpdir / "repo"
        harness_dir = repo_dir / ".repo-harness"
        repo_dir.mkdir(parents=True, exist_ok=True)
        harness_dir.mkdir(parents=True, exist_ok=True)
        write_child_artifacts(repo_dir, harness_dir, case)

        bootstrap_path = harness_dir / "repo-health-shared-bootstrap.json"
        summary_path = harness_dir / "repo-health-summary.json"
        evidence_path = harness_dir / "repo-health-evidence.json"
        report_path = harness_dir / "repo-health-report.md"
        brief_path = harness_dir / "repo-health-agent-brief.md"

        bootstrap_path.write_text(json.dumps(case.bootstrap_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        run_subprocess(
            [
                "python3",
                str(ORCH_SCRIPTS / "aggregate_repo_health.py"),
                "--repo",
                str(repo_dir),
                "--run-id",
                RUN_ID,
                "--harness-dir",
                str(harness_dir),
                "--bootstrap-json",
                str(bootstrap_path),
                "--out-json",
                str(summary_path),
            ],
            cwd=REPO_ROOT,
        )
        run_subprocess(
            [
                "python3",
                str(ORCH_SCRIPTS / "validate_repo_health_summary.py"),
                "--summary",
                str(summary_path),
            ],
            cwd=REPO_ROOT,
        )
        run_subprocess(
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
            cwd=REPO_ROOT,
        )

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

        if summary["run_id"] != RUN_ID:
            raise RuntimeError(f"{case.name}: aggregate summary run_id mismatch")
        if summary["overall_health"] != case.expected_overall_health:
            raise RuntimeError(
                f"{case.name}: expected overall_health={case.expected_overall_health}, got {summary['overall_health']}"
            )
        if summary["coverage_status"] != case.expected_coverage_status:
            raise RuntimeError(
                f"{case.name}: expected coverage_status={case.expected_coverage_status}, got {summary['coverage_status']}"
            )
        if tuple(summary.get("missing_skills", [])) != case.expected_missing_skills:
            raise RuntimeError(
                f"{case.name}: expected missing_skills={case.expected_missing_skills}, got {tuple(summary.get('missing_skills', []))}"
            )
        if tuple(summary.get("invalid_summaries", [])) != case.expected_invalid_summaries:
            raise RuntimeError(
                f"{case.name}: expected invalid_summaries={case.expected_invalid_summaries}, got {tuple(summary.get('invalid_summaries', []))}"
            )
        if not report_path.exists() or not brief_path.exists():
            raise RuntimeError(f"{case.name}: synthesis outputs were not produced")

        assert_unknowns(case, evidence)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> int:
    for case in make_cases():
        run_case(case)
    print("Repo-health fixture regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
