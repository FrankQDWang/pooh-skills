#!/usr/bin/env python3
"""Deterministic fixture regressions for secrets-and-hardcode-audit."""

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
WRAPPER = REPO_ROOT / "skills" / "secrets-and-hardcode-audit" / "scripts" / "run_all.sh"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def run_wrapper(repo: Path, run_id: str) -> tuple[dict, str, str]:
    harness = repo / ".repo-harness"
    env = os.environ.copy()
    env["POOH_RUN_ID"] = run_id
    env["POOH_SKILLS_RUN_ID"] = run_id
    completed = subprocess.run(
        ["bash", str(WRAPPER), str(repo), str(harness)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"wrapper failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
    summary_path = harness / "skills" / "secrets-and-hardcode-audit" / "summary.json"
    report_path = harness / "skills" / "secrets-and-hardcode-audit" / "report.md"
    brief_path = harness / "skills" / "secrets-and-hardcode-audit" / "agent-brief.md"
    return (
        json.loads(summary_path.read_text(encoding="utf-8")),
        report_path.read_text(encoding="utf-8"),
        brief_path.read_text(encoding="utf-8"),
    )


def setup_clean_repo(repo: Path) -> None:
    git(repo, "init")
    git(repo, "config", "user.email", "fixture@example.com")
    git(repo, "config", "user.name", "Fixture")
    write(repo / ".gitignore", ".env\n.env.*\n*.pem\n*.key\n*.p12\n*.pfx\nid_rsa\nid_dsa\n")
    write(repo / "pyproject.toml", "[project]\nname='fixture'\nversion='0.1.0'\n")
    write(repo / "src" / "app.py", "def greet(name: str) -> str:\n    return f'hi {name}'\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")


def setup_history_leak_repo(repo: Path) -> None:
    setup_clean_repo(repo)
    write(repo / "src" / "secrets.py", 'TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz1234567890ABCD"\n')
    git(repo, "add", "src/secrets.py")
    git(repo, "commit", "-m", "introduce secret")
    write(repo / "src" / "secrets.py", 'TOKEN = os.environ["GITHUB_TOKEN"]\n')
    git(repo, "add", "src/secrets.py")
    git(repo, "commit", "-m", "remove secret")


def setup_worktree_secret_repo(repo: Path) -> None:
    git(repo, "init")
    git(repo, "config", "user.email", "fixture@example.com")
    git(repo, "config", "user.name", "Fixture")
    write(repo / ".gitignore", ".env\n.env.*\n*.pem\n*.key\n*.p12\n*.pfx\nid_rsa\nid_dsa\n")
    write(repo / "src" / "config.py", 'PASSWORD = "supersecret12345"\n')
    write(repo / "apps" / "web" / ".env.local", "OPENAI_API_KEY=fixture_secret_material_abcdefghijklmnopqrstuvwxyz123456\n")
    git(repo, "add", "src/config.py")
    git(repo, "commit", "-m", "baseline")


def inject_foreign_runtime_payload(repo: Path) -> None:
    base = repo / ".council-runtime" / "home" / ".claude" / "plugins" / "cache" / "fixture" / "site-packages" / "payload"
    write(base / "tests" / "test_hooks.sh", "export TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890ABCD\n")
    write(base / "auth.json", '{ "access_token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890ABCD" }\n')


def assert_clean_case() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="secrets-clean-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        setup_clean_repo(repo)
        summary, report, brief = run_wrapper(repo, "secrets-clean")
        if summary["overall_verdict"] != "clean":
            raise RuntimeError(f"clean case: expected clean, got {summary['overall_verdict']}")
        if summary["rollup_bucket"] != "green":
            raise RuntimeError(f"clean case: expected green, got {summary['rollup_bucket']}")
        if "## 2. Scan surface" not in report or "scan_surface:" not in brief:
            raise RuntimeError("clean case: scan surface section missing from report or brief")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def assert_history_case() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="secrets-history-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        setup_history_leak_repo(repo)
        summary, _, _ = run_wrapper(repo, "secrets-history")
        if summary["overall_verdict"] != "watch":
            raise RuntimeError(f"history case: expected watch, got {summary['overall_verdict']}")
        history_category = next(item for item in summary["categories"] if item["id"] == "git-history-secrets")
        if history_category["state"] != "watch":
            raise RuntimeError(f"history case: expected history watch, got {history_category['state']}")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def assert_worktree_case() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="secrets-worktree-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        setup_worktree_secret_repo(repo)
        summary, report, brief = run_wrapper(repo, "secrets-worktree")
        if summary["overall_verdict"] != "watch":
            raise RuntimeError(f"worktree case: expected watch, got {summary['overall_verdict']}")
        if summary["coverage"]["worktree_secret_hits"] < 1:
            raise RuntimeError("worktree case: expected at least one worktree secret hit")
        if summary["coverage"]["hardcoded_credential_hits"] < 1:
            raise RuntimeError("worktree case: expected at least one hardcoded credential hit")
        if summary["coverage"]["ignored_actionable_files_scanned"] < 1:
            raise RuntimeError("worktree case: expected ignored actionable files to be scanned")
        if summary["coverage"]["first_party_files_scanned"] < 1:
            raise RuntimeError("worktree case: expected first-party files to be scanned")
        if summary["coverage"]["surface_source"] != "git-index":
            raise RuntimeError(f"worktree case: expected git-index surface, got {summary['coverage']['surface_source']}")
        if "ignored-actionable" not in report or "ignored-actionable" not in brief:
            raise RuntimeError("worktree case: scan surface note missing ignored-actionable detail")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def assert_foreign_runtime_noise_case() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="secrets-foreign-runtime-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        setup_clean_repo(repo)
        inject_foreign_runtime_payload(repo)
        summary, _, _ = run_wrapper(repo, "secrets-foreign-runtime")
        if summary["overall_verdict"] != "clean":
            raise RuntimeError(f"foreign-runtime case: expected clean, got {summary['overall_verdict']}")
        if summary["coverage"]["foreign_runtime_files_excluded"] < 1:
            raise RuntimeError("foreign-runtime case: expected excluded foreign runtime files")
        for finding in summary["findings"]:
            path = str(finding.get("path") or "")
            if path.startswith(".council-runtime/"):
                raise RuntimeError(f"foreign-runtime case: leaked finding path {path}")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def main() -> int:
    assert_clean_case()
    assert_history_case()
    assert_worktree_case()
    assert_foreign_runtime_noise_case()
    print("Secrets-and-hardcode fixture regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
