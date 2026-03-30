#!/usr/bin/env python3
"""Validate the repo-local Codex plugin bundle and public plugin docs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]

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
    "~/.codex/skills",
    "scripts/install.sh --all",
    "./scripts/install.sh",
    "--target codex",
)


@dataclass
class CheckError:
    path: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the repo-local Codex plugin bundle.")
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
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            names.add(child.name)
    return names


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


def validate_marketplace(marketplace_path: Path, errors: list[CheckError]) -> None:
    if not marketplace_path.exists():
        errors.append(CheckError(str(marketplace_path), "Missing repo-local marketplace.json."))
        return
    try:
        marketplace = read_json(marketplace_path)
    except Exception as exc:
        errors.append(CheckError(str(marketplace_path), f"marketplace.json must be valid JSON: {exc}"))
        return

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        errors.append(CheckError(str(marketplace_path), "`plugins` must be an array."))
        return

    entry = next((item for item in plugins if isinstance(item, dict) and item.get("name") == "pooh-skills"), None)
    if entry is None:
        errors.append(CheckError(str(marketplace_path), "marketplace.json must contain a `pooh-skills` plugin entry."))
        return

    source = entry.get("source") or {}
    policy = entry.get("policy") or {}
    if source.get("source") != "local" or source.get("path") != "./plugins/pooh-skills":
        errors.append(CheckError(str(marketplace_path), "pooh-skills marketplace entry must point to `./plugins/pooh-skills`."))
    if policy.get("installation") != "AVAILABLE":
        errors.append(CheckError(str(marketplace_path), "marketplace policy.installation must be `AVAILABLE`."))
    if policy.get("authentication") != "ON_INSTALL":
        errors.append(CheckError(str(marketplace_path), "marketplace policy.authentication must be `ON_INSTALL`."))
    if entry.get("category") != "Productivity":
        errors.append(CheckError(str(marketplace_path), "marketplace category must be `Productivity`."))


def validate_bundle(source_skills_dir: Path, plugin_skills_dir: Path, errors: list[CheckError]) -> None:
    if not source_skills_dir.is_dir():
        errors.append(CheckError(str(source_skills_dir), "Missing source skills directory."))
        return
    if not plugin_skills_dir.is_dir():
        errors.append(CheckError(str(plugin_skills_dir), "Missing plugin bundle skills directory."))
        return

    source_skill_names = bundle_skill_names(source_skills_dir)
    plugin_skill_names = bundle_skill_names(plugin_skills_dir)
    if source_skill_names != plugin_skill_names:
        errors.append(
            CheckError(
                str(plugin_skills_dir),
                f"Plugin skill set drifted. source={sorted(source_skill_names)} bundle={sorted(plugin_skill_names)}",
            )
        )
    if not (plugin_skills_dir / ".pooh-runtime").is_dir():
        errors.append(CheckError(str(plugin_skills_dir / ".pooh-runtime"), "Plugin bundle must include `.pooh-runtime`."))

    source_files = {
        str(path.relative_to(source_skills_dir)): sha256(path)
        for path in iter_files(source_skills_dir)
    }
    plugin_files = {
        str(path.relative_to(plugin_skills_dir)): sha256(path)
        for path in iter_files(plugin_skills_dir)
    }

    missing_from_bundle = sorted(set(source_files) - set(plugin_files))
    extra_in_bundle = sorted(set(plugin_files) - set(source_files))
    mismatched = sorted(
        relative
        for relative in set(source_files) & set(plugin_files)
        if source_files[relative] != plugin_files[relative]
    )

    for relative in missing_from_bundle[:20]:
        errors.append(CheckError(str(plugin_skills_dir / relative), f"Bundle is missing source file `{relative}`."))
    for relative in extra_in_bundle[:20]:
        errors.append(CheckError(str(plugin_skills_dir / relative), f"Bundle has stale extra file `{relative}`."))
    for relative in mismatched[:20]:
        errors.append(CheckError(str(plugin_skills_dir / relative), f"Bundle file `{relative}` is out of sync with source."))

    for path in sorted(plugin_skills_dir.rglob("__pycache__")):
        errors.append(CheckError(str(path), "Plugin bundle must not contain `__pycache__` directories."))
    for path in sorted(plugin_skills_dir.rglob("*.pyc")):
        errors.append(CheckError(str(path), "Plugin bundle must not contain `.pyc` files."))


def public_doc_paths(repo_root: Path) -> Iterable[Path]:
    candidates = [repo_root / "README.md"]
    candidates.extend(
        path
        for path in sorted(repo_root.glob("*.md"))
        if path.name != "README.md"
    )
    candidates.append(repo_root / ".agents" / "plugins" / "marketplace.json")
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


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    plugin_root = repo / "plugins" / "pooh-skills"
    plugin_manifest = plugin_root / ".codex-plugin" / "plugin.json"
    plugin_skills_dir = plugin_root / "skills"
    source_skills_dir = repo / "skills"
    marketplace_path = repo / ".agents" / "plugins" / "marketplace.json"

    errors: list[CheckError] = []
    validate_manifest(plugin_manifest, errors)
    validate_marketplace(marketplace_path, errors)
    validate_bundle(source_skills_dir, plugin_skills_dir, errors)
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

    print("Repo-local plugin bundle is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
