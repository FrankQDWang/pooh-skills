#!/usr/bin/env python3
"""Regression coverage for legacy scanners that now use first-party surface classification."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Case:
    name: str
    script_rel: str
    expected_verdict: str | None
    files: dict[str, str]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_case(case: Case) -> dict:
    tempdir = Path(tempfile.mkdtemp(prefix=f"{case.name}-"))
    try:
        repo = tempdir / "repo"
        out_dir = repo / ".repo-harness"
        summary = out_dir / "summary.json"
        report = out_dir / "report.md"
        brief = out_dir / "agent-brief.md"
        repo.mkdir(parents=True, exist_ok=True)

        for relative_path, content in case.files.items():
            write(repo / relative_path, content)

        command = [
            "python3",
            str(REPO_ROOT / case.script_rel),
            "--repo",
            str(repo),
        ]
        if "module-shape-hardgate" in case.script_rel:
            command.extend(["--out-dir", str(out_dir)])
        else:
            command.extend(
                [
                    "--out",
                    str(summary),
                    "--report-out",
                    str(report),
                    "--agent-brief-out",
                    str(brief),
                ]
            )
        if "module-shape-hardgate" in case.script_rel:
            summary = out_dir / "module-shape-hardgate-summary.json"
            report = out_dir / "module-shape-hardgate-report.md"
            brief = out_dir / "module-shape-hardgate-agent-brief.md"

        completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(f"{case.name}: scan failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")

        payload = json.loads(summary.read_text(encoding="utf-8"))
        if case.expected_verdict and payload.get("overall_verdict") != case.expected_verdict:
            raise RuntimeError(
                f"{case.name}: expected overall_verdict={case.expected_verdict}, got {payload.get('overall_verdict')}"
            )
        if any(str(item.get("path") or "").startswith(".council-runtime/") for item in payload.get("findings", [])):
            raise RuntimeError(f"{case.name}: foreign runtime path leaked into findings")
        if ".council-runtime/" in (payload.get("summary_line") or ""):
            raise RuntimeError(f"{case.name}: summary_line leaked foreign runtime path")
        report_text = report.read_text(encoding="utf-8")
        brief_text = brief.read_text(encoding="utf-8")
        if ".council-runtime/" in report_text or ".council-runtime/" in brief_text:
            raise RuntimeError(f"{case.name}: report output leaked foreign runtime path")
        return payload
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def main() -> int:
    cases = [
        Case(
            name="pythonic-ddd-foreign-runtime",
            script_rel="skills/pythonic-ddd-drift-audit/scripts/run_py_drift_scan.py",
            expected_verdict=None,
            files={
                "pyproject.toml": "[project]\nname = 'fixture'\nversion = '0.1.0'\n",
                "main.py": "def main() -> None:\n    pass\n",
                "contexts/orders/domain/model.py": "class Order:\n    pass\n",
                ".council-runtime/home/.local/share/uv/tools/noise/site-packages/runtime/contexts/billing/domain/model.py": (
                    "from fastapi import APIRouter\n\nrouter = APIRouter()\n"
                ),
            },
        ),
        Case(
            name="distributed-side-effect-foreign-runtime",
            script_rel="skills/distributed-side-effect-hardgate/scripts/run_side_effect_scan.py",
            expected_verdict="not-applicable",
            files={
                "src/app.py": "def greet(name: str) -> str:\n    return f'hi {name}'\n",
                ".council-runtime/home/.local/share/uv/tools/noise/site-packages/runtime/worker.py": (
                    "def publish_order(session, requests):\n"
                    "    requests.post('https://example.com')\n"
                    "    session.commit()\n"
                ),
            },
        ),
    ]

    for case in cases:
        payload = run_case(case)
        surface_note = str(payload.get("surface_note") or "")
        if "foreign-runtime excluded" not in surface_note:
            raise RuntimeError(f"{case.name}: expected surface note to mention foreign-runtime exclusion")

    print("Legacy surface fixture regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
