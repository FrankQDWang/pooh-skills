#!/usr/bin/env python3
"""Validate the single-entry Codex plugin bundle and public plugin docs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PLUGIN_SKILLS = {"repo-health-orchestrator"}

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
FORBIDDEN_PUBLIC_DOC_PATTERNS = (
    "scripts/install.sh --all",
    "./scripts/install.sh",
    "--target codex",
)
REQUIRED_PUBLIC_INSTALL_FILES = (
    "scripts/install_home_local_plugin.sh",
    "scripts/uninstall_home_local_plugin.sh",
    "scripts/manage_home_local_plugin.py",
)
REQUIRED_README_INSTALL_PATTERNS = (
    "bash scripts/install_home_local_plugin.sh",
    "bash scripts/uninstall_home_local_plugin.sh",
)


@dataclass
class CheckError:
    path: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the single-entry Codex plugin bundle.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--json-out", default=None, help="Optional JSON output path.")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(read_text(path))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def should_skip(path: Path) -> bool:
    if path.name in SKIP_DIR_NAMES or path.name in SKIP_FILE_NAMES:
        return True
    if path.suffix in SKIP_FILE_SUFFIXES:
        return True
    return False


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if should_skip(path):
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.is_file():
            yield path


def bundle_skill_names(skills_dir: Path) -> set[str]:
    names: set[str] = set()
    if not skills_dir.exists():
        return names
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            names.add(child.name)
    return names


def subtree_hashes(root: Path, include_children: set[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for child_name in sorted(include_children):
        child = root / child_name
        if not child.exists():
            continue
        for path in iter_files(child):
            files[str(path.relative_to(root))] = sha256(path)
    return files


def validate_manifest(plugin_manifest: Path, errors: list[CheckError]) -> None:
    if not plugin_manifest.exists():
        errors.append(CheckError(str(plugin_manifest), "Missing plugin manifest."))
        return
    try:
        manifest = read_json(plugin_manifest)
    except Exception as exc:
        errors.append(CheckError(str(plugin_manifest), f"plugin.json must be valid JSON: {exc}"))
        return

    required_top = {
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "skills",
        "interface",
    }
    missing_top = sorted(required_top - set(manifest))
    if missing_top:
        errors.append(CheckError(str(plugin_manifest), f"plugin.json missing top-level keys: {', '.join(missing_top)}."))
        return

    if manifest.get("name") != "pooh-skills":
        errors.append(CheckError(str(plugin_manifest), "plugin.json `name` must equal `pooh-skills`."))
    if manifest.get("skills") != "./skills/":
        errors.append(CheckError(str(plugin_manifest), "plugin.json `skills` must equal `./skills/`."))
    if manifest.get("license") != "UNLICENSED":
        errors.append(CheckError(str(plugin_manifest), "plugin.json `license` must currently be `UNLICENSED`."))

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append(CheckError(str(plugin_manifest), "`interface` must be an object."))
        return

    required_interface = {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "websiteURL",
        "defaultPrompt",
        "brandColor",
    }
    missing_interface = sorted(required_interface - set(interface))
    if missing_interface:
        errors.append(CheckError(str(plugin_manifest), f"plugin.json `interface` missing keys: {', '.join(missing_interface)}."))
        return

    if interface.get("displayName") != "Pooh Skills":
        errors.append(CheckError(str(plugin_manifest), "plugin displayName must be `Pooh Skills`."))
    if interface.get("category") != "Productivity":
        errors.append(CheckError(str(plugin_manifest), "plugin category must be `Productivity`."))
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or len(prompts) != 3:
        errors.append(CheckError(str(plugin_manifest), "`interface.defaultPrompt` must contain exactly 3 prompts."))
    elif any("$repo-health-orchestrator" not in str(prompt) for prompt in prompts):
        errors.append(CheckError(str(plugin_manifest), "Every starter prompt must point users to `$repo-health-orchestrator`."))


def validate_no_repo_marketplace(marketplace_path: Path, errors: list[CheckError]) -> None:
    if marketplace_path.exists():
        errors.append(CheckError(str(marketplace_path), "Repo-local marketplace.json must not exist in the single-entry home-local model."))


def validate_bundle(
    source_skills_dir: Path,
    plugin_skills_dir: Path,
    internal_skills_dir: Path,
    errors: list[CheckError],
) -> None:
    if not source_skills_dir.is_dir():
        errors.append(CheckError(str(source_skills_dir), "Missing source skills directory."))
        return
    if not plugin_skills_dir.is_dir():
        errors.append(CheckError(str(plugin_skills_dir), "Missing public plugin bundle skills directory."))
        return
    if not internal_skills_dir.is_dir():
        errors.append(CheckError(str(internal_skills_dir), "Missing internal plugin bundle skills directory."))
        return

    source_skill_names = bundle_skill_names(source_skills_dir)
    public_skill_names = bundle_skill_names(plugin_skills_dir)
    if public_skill_names != PUBLIC_PLUGIN_SKILLS:
        errors.append(
            CheckError(
                str(plugin_skills_dir),
                f"Public plugin skill set must be exactly {sorted(PUBLIC_PLUGIN_SKILLS)}; found {sorted(public_skill_names)}",
            )
        )
    expected_internal_names = source_skill_names - PUBLIC_PLUGIN_SKILLS
    internal_skill_names = bundle_skill_names(internal_skills_dir)
    if internal_skill_names != expected_internal_names:
        errors.append(
            CheckError(
                str(internal_skills_dir),
                f"Internal plugin skill set drifted. expected={sorted(expected_internal_names)} bundle={sorted(internal_skill_names)}",
            )
        )
    if not (internal_skills_dir / ".pooh-runtime").is_dir():
        errors.append(CheckError(str(internal_skills_dir / ".pooh-runtime"), "Internal plugin bundle must include `.pooh-runtime`."))

    source_public_files = subtree_hashes(source_skills_dir, PUBLIC_PLUGIN_SKILLS)
    plugin_public_files = {
        str(path.relative_to(plugin_skills_dir)): sha256(path)
        for path in iter_files(plugin_skills_dir)
    }
    source_internal_files = subtree_hashes(source_skills_dir, expected_internal_names | {".pooh-runtime"})
    plugin_internal_files = {
        str(path.relative_to(internal_skills_dir)): sha256(path)
        for path in iter_files(internal_skills_dir)
    }

    compare_file_maps(source_public_files, plugin_public_files, plugin_skills_dir, errors, "Public bundle")
    compare_file_maps(source_internal_files, plugin_internal_files, internal_skills_dir, errors, "Internal bundle")

    for path in sorted(plugin_skills_dir.rglob("__pycache__")):
        errors.append(CheckError(str(path), "Public plugin bundle must not contain `__pycache__` directories."))
    for path in sorted(plugin_skills_dir.rglob("*.pyc")):
        errors.append(CheckError(str(path), "Public plugin bundle must not contain `.pyc` files."))
    for path in sorted(internal_skills_dir.rglob("__pycache__")):
        errors.append(CheckError(str(path), "Internal plugin bundle must not contain `__pycache__` directories."))
    for path in sorted(internal_skills_dir.rglob("*.pyc")):
        errors.append(CheckError(str(path), "Internal plugin bundle must not contain `.pyc` files."))


def compare_file_maps(
    source_files: dict[str, str],
    plugin_files: dict[str, str],
    target_root: Path,
    errors: list[CheckError],
    label: str,
) -> None:
    missing_from_bundle = sorted(set(source_files) - set(plugin_files))
    extra_in_bundle = sorted(set(plugin_files) - set(source_files))
    mismatched = sorted(
        relative
        for relative in set(source_files) & set(plugin_files)
        if source_files[relative] != plugin_files[relative]
    )

    for relative in missing_from_bundle[:20]:
        errors.append(CheckError(str(target_root / relative), f"{label} is missing source file `{relative}`."))
    for relative in extra_in_bundle[:20]:
        errors.append(CheckError(str(target_root / relative), f"{label} has stale extra file `{relative}`."))
    for relative in mismatched[:20]:
        errors.append(CheckError(str(target_root / relative), f"{label} file `{relative}` is out of sync with source."))


def public_doc_paths(repo_root: Path) -> Iterable[Path]:
    candidates = [repo_root / "README.md"]
    candidates.extend(
        path
        for path in sorted(repo_root.glob("*.md"))
        if path.name != "README.md"
    )
    candidates.append(repo_root / "plugins" / "pooh-skills" / ".codex-plugin" / "plugin.json")
    return candidates


def validate_docs(repo_root: Path, errors: list[CheckError]) -> None:
    for path in public_doc_paths(repo_root):
        if not path.exists():
            errors.append(CheckError(str(path), "Missing expected public plugin document."))
            continue
        text = read_text(path)
        for pattern in FORBIDDEN_PUBLIC_DOC_PATTERNS:
            if pattern in text:
                errors.append(CheckError(str(path), f"Public plugin surface still contains legacy skill-install pattern `{pattern}`."))

    for relative in REQUIRED_PUBLIC_INSTALL_FILES:
        path = repo_root / relative
        if not path.exists():
            errors.append(CheckError(str(path), "Missing public home-local plugin install file."))
            continue
        if path.suffix == ".sh" and not os.access(path, os.X_OK):
            errors.append(CheckError(str(path), "Public install shell scripts must be executable."))

    readme_path = repo_root / "README.md"
    if readme_path.exists():
        readme_text = read_text(readme_path)
        for pattern in REQUIRED_README_INSTALL_PATTERNS:
            if pattern not in readme_text:
                errors.append(CheckError(str(readme_path), f"README must document `{pattern}`."))
        for forbidden in (
            "repo-local plugin",
            "repo-local Codex plugin",
        ):
            if forbidden in readme_text:
                errors.append(CheckError(str(readme_path), f"README must not describe legacy `{forbidden}` flow."))


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    plugin_root = repo / "plugins" / "pooh-skills"
    plugin_manifest = plugin_root / ".codex-plugin" / "plugin.json"
    plugin_skills_dir = plugin_root / "skills"
    internal_skills_dir = plugin_root / "internal-skills"
    source_skills_dir = repo / "skills"
    marketplace_path = repo / ".agents" / "plugins" / "marketplace.json"

    errors: list[CheckError] = []
    validate_manifest(plugin_manifest, errors)
    validate_no_repo_marketplace(marketplace_path, errors)
    validate_bundle(source_skills_dir, plugin_skills_dir, internal_skills_dir, errors)
    validate_docs(repo, errors)

    payload = {
        "repo_root": str(repo),
        "error_count": len(errors),
        "errors": [{"path": error.path, "message": error.message} for error in errors],
    }
    if args.json_out:
        out_path = Path(args.json_out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if errors:
        for error in errors:
            print(f"{error.path}: {error.message}", file=sys.stderr)
        return 1

    print("Single-entry plugin bundle is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
