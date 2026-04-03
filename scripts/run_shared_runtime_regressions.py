#!/usr/bin/env python3
"""Regression coverage for shared runtime probe and finalize behavior."""

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
RUNTIME_BIN = REPO_ROOT / "skills" / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN))

from runtime_contract import load_registry, tool_check_command, tool_check_matches  # noqa: E402


def assert_ajv_probe() -> None:
    registry = load_registry()
    command = tool_check_command("ajv-cli", registry)
    if command[-1] == "--version":
        raise RuntimeError("ajv-cli probe regressed to --version")
    ok, output, resolved = tool_check_matches("ajv-cli", registry)
    if not ok:
        raise RuntimeError(f"ajv-cli probe failed unexpectedly: {' '.join(resolved)}\n{output}")
    if resolved[-1] != "help":
        raise RuntimeError(f"ajv-cli probe should use help, got: {' '.join(resolved)}")
    if "Validate data file(s) against schema" not in output:
        raise RuntimeError("ajv-cli probe output did not include the expected help text")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def assert_finalize_rejects_missing_artifacts() -> None:
    tempdir = Path(tempfile.mkdtemp(prefix="runtime-finalize-"))
    try:
        repo = tempdir / "repo"
        harness = repo / ".repo-harness"
        repo.mkdir(parents=True, exist_ok=True)
        harness.mkdir(parents=True, exist_ok=True)
        write(repo / "pyproject.toml", "[project]\nname = 'fixture'\nversion = '0.1.0'\n")
        write(repo / "src" / "service.py", "def greet(name: str) -> str:\n    return f'hi {name}'\n")
        write(repo / "package.json", "{\n  \"name\": \"fixture\",\n  \"private\": true\n}\n")

        env = os.environ.copy()
        env["POOH_RUN_ID"] = "shared-runtime-regression"
        env["POOH_SKILLS_RUN_ID"] = "shared-runtime-regression"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        wrapper = REPO_ROOT / "skills" / "signature-contract-hardgate" / "scripts" / "run_all.sh"
        completed = subprocess.run(
            ["bash", str(wrapper), str(repo), str(harness)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if completed.returncode not in {0, 1}:
            raise RuntimeError(
                f"signature wrapper failed unexpectedly\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )

        child_dir = harness / "skills" / "signature-contract-hardgate"
        state_path = child_dir / "runtime.json"
        summary_path = child_dir / "summary.json"
        report_path = child_dir / "report.md"
        if not state_path.exists() or not summary_path.exists() or not report_path.exists():
            raise RuntimeError("signature wrapper did not materialize the baseline child artifacts")

        report_path.unlink()
        finalize = subprocess.run(
            [
                "python3",
                str(RUNTIME_BIN / "runtime_contract.py"),
                "finalize-sidecar",
                "--state",
                str(state_path),
                "--summary",
                str(summary_path),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if finalize.returncode == 0:
            raise RuntimeError("finalize-sidecar accepted a missing report artifact")
        runtime = json.loads(state_path.read_text(encoding="utf-8"))
        if runtime.get("stage") != "invalid":
            raise RuntimeError(f"runtime stage should flip to invalid, got {runtime.get('stage')!r}")
        if "report artifact missing" not in str(runtime.get("current_action") or ""):
            raise RuntimeError("runtime invalid reason did not mention the missing report artifact")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def main() -> int:
    assert_ajv_probe()
    assert_finalize_rejects_missing_artifacts()
    print("Shared runtime regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
