#!/usr/bin/env python3
"""Bootstrap the shared pooh-runtime toolchain for the full audit fleet."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from repo_health_catalog import DOMAIN_SPECS
from repo_health_catalog import manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap the shared toolchain for all repo-health child skills.")
    parser.add_argument("--repo", required=True, help="Target repository root to audit.")
    parser.add_argument("--out-json", required=True, help="Path to write the shared bootstrap result JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    orchestrator_dir = script_dir.parent
    skills_dir = orchestrator_dir.parent
    runtime_bin = skills_dir / ".pooh-runtime" / "bin" / "runtime_contract.py"

    manifests = [manifest_path(skills_dir, spec.domain) for spec in DOMAIN_SPECS]
    command = [
        "python3",
        str(runtime_bin),
        "bootstrap-shared",
        "--repo",
        str(Path(args.repo).resolve()),
        "--out-json",
        str(Path(args.out_json).resolve()),
    ]
    for path in manifests:
        command.extend(["--manifest", str(path.resolve())])

    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        stream = sys.stdout if completed.returncode == 0 else sys.stderr
        print(completed.stderr, end="", file=stream)

    if completed.returncode not in {0, 10}:
        return completed.returncode

    out_path = Path(args.out_json).resolve()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    payload["domains"] = [
        {
            "domain": spec.domain,
            "skill_name": spec.skill_name,
            "manifest_path": str(manifest_path(skills_dir, spec.domain).resolve()),
        }
        for spec in DOMAIN_SPECS
    ]
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
