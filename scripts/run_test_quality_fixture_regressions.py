#!/usr/bin/env python3
"""Deterministic fixture regressions for test-quality-audit."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "test-quality-audit" / "scripts" / "run_test_quality_scan.py"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_scan(repo: Path) -> dict:
    out_dir = repo / ".repo-harness"
    summary = out_dir / "summary.json"
    report = out_dir / "report.md"
    brief = out_dir / "agent-brief.md"
    completed = subprocess.run(
        [
            "python3.12",
            str(SCRIPT),
            "--repo",
            str(repo),
            "--summary-out",
            str(summary),
            "--report-out",
            str(report),
            "--agent-brief-out",
            str(brief),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    _ = completed
    payload = json.loads(summary.read_text(encoding="utf-8"))
    if not report.read_text(encoding="utf-8").strip():
        raise RuntimeError("report is empty")
    if not brief.read_text(encoding="utf-8").strip():
        raise RuntimeError("brief is empty")
    return payload


def setup_clean_repo(repo: Path) -> None:
    write(repo / "pyproject.toml", "[project]\nname='fixture'\nversion='0.1.0'\n")
    write(repo / "src" / "service.py", "def divide(a: int, b: int) -> float:\n    return a / b\n")
    write(
        repo / "tests" / "test_service.py",
        """
import pytest

from src.service import divide


def test_divide_success() -> None:
    assert divide(6, 3) == 2


def test_divide_zero_error() -> None:
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
        """.strip()
        + "\n",
    )
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: uv run pytest
        """.strip()
        + "\n",
    )


def setup_placeholder_repo(repo: Path) -> None:
    write(repo / "pyproject.toml", "[project]\nname='fixture'\nversion='0.1.0'\n")
    write(repo / "src" / "service.py", "def greet() -> str:\n    return 'ok'\n")
    write(
        repo / "tests" / "test_placeholder.py",
        """
def test_placeholder() -> None:
    assert True
        """.strip()
        + "\n",
    )
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: uv run pytest
        """.strip()
        + "\n",
    )


def setup_mock_skip_repo(repo: Path) -> None:
    write(
        repo / "package.json",
        json.dumps({"name": "fixture", "private": True, "scripts": {"test": "vitest run"}}, indent=2) + "\n",
    )
    write(repo / "src" / "logic.ts", "export const compute = (value: number) => value * 2;\n")
    write(
        repo / "tests" / "logic.test.ts",
        """
import { describe, it, expect, vi } from "vitest";

vi.mock("../src/logic");
vi.mock("../src/logic");
vi.mock("../src/logic");

describe.skip("logic", () => {
  it("skips too much", () => {
    expect(true).toBe(true);
  });
});
        """.strip()
        + "\n",
    )
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pnpm test
      - run: echo retries: 2
        """.strip()
        + "\n",
    )


def setup_not_applicable_repo(repo: Path) -> None:
    write(repo / "README.md", "# docs only\n")


def assert_clean_case() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="test-quality-clean-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        setup_clean_repo(repo)
        payload = run_scan(repo)
        assert payload["overall_verdict"] == "clean", payload["overall_verdict"]
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def assert_placeholder_case() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="test-quality-placeholder-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        setup_placeholder_repo(repo)
        payload = run_scan(repo)
        categories = {item["id"]: item["state"] for item in payload["categories"]}
        assert payload["overall_verdict"] == "watch", payload["overall_verdict"]
        assert categories["placeholder-test-quality"] == "watch", categories
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def assert_mock_skip_case() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="test-quality-mock-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        setup_mock_skip_repo(repo)
        payload = run_scan(repo)
        categories = {item["id"]: item["state"] for item in payload["categories"]}
        assert payload["overall_verdict"] == "watch", payload["overall_verdict"]
        assert categories["skip-retry-governance"] == "watch", categories
        assert categories["mock-discipline"] == "watch", categories
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def assert_not_applicable_case() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="test-quality-na-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        setup_not_applicable_repo(repo)
        payload = run_scan(repo)
        assert payload["overall_verdict"] == "not-applicable", payload["overall_verdict"]
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def main() -> int:
    assert_clean_case()
    assert_placeholder_case()
    assert_mock_skip_case()
    assert_not_applicable_case()
    print("Test-quality fixture regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
