#!/usr/bin/env python3
"""Materialize the repo-local Codex plugin bundle from the root skill fleet."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILLS_DIR = REPO_ROOT / "skills"
PLUGIN_ROOT = REPO_ROOT / "plugins" / "pooh-skills"
TARGET_SKILLS_DIR = PLUGIN_ROOT / "skills"

SKIP_DIR_NAMES = {
    "__pycache__",
    ".repo-harness",
    ".venv",
    "node_modules",
    ".downloads",
}
SKIP_FILE_NAMES = {
    ".DS_Store",
    ".install.lock",
    "lychee",
    "vale",
}
SKIP_FILE_SUFFIXES = {
    ".pyc",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync root skills into the repo-local Codex plugin bundle.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    return parser.parse_args()


def should_skip(path: Path) -> bool:
    if path.name in SKIP_DIR_NAMES or path.name in SKIP_FILE_NAMES:
        return True
    if path.suffix in SKIP_FILE_SUFFIXES:
        return True
    return False


def copy_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in sorted(source.iterdir()):
        if should_skip(child):
            continue
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(
                child,
                destination,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".repo-harness",
                    ".venv",
                    "node_modules",
                    ".downloads",
                    ".DS_Store",
                    ".install.lock",
                    "lychee",
                    "vale",
                ),
                copy_function=shutil.copy2,
                dirs_exist_ok=False,
            )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, destination)


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo).resolve()
    source_skills_dir = repo_root / SOURCE_SKILLS_DIR.relative_to(REPO_ROOT)
    plugin_root = repo_root / PLUGIN_ROOT.relative_to(REPO_ROOT)
    target_skills_dir = plugin_root / "skills"

    if not source_skills_dir.is_dir():
        raise SystemExit(f"Missing source skills directory: {source_skills_dir}")
    if not plugin_root.is_dir():
        raise SystemExit(f"Missing plugin root: {plugin_root}")

    if target_skills_dir.exists():
        shutil.rmtree(target_skills_dir)

    copy_tree(source_skills_dir, target_skills_dir)
    print(f"Synchronized plugin bundle -> {target_skills_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
