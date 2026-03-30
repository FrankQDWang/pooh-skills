#!/usr/bin/env python3
"""Sync canonical shared skill references into each skill-local references directory."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
SHARED_DIR = REPO_ROOT / "shared"
CANONICAL_MAP = {
    "output-contract.md": "shared-output-contract.md",
    "reporting-style.md": "shared-reporting-style.md",
    "runtime-artifact-contract.md": "shared-runtime-artifact-contract.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync shared canonical docs into each skill references directory.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    return parser.parse_args()


def generated_content(source_name: str, content: str) -> str:
    return (
        "<!-- GENERATED FILE. Edit shared/{name} and run "
        "`python3 scripts/sync_shared_skill_refs.py --write`. -->\n\n{body}".format(
            name=source_name,
            body=content.rstrip() + "\n",
        )
    )


def file_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    failures: list[str] = []
    for skill_dir in sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir() and (path / "SKILL.md").exists()):
        references_dir = skill_dir / "references"
        references_dir.mkdir(parents=True, exist_ok=True)
        for source_name, target_name in CANONICAL_MAP.items():
            source_path = SHARED_DIR / source_name
            target_path = references_dir / target_name
            expected = generated_content(source_name, source_path.read_text(encoding="utf-8"))
            if target_path.exists():
                actual = target_path.read_text(encoding="utf-8")
            else:
                actual = ""
            if args.check:
                if file_digest(actual) != file_digest(expected):
                    failures.append(f"{target_path} is out of sync with {source_path}")
            else:
                target_path.write_text(expected, encoding="utf-8")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


args = parse_args()

if __name__ == "__main__":
    raise SystemExit(main())
