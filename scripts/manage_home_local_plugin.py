#!/usr/bin/env python3
"""Install or uninstall the Pooh Skills plugin in a user's home-local Codex marketplace."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "pooh-skills"
PLUGIN_RELATIVE_PATH = Path("plugins") / PLUGIN_NAME
MARKETPLACE_RELATIVE_PATH = Path(".agents") / "plugins" / "marketplace.json"
LEGACY_SKILLS_RELATIVE_PATH = Path(".codex") / "skills"
CANONICAL_ENTRY = {
    "name": PLUGIN_NAME,
    "source": {
        "source": "local",
        "path": f"./plugins/{PLUGIN_NAME}",
    },
    "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    },
    "category": "Productivity",
}


@dataclass
class OperationResult:
    action: str
    home_root: str
    plugin_path: str
    marketplace_path: str
    install_mode: str | None
    cleaned_legacy_skills: list[str]
    removed_marketplace_entry: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the home-local Pooh Skills Codex plugin.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install the plugin into a home-local Codex marketplace.")
    install.add_argument("--repo", default=str(REPO_ROOT), help="Repository root containing plugins/pooh-skills.")
    install.add_argument("--home", default=str(Path.home()), help="Home directory to install into.")
    install.add_argument(
        "--mode",
        choices=("symlink", "copy"),
        default="symlink",
        help="Install mode for ~/plugins/pooh-skills.",
    )
    install.add_argument(
        "--skip-legacy-cleanup",
        action="store_true",
        help="Do not remove legacy ~/.codex/skills copies for this fleet.",
    )
    install.add_argument(
        "--json-out",
        default=None,
        help="Optional JSON output path for machine-readable install results.",
    )

    uninstall = subparsers.add_parser("uninstall", help="Remove the plugin from a home-local Codex marketplace.")
    uninstall.add_argument("--home", default=str(Path.home()), help="Home directory to uninstall from.")
    uninstall.add_argument(
        "--purge-legacy-skills",
        action="store_true",
        help="Also remove legacy ~/.codex/skills copies for this fleet.",
    )
    uninstall.add_argument("--repo", default=str(REPO_ROOT), help="Repository root used to enumerate legacy skill ids.")
    uninstall.add_argument(
        "--json-out",
        default=None,
        help="Optional JSON output path for machine-readable uninstall results.",
    )

    return parser.parse_args()


def normalize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "local"


def titleize_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("-") if part)


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def canonical_plugin_entry() -> dict:
    return json.loads(json.dumps(CANONICAL_ENTRY))


def default_marketplace(home_root: Path) -> dict:
    username = normalize_slug(os.environ.get("USER") or getpass.getuser() or home_root.name)
    display_name = titleize_slug(username)
    return {
        "name": f"{username}-local",
        "interface": {
            "displayName": f"{display_name} Local Plugins",
        },
        "plugins": [],
    }


def load_marketplace(marketplace_path: Path, home_root: Path) -> dict:
    if not marketplace_path.exists():
        return default_marketplace(home_root)

    try:
        payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exercised by script runtime, not fixtures
        raise RuntimeError(f"Failed to parse marketplace JSON at {marketplace_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"Marketplace file must contain a JSON object: {marketplace_path}")

    if "name" not in payload or not isinstance(payload["name"], str) or not payload["name"].strip():
        payload["name"] = default_marketplace(home_root)["name"]

    interface = payload.get("interface")
    if not isinstance(interface, dict):
        interface = {}
        payload["interface"] = interface
    if "displayName" not in interface or not isinstance(interface["displayName"], str) or not interface["displayName"].strip():
        interface["displayName"] = default_marketplace(home_root)["interface"]["displayName"]

    plugins = payload.get("plugins")
    if plugins is None:
        payload["plugins"] = []
    elif not isinstance(plugins, list):
        raise RuntimeError(f"`plugins` must be an array in marketplace file: {marketplace_path}")

    return payload


def remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def install_plugin_path(repo_plugin_root: Path, home_plugin_root: Path, mode: str) -> None:
    home_plugin_root.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        if home_plugin_root.is_symlink():
            if home_plugin_root.resolve() == repo_plugin_root.resolve():
                return
            home_plugin_root.unlink()
        elif home_plugin_root.exists():
            remove_path(home_plugin_root)
        home_plugin_root.symlink_to(repo_plugin_root, target_is_directory=True)
        return

    if home_plugin_root.exists() or home_plugin_root.is_symlink():
        remove_path(home_plugin_root)
    shutil.copytree(repo_plugin_root, home_plugin_root, symlinks=False)


def enumerate_skill_ids(repo_root: Path) -> list[str]:
    skills_dir = repo_root / "skills"
    ids: list[str] = []
    for child in sorted(skills_dir.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir() and (child / "SKILL.md").exists():
            ids.append(child.name)
    return ids


def cleanup_legacy_skills(home_root: Path, skill_ids: list[str]) -> list[str]:
    legacy_root = home_root / LEGACY_SKILLS_RELATIVE_PATH
    removed: list[str] = []
    for skill_id in skill_ids:
        skill_dir = legacy_root / skill_id
        if skill_dir.exists() or skill_dir.is_symlink():
            remove_path(skill_dir)
            removed.append(skill_id)
    return removed


def upsert_marketplace_entry(marketplace: dict) -> None:
    plugins = list(marketplace.get("plugins", []))
    replacement = canonical_plugin_entry()
    updated = False
    new_plugins: list[dict] = []
    for plugin in plugins:
        if isinstance(plugin, dict) and plugin.get("name") == PLUGIN_NAME:
            new_plugins.append(replacement)
            updated = True
        else:
            new_plugins.append(plugin)
    if not updated:
        new_plugins.append(replacement)
    marketplace["plugins"] = new_plugins


def remove_marketplace_entry(marketplace: dict) -> bool:
    plugins = marketplace.get("plugins", [])
    kept = [plugin for plugin in plugins if not (isinstance(plugin, dict) and plugin.get("name") == PLUGIN_NAME)]
    removed = len(kept) != len(plugins)
    marketplace["plugins"] = kept
    return removed


def verify_repo_plugin(repo_root: Path) -> Path:
    plugin_root = repo_root / PLUGIN_RELATIVE_PATH
    manifest = plugin_root / ".codex-plugin" / "plugin.json"
    skills_dir = plugin_root / "skills"
    if not manifest.exists():
        raise RuntimeError(f"Missing plugin manifest: {manifest}")
    if not skills_dir.is_dir():
        raise RuntimeError(f"Missing plugin skills directory: {skills_dir}")
    return plugin_root


def install(args: argparse.Namespace) -> OperationResult:
    repo_root = Path(args.repo).resolve()
    home_root = Path(args.home).expanduser().resolve()
    repo_plugin_root = verify_repo_plugin(repo_root)
    home_plugin_root = home_root / PLUGIN_RELATIVE_PATH
    marketplace_path = home_root / MARKETPLACE_RELATIVE_PATH

    install_plugin_path(repo_plugin_root, home_plugin_root, args.mode)
    marketplace = load_marketplace(marketplace_path, home_root)
    upsert_marketplace_entry(marketplace)
    atomic_write_json(marketplace_path, marketplace)

    removed_legacy_skills: list[str] = []
    if not args.skip_legacy_cleanup:
        removed_legacy_skills = cleanup_legacy_skills(home_root, enumerate_skill_ids(repo_root))

    return OperationResult(
        action="install",
        home_root=str(home_root),
        plugin_path=str(home_plugin_root),
        marketplace_path=str(marketplace_path),
        install_mode=args.mode,
        cleaned_legacy_skills=removed_legacy_skills,
        removed_marketplace_entry=False,
    )


def uninstall(args: argparse.Namespace) -> OperationResult:
    home_root = Path(args.home).expanduser().resolve()
    repo_root = Path(args.repo).resolve()
    home_plugin_root = home_root / PLUGIN_RELATIVE_PATH
    marketplace_path = home_root / MARKETPLACE_RELATIVE_PATH

    remove_path(home_plugin_root)

    removed_entry = False
    if marketplace_path.exists():
        marketplace = load_marketplace(marketplace_path, home_root)
        removed_entry = remove_marketplace_entry(marketplace)
        atomic_write_json(marketplace_path, marketplace)

    removed_legacy_skills: list[str] = []
    if args.purge_legacy_skills:
        removed_legacy_skills = cleanup_legacy_skills(home_root, enumerate_skill_ids(repo_root))

    return OperationResult(
        action="uninstall",
        home_root=str(home_root),
        plugin_path=str(home_plugin_root),
        marketplace_path=str(marketplace_path),
        install_mode=None,
        cleaned_legacy_skills=removed_legacy_skills,
        removed_marketplace_entry=removed_entry,
    )


def emit_result(result: OperationResult, json_out: str | None) -> None:
    payload = asdict(result)
    if json_out:
        atomic_write_json(Path(json_out).expanduser().resolve(), payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> int:
    args = parse_args()
    try:
        if args.command == "install":
            result = install(args)
        else:
            result = uninstall(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    emit_result(result, args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
