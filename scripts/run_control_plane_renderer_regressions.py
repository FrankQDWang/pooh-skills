#!/usr/bin/env python3
"""Regression coverage for repo-health control-plane rendering."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
ORCH_SCRIPTS = REPO_ROOT / "skills" / "repo-health-orchestrator" / "scripts"
if str(ORCH_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ORCH_SCRIPTS))

from repo_health_catalog import DOMAIN_SPECS  # noqa: E402
from repo_health_catalog import agent_brief_path as child_agent_brief_path  # noqa: E402
from repo_health_catalog import report_path as child_report_path  # noqa: E402
from repo_health_catalog import summary_path as child_summary_path  # noqa: E402

RUN_ID = "renderer-regression-run"


def run_python(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=True)
    return completed


def render(state_path: Path, width: int, final: bool = False) -> str:
    command = [
        "python3",
        str(ORCH_SCRIPTS / "render_control_plane.py"),
        "--state",
        str(state_path),
        "--width",
        str(width),
        "--no-clear",
        "--no-color",
    ]
    if final:
        command.append("--final")
    return run_python(command, cwd=REPO_ROOT).stdout


def write_summary(summary_path: Path, repo_root: Path, harness_dir: Path) -> None:
    skill_runs = []
    for spec in DOMAIN_SPECS:
        status = "present"
        dependency_status = "ready"
        verdict = "healthy"
        notes = ""
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        if spec.domain == "structure":
            verdict = "blocked"
            severity_counts = {"critical": 0, "high": 1, "medium": 0, "low": 0}
        elif spec.domain == "cleanup":
            status = "missing"
            notes = "summary file not found"
        elif spec.domain == "silent-failure":
            status = "invalid"
            notes = "summary failed validation"
        skill_runs.append(
            {
                "run_id": RUN_ID,
                "domain": spec.domain,
                "skill_name": spec.skill_name,
                "status": status,
                "summary_path": str(child_summary_path(harness_dir, spec.domain).resolve()),
                "report_path": str(child_report_path(harness_dir, spec.domain).resolve()),
                "agent_brief_path": str(child_agent_brief_path(harness_dir, spec.domain).resolve()),
                "dependency_status": dependency_status,
                "dependency_failures": [],
                "child_verdict": verdict,
                "severity_counts": severity_counts,
                "top_categories": ["regression-signal"] if spec.domain == "structure" else [],
                "notes": notes,
            }
        )

    payload = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "skill": "repo-health-orchestrator",
        "generated_at": "2026-03-30T00:00:00+00:00",
        "repo_root": str(repo_root.resolve()),
        "overall_health": "watch",
        "coverage_status": "partial",
        "summary_line": "No blocker-free run exists because one domain is high risk and coverage is incomplete.",
        "skill_runs": skill_runs,
        "top_actions": [
            "Fix structure first.",
            "Re-run cleanup coverage.",
            "Rebuild silent-failure summary.",
        ],
        "missing_skills": ["controlled-cleanup-hardgate"],
        "invalid_summaries": ["overdefensive-silent-failure-hardgate"],
        "dependency_status": "ready",
        "bootstrap_actions": [],
        "dependency_failures": [],
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def assert_contains(label: str, text: str, fragments: list[str]) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise RuntimeError(f"{label}: missing fragments {missing}")


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="renderer-regression-"))
    try:
        repo_root = tmpdir / "repo"
        harness_dir = repo_root / ".repo-harness"
        state_path = harness_dir / "repo-health-control-plane.json"
        summary_path = harness_dir / "repo-health-summary.json"
        repo_root.mkdir(parents=True, exist_ok=True)
        harness_dir.mkdir(parents=True, exist_ok=True)

        run_python(
            [
                "python3",
                str(ORCH_SCRIPTS / "control_plane_state.py"),
                "init",
                "--state",
                str(state_path),
                "--run-id",
                RUN_ID,
                "--context",
                "renderer-regression",
            ],
            cwd=REPO_ROOT,
        )
        run_python(
            [
                "python3",
                str(ORCH_SCRIPTS / "control_plane_state.py"),
                "update-overall",
                "--state",
                str(state_path),
                "--stage",
                "running",
                "--summary-line",
                "Renderer regression is exercising the live board.",
                "--auto-progress",
            ],
            cwd=REPO_ROOT,
        )
        run_python(
            [
                "python3",
                str(ORCH_SCRIPTS / "control_plane_state.py"),
                "update-worker",
                "--state",
                str(state_path),
                "--domain",
                "structure",
                "--runtime-status",
                "running",
                "--detail",
                "subagent active",
            ],
            cwd=REPO_ROOT,
        )

        wide_running = render(state_path, 160)
        narrow_running = render(state_path, 96)
        assert_contains(
            "wide running render",
            wide_running,
            [
                "MAIN ORCHESTRATOR",
                "ACTION QUEUE",
                "CHILD SUBAGENT SKILLS (Workers)",
                "Audit-Dependencies",
                "run_id: renderer-regression-run",
            ],
        )
        assert_contains(
            "narrow running render",
            narrow_running,
            [
                "MAIN ORCHESTRATOR",
                "ACTION QUEUE",
                "Audit-Contracts",
                "Status:",
            ],
        )

        write_summary(summary_path, repo_root, harness_dir)
        run_python(
            [
                "python3",
                str(ORCH_SCRIPTS / "control_plane_state.py"),
                "finalize-from-summary",
                "--state",
                str(state_path),
                "--summary",
                str(summary_path),
            ],
            cwd=REPO_ROOT,
        )

        wide_final = render(state_path, 160, final=True)
        narrow_final = render(state_path, 96, final=True)
        assert_contains(
            "wide final render",
            wide_final,
            [
                "overall_health: watch",
                "coverage_status: partial",
                "Missing: controlled-cleanup-hardgate",
                "Invalid: overdefensive-silent-failure-hardgate",
                "Fix structure first.",
            ],
        )
        assert_contains(
            "narrow final render",
            narrow_final,
            [
                "COMPLETE (Watch Items Active)",
                "coverage_status: partial",
                "Audit-Silent-Failure",
                "Fix structure first.",
            ],
        )

        print("Control-plane renderer regressions passed.")
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
