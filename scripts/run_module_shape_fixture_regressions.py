#!/usr/bin/env python3
"""Deterministic regression fixtures for module-shape-hardgate."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO_ROOT / "skills" / "module-shape-hardgate" / "scripts"
SCAN_SCRIPT = SKILL_SCRIPTS / "run_module_shape_scan.py"
VALIDATE_SCRIPT = SKILL_SCRIPTS / "validate_module_shape_summary.py"
SUMMARY_NAME = "module-shape-hardgate-summary.json"


def run_case(name: str, files: dict[str, str]) -> dict:
    tmpdir = Path(tempfile.mkdtemp(prefix=f"module-shape-{name}-"))
    try:
        repo_dir = tmpdir / "repo"
        out_dir = tmpdir / "out"
        repo_dir.mkdir(parents=True, exist_ok=True)
        for relative_path, content in files.items():
            target = repo_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        subprocess.run(
            [
                "python3",
                str(SCAN_SCRIPT),
                "--repo",
                str(repo_dir),
                "--out-dir",
                str(out_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
        )
        subprocess.run(
            [
                "python3",
                str(VALIDATE_SCRIPT),
                "--summary",
                str(out_dir / SUMMARY_NAME),
            ],
            check=True,
            cwd=REPO_ROOT,
        )
        return json.loads((out_dir / SUMMARY_NAME).read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def build_python_false_positive_fixture() -> str:
    long_body = "\n".join(f"    value_{idx} = {idx}" for idx in range(470))
    exports = "\n\n".join(
        f"def export_{idx:02d}():\n    return {idx}"
        for idx in range(30)
    )
    return (
        "import argparse\n"
        "from pydantic import BaseModel\n\n"
        "next_actions = []\n"
        "component_count = 0\n\n"
        "class Payload(BaseModel):\n"
        "    value: int\n\n"
        "def long_orchestration():\n"
        "    total = 0\n"
        f"{long_body}\n"
        "    return total\n\n"
        f"{exports}\n"
    )


def build_positive_ui_fixture() -> str:
    long_body = "\n".join(f"  const line{idx} = {idx};" for idx in range(470))
    exports = "\n".join(f"export const widget{idx:02d} = {idx};" for idx in range(30))
    return (
        'import React, { useState } from "react";\n'
        'import { z } from "zod";\n\n'
        "const DashboardSchema = z.object({ count: z.number() });\n\n"
        "export function Dashboard() {\n"
        "  const [count, setCount] = useState(0);\n"
        "  void setCount;\n"
        f"{long_body}\n"
        "  return <div>{count}</div>;\n"
        "}\n\n"
        f"{exports}\n"
    )


def assert_syntax_error_case() -> None:
    summary = run_case("syntax-error", {"bad.py": "def broken(:\n    pass\n"})
    if summary["overall_verdict"] != "scan-blocked":
        raise RuntimeError(f"syntax-error: expected scan-blocked, got {summary['overall_verdict']}")
    if not any(f["category"] == "scan-blocker" for f in summary["findings"]):
        raise RuntimeError("syntax-error: expected at least one scan-blocker finding")


def assert_ui_false_positive_case() -> None:
    summary = run_case("ui-false-positive", {"services/analyzer.py": build_python_false_positive_fixture()})
    god_modules = [f for f in summary["findings"] if f["category"] == "god-module"]
    if not god_modules:
        raise RuntimeError("ui-false-positive: expected a god-module finding for the oversized fixture")
    tags = god_modules[0]["metrics"].get("responsibility_tags", [])
    if "ui" in tags:
        raise RuntimeError(f"ui-false-positive: unexpected ui responsibility tag in {tags}")
    if any(f["category"] == "mixed-responsibility" for f in summary["findings"]):
        raise RuntimeError("ui-false-positive: raw identifier text should not create mixed-responsibility evidence")


def assert_positive_ui_case() -> None:
    summary = run_case("positive-ui", {"src/components/dashboard.tsx": build_positive_ui_fixture()})
    god_modules = [f for f in summary["findings"] if f["category"] == "god-module"]
    if not god_modules:
        raise RuntimeError("positive-ui: expected a god-module finding for the oversized TSX fixture")
    tags = god_modules[0]["metrics"].get("responsibility_tags", [])
    if "ui" not in tags:
        raise RuntimeError(f"positive-ui: expected ui responsibility tag in {tags}")


def assert_foreign_runtime_noise_case() -> None:
    summary = run_case(
        "foreign-runtime-noise",
        {
            "src/service.py": "def greet(name: str) -> str:\n    return f'hi {name}'\n",
            ".council-runtime/home/.local/share/uv/fixture/site-packages/noise/bad.py": "def broken(:\n    pass\n",
        },
    )
    if summary["overall_verdict"] == "scan-blocked":
        raise RuntimeError("foreign-runtime-noise: foreign runtime parse blockers must not block the official verdict")
    if summary["coverage"]["files_scanned"] != 1:
        raise RuntimeError(f"foreign-runtime-noise: expected exactly one first-party file, got {summary['coverage']['files_scanned']}")
    if any(f["path"].startswith(".council-runtime/") for f in summary["findings"]):
        raise RuntimeError("foreign-runtime-noise: foreign runtime path leaked into findings")


def main() -> int:
    assert_syntax_error_case()
    assert_ui_false_positive_case()
    assert_positive_ui_case()
    assert_foreign_runtime_noise_case()
    print("Module-shape fixture regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
