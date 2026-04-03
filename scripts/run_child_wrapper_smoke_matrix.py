#!/usr/bin/env python3
"""Smoke-test every audit skill wrapper against a minimal mixed-language fixture repo."""

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

RUN_ID = "child-wrapper-smoke-run"
VALID_DEPENDENCY_STATUSES = {"ready", "auto-installed", "blocked"}
VALID_ROLLUP_BUCKETS = {"blocked", "red", "yellow", "green", "not-applicable"}


def create_fixture_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "web").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)

    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "fixture-repo"',
                'version = "0.1.0"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "fixture-repo",
                "version": "0.1.0",
                "private": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "src" / "service.py").write_text(
        "def greet(name: str) -> str:\n    return f'hello {name}'\n",
        encoding="utf-8",
    )
    (root / "web" / "index.ts").write_text(
        "export const greet = (name: string): string => `hello ${name}`;\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Fixture Repo\n\nA small mixed-language fixture.\n", encoding="utf-8")
    (root / "docs" / "api.md").write_text("# API\n\nCurrent endpoints are documented locally.\n", encoding="utf-8")
    (root / ".github" / "workflows" / "ci.yml").write_text(
        "name: ci\non: [push]\njobs:\n  checks:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_sidecar(path: Path, skill_name: str, domain: str, repo_root: Path) -> None:
    payload = read_json(path)
    if payload.get("run_id") != RUN_ID:
        raise RuntimeError(f"{skill_name}: runtime run_id mismatch")
    if payload.get("skill") != skill_name:
        raise RuntimeError(f"{skill_name}: runtime skill mismatch")
    if payload.get("domain") != domain:
        raise RuntimeError(f"{skill_name}: runtime domain mismatch")
    if payload.get("repo_root") != str(repo_root.resolve()):
        raise RuntimeError(f"{skill_name}: runtime repo_root mismatch")
    if not isinstance(payload.get("generated_at"), str) or not payload.get("generated_at"):
        raise RuntimeError(f"{skill_name}: runtime generated_at missing")
    if payload.get("dependency_status") not in VALID_DEPENDENCY_STATUSES:
        raise RuntimeError(f"{skill_name}: runtime dependency_status invalid")
    if not isinstance(payload.get("bootstrap_actions"), list):
        raise RuntimeError(f"{skill_name}: runtime bootstrap_actions missing")
    if not isinstance(payload.get("dependency_failures"), list):
        raise RuntimeError(f"{skill_name}: runtime dependency_failures missing")


def assert_summary(path: Path, skill_name: str, domain: str, repo_root: Path, report_path: Path, brief_path: Path) -> None:
    payload = read_json(path)
    if payload.get("run_id") != RUN_ID:
        raise RuntimeError(f"{skill_name}: summary run_id mismatch")
    if payload.get("skill") != skill_name:
        raise RuntimeError(f"{skill_name}: summary skill mismatch")
    if payload.get("domain") != domain:
        raise RuntimeError(f"{skill_name}: summary domain mismatch")
    if payload.get("repo_root") != str(repo_root.resolve()):
        raise RuntimeError(f"{skill_name}: summary repo_root mismatch")
    if not isinstance(payload.get("generated_at"), str) or not payload.get("generated_at"):
        raise RuntimeError(f"{skill_name}: summary generated_at missing")
    if payload.get("dependency_status") not in VALID_DEPENDENCY_STATUSES:
        raise RuntimeError(f"{skill_name}: summary dependency_status invalid")
    if payload.get("rollup_bucket") not in VALID_ROLLUP_BUCKETS:
        raise RuntimeError(f"{skill_name}: summary rollup_bucket invalid")
    if not isinstance(payload.get("overall_verdict"), str) or not payload.get("overall_verdict"):
        raise RuntimeError(f"{skill_name}: summary overall_verdict missing")
    if not isinstance(payload.get("bootstrap_actions"), list):
        raise RuntimeError(f"{skill_name}: summary bootstrap_actions missing")
    if not isinstance(payload.get("dependency_failures"), list):
        raise RuntimeError(f"{skill_name}: summary dependency_failures missing")
    if payload.get("summary_path") != str(path.resolve()):
        raise RuntimeError(f"{skill_name}: summary_path not injected correctly")
    if payload.get("report_path") != str(report_path.resolve()):
        raise RuntimeError(f"{skill_name}: report_path not injected correctly")
    if payload.get("agent_brief_path") != str(brief_path.resolve()):
        raise RuntimeError(f"{skill_name}: agent_brief_path not injected correctly")
    if not isinstance(payload.get("severity_counts"), dict):
        raise RuntimeError(f"{skill_name}: summary severity_counts missing")
    if not isinstance(payload.get("findings"), list):
        raise RuntimeError(f"{skill_name}: summary findings missing")
    if not report_path.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"{skill_name}: report is empty")
    if not brief_path.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"{skill_name}: agent brief is empty")


def run_wrapper(repo_root: Path, harness_dir: Path, skill_name: str, domain: str) -> None:
    wrapper = REPO_ROOT / "skills" / skill_name / "scripts" / "run_all.sh"
    child_dir = harness_dir / "skills" / skill_name
    runtime_path = child_dir / "runtime.json"
    summary_path = child_dir / "summary.json"
    report_path = child_dir / "report.md"
    brief_path = child_dir / "agent-brief.md"

    env = os.environ.copy()
    env["POOH_RUN_ID"] = RUN_ID
    env["POOH_SKILLS_RUN_ID"] = RUN_ID
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        ["bash", str(wrapper), str(repo_root), str(harness_dir)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(
            f"{skill_name}: wrapper exited {completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    for path in (runtime_path, summary_path, report_path, brief_path):
        if not path.exists():
            raise RuntimeError(f"{skill_name}: expected artifact missing at {path}")

    assert_sidecar(runtime_path, skill_name, domain, repo_root)
    assert_summary(summary_path, skill_name, domain, repo_root, report_path, brief_path)


def main() -> int:
    tempdir = Path(tempfile.mkdtemp(prefix="child-wrapper-smoke-"))
    try:
        repo_root = tempdir / "repo"
        harness_dir = repo_root / ".repo-harness"
        repo_root.mkdir(parents=True, exist_ok=True)
        harness_dir.mkdir(parents=True, exist_ok=True)
        create_fixture_repo(repo_root)

        for spec in DOMAIN_SPECS:
            run_wrapper(repo_root, harness_dir, spec.skill_name, spec.domain)

        print("Child wrapper smoke matrix passed.")
        return 0
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
