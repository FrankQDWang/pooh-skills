#!/usr/bin/env python3
"""Regression tests for the public home-local plugin install and uninstall flow."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_home_local_plugin.sh"
UNINSTALL_SCRIPT = REPO_ROOT / "scripts" / "uninstall_home_local_plugin.sh"
PLUGIN_TARGET = REPO_ROOT / "plugins" / "pooh-skills"


def run(*args: str) -> None:
    subprocess.run(args, cwd=REPO_ROOT, check=True, text=True, capture_output=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_legacy_skill(home_root: Path, skill_id: str) -> None:
    skill_dir = home_root / ".codex" / "skills" / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"# {skill_id}\n", encoding="utf-8")


def assert_pooh_entry(marketplace: dict) -> None:
    plugins = marketplace.get("plugins", [])
    entry = next((plugin for plugin in plugins if plugin.get("name") == "pooh-skills"), None)
    assert entry is not None, "pooh-skills entry missing from home-local marketplace"
    assert entry["source"] == {"source": "local", "path": "./plugins/pooh-skills"}
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    assert entry["category"] == "Productivity"


def assert_single_entry_bundle(plugin_root: Path) -> None:
    public_skills = sorted(path.parent.name for path in plugin_root.glob("skills/*/SKILL.md"))
    internal_skills = sorted(path.parent.name for path in plugin_root.glob("internal-skills/*/SKILL.md"))
    assert public_skills == ["repo-health-orchestrator"], f"public plugin skills drifted: {public_skills}"
    assert len(internal_skills) == 15, f"internal worker count drifted: {internal_skills}"
    assert "repo-health-orchestrator" not in internal_skills
    assert (plugin_root / "internal-skills" / ".pooh-runtime").is_dir()


def run_existing_marketplace_scenario(temp_root: Path) -> None:
    home_root = temp_root / "existing-home"
    home_root.mkdir(parents=True, exist_ok=True)
    marketplace_path = home_root / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text(
        json.dumps(
            {
                "name": "existing-local",
                "interface": {"displayName": "Existing Local Plugins"},
                "plugins": [
                    {
                        "name": "example-plugin",
                        "source": {"source": "local", "path": "./plugins/example-plugin"},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                        "category": "Productivity",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    seed_legacy_skill(home_root, "dependency-audit")
    seed_legacy_skill(home_root, "repo-health-orchestrator")

    run("bash", str(INSTALL_SCRIPT), "--home", str(home_root))
    installed_plugin = home_root / "plugins" / "pooh-skills"
    assert installed_plugin.is_symlink(), "installer should create a symlink by default"
    assert installed_plugin.resolve() == PLUGIN_TARGET.resolve()
    assert_single_entry_bundle(installed_plugin.resolve())

    marketplace = read_json(marketplace_path)
    assert marketplace["interface"]["displayName"] == "Existing Local Plugins"
    assert any(plugin.get("name") == "example-plugin" for plugin in marketplace["plugins"])
    assert_pooh_entry(marketplace)
    assert not (home_root / ".codex" / "skills" / "dependency-audit").exists()
    assert not (home_root / ".codex" / "skills" / "repo-health-orchestrator").exists()

    run("bash", str(INSTALL_SCRIPT), "--home", str(home_root))
    assert installed_plugin.is_symlink()

    run("bash", str(UNINSTALL_SCRIPT), "--home", str(home_root))
    marketplace_after_uninstall = read_json(marketplace_path)
    assert any(plugin.get("name") == "example-plugin" for plugin in marketplace_after_uninstall["plugins"])
    assert not any(plugin.get("name") == "pooh-skills" for plugin in marketplace_after_uninstall["plugins"])
    assert not installed_plugin.exists()


def run_fresh_home_scenario(temp_root: Path) -> None:
    home_root = temp_root / "fresh-home"
    home_root.mkdir(parents=True, exist_ok=True)

    run("bash", str(INSTALL_SCRIPT), "--home", str(home_root))

    installed_plugin = home_root / "plugins" / "pooh-skills"
    marketplace_path = home_root / ".agents" / "plugins" / "marketplace.json"
    assert installed_plugin.is_symlink()
    assert installed_plugin.resolve() == PLUGIN_TARGET.resolve()
    assert_single_entry_bundle(installed_plugin.resolve())
    marketplace = read_json(marketplace_path)
    assert marketplace["name"].endswith("-local")
    assert marketplace["interface"]["displayName"].endswith("Local Plugins")
    assert_pooh_entry(marketplace)

    run("bash", str(UNINSTALL_SCRIPT), "--home", str(home_root))
    marketplace_after_uninstall = read_json(marketplace_path)
    assert marketplace_after_uninstall["plugins"] == []
    assert not installed_plugin.exists()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pooh-plugin-install-") as temp_dir:
        temp_root = Path(temp_dir)
        run_existing_marketplace_scenario(temp_root)
        run_fresh_home_scenario(temp_root)

    print("Home-local plugin installer regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
