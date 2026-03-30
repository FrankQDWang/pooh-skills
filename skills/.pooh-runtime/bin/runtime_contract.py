#!/usr/bin/env python3
"""Shared runtime contract helpers for pooh-skills."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

SCHEMA_VERSION = "2.0"
BOOTSTRAP_BLOCKED_EXIT = 10
RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = RUNTIME_ROOT / "assets" / "tool-registry.json"
PY_TOOLCHAIN_DIR = RUNTIME_ROOT / "python-toolchain"
NODE_TOOLCHAIN_DIR = RUNTIME_ROOT / "node-toolchain"
PY_BIN_DIR = PY_TOOLCHAIN_DIR / ".venv" / "bin"
NODE_BIN_DIR = NODE_TOOLCHAIN_DIR / "node_modules" / ".bin"
DOCS_BIN_DIR = RUNTIME_ROOT / "bin"
DOWNLOAD_DIR = DOCS_BIN_DIR / ".downloads"
INSTALL_LOCK_PATH = RUNTIME_ROOT / ".install.lock"

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "coverage",
    ".repo-harness",
    "vendor",
    "target",
    "out",
    ".idea",
    ".vscode",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}

MANIFEST_FILES = {
    "package.json",
    "pnpm-lock.yaml",
    "pyproject.toml",
    "uv.lock",
    "README.md",
}

FEATURE_BLOCKED_BY_NETWORK = {"mcp-context7"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared runtime contract helpers for pooh-skills.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="Run preflight and bootstrap one skill manifest.")
    bootstrap.add_argument("--skill-id", required=True)
    bootstrap.add_argument("--manifest", required=True)
    bootstrap.add_argument("--repo", required=True)
    bootstrap.add_argument("--state", required=True)
    bootstrap.add_argument("--summary-path", required=True)
    bootstrap.add_argument("--report-path", required=True)
    bootstrap.add_argument("--agent-brief-path", required=True)

    bootstrap_shared = subparsers.add_parser("bootstrap-shared", help="Bootstrap a shared tool/runtime union.")
    bootstrap_shared.add_argument("--repo", required=True)
    bootstrap_shared.add_argument("--out-json", required=True)
    bootstrap_shared.add_argument("--manifest", action="append", default=[])

    update = subparsers.add_parser("update-sidecar", help="Update a runtime sidecar.")
    update.add_argument("--state", required=True)
    update.add_argument("--stage", required=False)
    update.add_argument("--dependency-status", required=False)
    update.add_argument("--current-action", required=False)
    update.add_argument("--summary-path", required=False)
    update.add_argument("--report-path", required=False)
    update.add_argument("--agent-brief-path", required=False)

    inject = subparsers.add_parser("inject-summary", help="Inject dependency contract fields into a summary.")
    inject.add_argument("--state", required=True)
    inject.add_argument("--summary", required=True)

    blocked = subparsers.add_parser("blocked-artifacts", help="Generate blocked summary/report/brief.")
    blocked.add_argument("--skill-id", required=True)
    blocked.add_argument("--repo", required=True)
    blocked.add_argument("--state", required=True)
    blocked.add_argument("--summary-path", required=True)
    blocked.add_argument("--report-path", required=True)
    blocked.add_argument("--agent-brief-path", required=True)

    finalize = subparsers.add_parser("finalize-sidecar", help="Finalize a runtime sidecar from a summary.")
    finalize.add_argument("--state", required=True)
    finalize.add_argument("--summary", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def repo_profile(repo: Path) -> dict[str, Any]:
    languages: set[str] = set()
    manifests: set[str] = set()
    files_scanned = 0
    python_files = 0
    ts_files = 0
    js_files = 0
    docs_roots: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [item for item in dirnames if item not in SKIP_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            files_scanned += 1
            if filename in MANIFEST_FILES:
                manifests.add(filename)
            suffix = path.suffix.lower()
            language = LANGUAGE_BY_SUFFIX.get(suffix)
            if language:
                languages.add(language)
                if language == "python":
                    python_files += 1
                elif language == "typescript":
                    ts_files += 1
                elif language == "javascript":
                    js_files += 1
            if suffix in {".md", ".mdx", ".rst"}:
                try:
                    docs_roots.add(str(path.parent.relative_to(repo)))
                except ValueError:
                    docs_roots.add(str(path.parent))

    package_managers: list[str] = []
    if "pnpm-lock.yaml" in manifests:
        package_managers.append("pnpm")
    if "package.json" in manifests:
        package_managers.append("node")
    if "uv.lock" in manifests:
        package_managers.append("uv")
    if "pyproject.toml" in manifests:
        package_managers.append("python")

    return {
        "repo_root": str(repo.resolve()),
        "languages": sorted(languages),
        "manifests": sorted(manifests),
        "package_managers": package_managers,
        "files_scanned": files_scanned,
        "python_files": python_files,
        "ts_files": ts_files,
        "js_files": js_files,
        "docs_roots": sorted(item for item in docs_roots if item not in {"."}),
    }


def default_sidecar(skill_id: str, repo: Path, summary_path: Path, report_path: Path, agent_brief_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": skill_id,
        "repo_root": str(repo.resolve()),
        "generated_at": utc_now(),
        "stage": "preflight",
        "dependency_status": "ready",
        "current_action": "Running runtime preflight.",
        "bootstrap_actions": [],
        "dependency_failures": [],
        "summary_path": str(summary_path.resolve()),
        "report_path": str(report_path.resolve()),
        "agent_brief_path": str(agent_brief_path.resolve()),
    }


def load_manifest(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload.get("runtime_features"), list):
        raise ValueError(f"{path} missing runtime_features list")
    if not isinstance(payload.get("tools"), list):
        raise ValueError(f"{path} missing tools list")
    return {
        "skill": str(payload.get("skill") or path.parent.parent.name),
        "runtime_features": [str(item) for item in payload.get("runtime_features") or []],
        "tools": [str(item) for item in payload.get("tools") or []],
    }


def load_registry() -> dict[str, Any]:
    return load_json(REGISTRY_PATH)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def classify_failure(text: str) -> tuple[bool, bool, bool]:
    lower = text.lower()
    blocked_by_permissions = any(token in lower for token in ("permission denied", "operation not permitted", "eacces", "not writable"))
    blocked_by_network = any(token in lower for token in ("could not resolve", "name or service not known", "network", "timed out", "connection refused", "temporary failure"))
    blocked_by_security = any(
        token in lower
        for token in (
            "blocked",
            "forbidden",
            "security",
            "policy",
            "certificate",
            "tls",
            "ssl",
            "externally-managed-environment",
            "externally managed",
            "pep 668",
        )
    )
    return blocked_by_security, blocked_by_permissions, blocked_by_network


def detect_target(spec: dict[str, Any]) -> bool:
    detect_type = spec.get("type")
    if detect_type == "env_flag":
        return str(os.environ.get(str(spec.get("env") or ""), "")).lower() in {"1", "true", "yes", "on"}
    if detect_type == "http_reachable":
        url = str(spec.get("url") or "")
        if not url:
            return False
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=float(spec.get("timeout_seconds", 5))) as response:
                return response.status < 500
        except (urllib.error.URLError, TimeoutError, ValueError):
            return False
    if detect_type == "env_or_http":
        return detect_target({"type": "env_flag", "env": spec.get("env")}) or detect_target({
            "type": "http_reachable",
            "url": spec.get("url"),
            "timeout_seconds": spec.get("timeout_seconds", 5),
        })
    return False


def run_command(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env or os.environ.copy(),
        )
    except FileNotFoundError as exc:
        return False, str(exc)
    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part).strip()
    if completed.returncode == 0:
        return True, output or "command completed successfully"
    return False, output or f"command exited with code {completed.returncode}"


@contextlib.contextmanager
def install_lock() -> Any:
    INSTALL_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INSTALL_LOCK_PATH, "a+", encoding="utf-8") as handle:
        acquired = False
        while not acquired:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                acquired = True
            except BlockingIOError:
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def platform_key() -> str | None:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        arch = "arm64"
    elif machine in {"x86_64", "amd64"}:
        arch = "x64"
    else:
        return None
    if sys.platform.startswith("darwin"):
        return f"darwin-{arch}"
    if sys.platform.startswith("linux"):
        return f"linux-{arch}"
    return None


def resolve_tool_path(tool_id: str, registry: dict[str, Any]) -> Path:
    entry = registry["tools"][tool_id]
    binary = entry["binary_names"][0]
    ecosystem = entry["ecosystem"]
    if ecosystem == "python":
        return PY_BIN_DIR / binary
    if ecosystem == "node":
        return NODE_BIN_DIR / binary
    if ecosystem == "docs":
        return DOCS_BIN_DIR / binary
    raise ValueError(f"unsupported ecosystem for {tool_id}: {ecosystem}")


def command_output(command: list[str], cwd: Path) -> tuple[bool, str]:
    return run_command(command, cwd)


def tool_version_matches(tool_id: str, registry: dict[str, Any]) -> tuple[bool, str]:
    entry = registry["tools"][tool_id]
    tool_path = resolve_tool_path(tool_id, registry)
    if not tool_path.exists():
        return False, "tool binary does not exist in shared runtime"
    command = [str(tool_path), *[str(item) for item in entry.get("version_args") or ["--version"]]]
    success, output = command_output(command, RUNTIME_ROOT)
    if not success:
        return False, output
    expected = str(entry.get("version_match") or "").strip()
    if expected and expected not in output:
        return False, f"expected version marker {expected!r} but saw {output!r}"
    return True, output


def bootstrap_actions_entry(name: str, kind: str, status: str, command: list[str], details: str) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "status": status,
        "command": shlex.join(command),
        "details": details,
    }


def ensure_base_prerequisites(required_ecosystems: set[str]) -> tuple[set[str], list[dict[str, Any]]]:
    registry = load_registry()
    failures: list[dict[str, Any]] = []
    ready: set[str] = set()
    for ecosystem in sorted(required_ecosystems):
        if ecosystem not in {"python", "node"}:
            ready.add(ecosystem)
            continue
        missing = []
        for command in registry.get("base_prerequisites", {}).get(ecosystem, []):
            if not command_exists(command):
                missing.append(command)
        if missing:
            for command in missing:
                failures.append({
                    "name": command,
                    "kind": "host-prerequisite",
                    "required_for": f"{ecosystem}-toolchain",
                    "attempted_command": "",
                    "failure_reason": f"Required host prerequisite `{command}` is unavailable.",
                    "blocked_by_security": False,
                    "blocked_by_permissions": False,
                    "blocked_by_network": False,
                })
            continue
        ready.add(ecosystem)
    return ready, failures


def ensure_python_toolchain(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    PY_TOOLCHAIN_DIR.mkdir(parents=True, exist_ok=True)
    command = ["uv", "sync", "--project", str(PY_TOOLCHAIN_DIR), "--locked", "--only-group", "audit"]
    success, output = run_command(command, PY_TOOLCHAIN_DIR)
    actions.append(bootstrap_actions_entry("python-toolchain", "toolchain", "installed" if success else "failed", command, output))
    if success:
        return []
    blocked_by_security, blocked_by_permissions, blocked_by_network = classify_failure(output)
    return [{
        "name": "python-toolchain",
        "kind": "toolchain",
        "required_for": "python-audits",
        "attempted_command": shlex.join(command),
        "failure_reason": output,
        "blocked_by_security": blocked_by_security,
        "blocked_by_permissions": blocked_by_permissions,
        "blocked_by_network": blocked_by_network,
    }]


def ensure_node_toolchain(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    NODE_TOOLCHAIN_DIR.mkdir(parents=True, exist_ok=True)
    command = ["pnpm", "install", "--dir", str(NODE_TOOLCHAIN_DIR), "--frozen-lockfile"]
    success, output = run_command(command, NODE_TOOLCHAIN_DIR)
    actions.append(bootstrap_actions_entry("node-toolchain", "toolchain", "installed" if success else "failed", command, output))
    if success:
        return []
    blocked_by_security, blocked_by_permissions, blocked_by_network = classify_failure(output)
    return [{
        "name": "node-toolchain",
        "kind": "toolchain",
        "required_for": "typescript-audits",
        "attempted_command": shlex.join(command),
        "failure_reason": output,
        "blocked_by_security": blocked_by_security,
        "blocked_by_permissions": blocked_by_permissions,
        "blocked_by_network": blocked_by_network,
    }]


def install_docs_tool(tool_id: str, registry: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entry = registry["tools"][tool_id]
    tool_path = resolve_tool_path(tool_id, registry)
    version_ok, version_output = tool_version_matches(tool_id, registry)
    if version_ok:
        actions.append(bootstrap_actions_entry(tool_id, "docs-binary", "ready", [str(tool_path), "--version"], version_output))
        return []

    spec = entry["download"]
    key = platform_key()
    asset_name = (spec.get("assets") or {}).get(key or "")
    if not asset_name:
        return [{
            "name": tool_id,
            "kind": "docs-binary",
            "required_for": tool_id,
            "attempted_command": "",
            "failure_reason": f"No official release asset is defined for platform {platform.system()} {platform.machine()}",
            "blocked_by_security": False,
            "blocked_by_permissions": False,
            "blocked_by_network": False,
        }]

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{spec['owner']}/{spec['repo']}/releases/download/{spec['tag']}/{asset_name}"
    archive_path = DOWNLOAD_DIR / asset_name
    request = urllib.request.Request(url, headers={"User-Agent": "pooh-skills-runtime"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            archive_path.write_bytes(response.read())
    except Exception as exc:
        message = str(exc)
        blocked_by_security, blocked_by_permissions, blocked_by_network = classify_failure(message)
        actions.append(bootstrap_actions_entry(tool_id, "docs-binary", "failed", ["download", url], message))
        return [{
            "name": tool_id,
            "kind": "docs-binary",
            "required_for": tool_id,
            "attempted_command": f"download {url}",
            "failure_reason": message,
            "blocked_by_security": blocked_by_security,
            "blocked_by_permissions": blocked_by_permissions,
            "blocked_by_network": blocked_by_network or True,
        }]

    try:
        with TemporaryDirectory(prefix=f"{tool_id}-extract-") as temp_dir:
            temp_root = Path(temp_dir)
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(temp_root)
            extracted = temp_root / str(spec["binary_path"])
            if not extracted.exists():
                candidates = list(temp_root.rglob(str(spec["binary_path"])))
                if candidates:
                    extracted = candidates[0]
            if not extracted.exists():
                raise FileNotFoundError(f"Could not locate {spec['binary_path']} inside {asset_name}")
            DOCS_BIN_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(extracted, tool_path)
            tool_path.chmod(0o755)
    except Exception as exc:
        message = str(exc)
        blocked_by_security, blocked_by_permissions, blocked_by_network = classify_failure(message)
        actions.append(bootstrap_actions_entry(tool_id, "docs-binary", "failed", ["extract", str(archive_path)], message))
        return [{
            "name": tool_id,
            "kind": "docs-binary",
            "required_for": tool_id,
            "attempted_command": f"extract {archive_path}",
            "failure_reason": message,
            "blocked_by_security": blocked_by_security,
            "blocked_by_permissions": blocked_by_permissions,
            "blocked_by_network": blocked_by_network,
        }]

    ok, output = tool_version_matches(tool_id, registry)
    actions.append(bootstrap_actions_entry(tool_id, "docs-binary", "installed" if ok else "failed", [str(tool_path), "--version"], output))
    if ok:
        return []
    blocked_by_security, blocked_by_permissions, blocked_by_network = classify_failure(output)
    return [{
        "name": tool_id,
        "kind": "docs-binary",
        "required_for": tool_id,
        "attempted_command": f"{tool_path} --version",
        "failure_reason": output,
        "blocked_by_security": blocked_by_security,
        "blocked_by_permissions": blocked_by_permissions,
        "blocked_by_network": blocked_by_network,
    }]


def verify_required_tools(required_tools: list[str], registry: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for tool_id in required_tools:
        ok, output = tool_version_matches(tool_id, registry)
        if ok:
            continue
        failures.append({
            "name": tool_id,
            "kind": "tool",
            "required_for": tool_id,
            "attempted_command": f"{resolve_tool_path(tool_id, registry)} --version",
            "failure_reason": output,
            "blocked_by_security": False,
            "blocked_by_permissions": False,
            "blocked_by_network": False,
        })
    return failures


def bootstrap_requirement_union(repo: Path, required_tools: list[str], runtime_features: list[str]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    registry = load_registry()
    tool_registry = registry.get("tools") or {}
    feature_registry = registry.get("runtime_features") or {}
    actions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for feature_name in runtime_features:
        feature = feature_registry.get(feature_name)
        if not feature:
            failures.append({
                "name": feature_name,
                "kind": "runtime-feature",
                "required_for": feature_name,
                "attempted_command": "",
                "failure_reason": f"Runtime feature `{feature_name}` is not defined in the shared registry.",
                "blocked_by_security": False,
                "blocked_by_permissions": False,
                "blocked_by_network": False,
            })
            continue
        if detect_target(feature.get("detect") or {}):
            continue
        failures.append({
            "name": feature_name,
            "kind": feature.get("kind") or "runtime-feature",
            "required_for": feature.get("required_for") or feature_name,
            "attempted_command": "",
            "failure_reason": feature.get("failure_reason") or "required runtime capability is unavailable on this host",
            "blocked_by_security": False,
            "blocked_by_permissions": False,
            "blocked_by_network": feature_name in FEATURE_BLOCKED_BY_NETWORK,
        })

    valid_tools: list[str] = []
    for tool_id in required_tools:
        if tool_id not in tool_registry:
            failures.append({
                "name": tool_id,
                "kind": "tool",
                "required_for": tool_id,
                "attempted_command": "",
                "failure_reason": f"Tool `{tool_id}` is not defined in the shared tool registry.",
                "blocked_by_security": False,
                "blocked_by_permissions": False,
                "blocked_by_network": False,
            })
            continue
        valid_tools.append(tool_id)

    required_ecosystems = {tool_registry[tool_id]["ecosystem"] for tool_id in valid_tools}
    ready_ecosystems, prerequisite_failures = ensure_base_prerequisites(required_ecosystems)
    failures.extend(prerequisite_failures)

    with install_lock():
        verifiable_tools: list[str] = []

        if "python" in ready_ecosystems:
            python_failures = ensure_python_toolchain(actions)
            failures.extend(python_failures)
            if python_failures:
                ready_ecosystems.discard("python")
            else:
                verifiable_tools.extend([tool_id for tool_id in valid_tools if tool_registry[tool_id]["ecosystem"] == "python"])

        if "node" in ready_ecosystems:
            node_failures = ensure_node_toolchain(actions)
            failures.extend(node_failures)
            if node_failures:
                ready_ecosystems.discard("node")
            else:
                verifiable_tools.extend([tool_id for tool_id in valid_tools if tool_registry[tool_id]["ecosystem"] == "node"])

        for tool_id in valid_tools:
            if tool_registry[tool_id]["ecosystem"] == "docs":
                docs_failures = install_docs_tool(tool_id, registry, actions)
                failures.extend(docs_failures)
                if not docs_failures:
                    verifiable_tools.append(tool_id)

        failures.extend(verify_required_tools(verifiable_tools, registry))

    dependency_status = "auto-installed" if any(action["status"] == "installed" for action in actions) else "ready"
    if failures:
        return "blocked", actions, failures
    return dependency_status, actions, failures


def bootstrap(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest).resolve())
    repo = Path(args.repo).resolve()
    state_path = Path(args.state).resolve()
    summary_path = Path(args.summary_path).resolve()
    report_path = Path(args.report_path).resolve()
    brief_path = Path(args.agent_brief_path).resolve()
    sidecar = default_sidecar(args.skill_id, repo, summary_path, report_path, brief_path)
    write_json_atomic(state_path, sidecar)

    sidecar["stage"] = "preflight"
    sidecar["current_action"] = "Checking runtime features and shared toolchain prerequisites."
    write_json_atomic(state_path, sidecar)

    dependency_status, actions, failures = bootstrap_requirement_union(
        repo,
        list(dict.fromkeys(manifest["tools"])),
        list(dict.fromkeys(manifest["runtime_features"])),
    )

    sidecar["bootstrap_actions"] = actions
    sidecar["dependency_failures"] = failures
    sidecar["dependency_status"] = dependency_status
    sidecar["generated_at"] = utc_now()
    if failures:
        sidecar["stage"] = "blocked"
        sidecar["current_action"] = "Shared toolchain bootstrap blocked this skill before the main audit could start."
        write_json_atomic(state_path, sidecar)
        return BOOTSTRAP_BLOCKED_EXIT

    sidecar["stage"] = "running"
    sidecar["current_action"] = "Preflight complete. Shared toolchain is ready."
    write_json_atomic(state_path, sidecar)
    return 0


def bootstrap_shared(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    manifests = [load_manifest(Path(item).resolve()) for item in args.manifest]
    tools: list[str] = []
    runtime_features: list[str] = []
    for manifest in manifests:
        tools.extend(manifest["tools"])
        runtime_features.extend(manifest["runtime_features"])
    dependency_status, actions, failures = bootstrap_requirement_union(repo, list(dict.fromkeys(tools)), list(dict.fromkeys(runtime_features)))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "repo_root": str(repo.resolve()),
        "dependency_status": dependency_status,
        "tools": list(dict.fromkeys(tools)),
        "runtime_features": list(dict.fromkeys(runtime_features)),
        "bootstrap_actions": actions,
        "dependency_failures": failures,
    }
    write_json_atomic(Path(args.out_json).resolve(), payload)
    return BOOTSTRAP_BLOCKED_EXIT if failures else 0


def update_sidecar(args: argparse.Namespace) -> int:
    path = Path(args.state).resolve()
    payload = load_json(path)
    if args.stage is not None:
        payload["stage"] = args.stage
    if args.dependency_status is not None:
        payload["dependency_status"] = args.dependency_status
    if args.current_action is not None:
        payload["current_action"] = args.current_action
    if args.summary_path is not None:
        payload["summary_path"] = str(Path(args.summary_path).resolve())
    if args.report_path is not None:
        payload["report_path"] = str(Path(args.report_path).resolve())
    if args.agent_brief_path is not None:
        payload["agent_brief_path"] = str(Path(args.agent_brief_path).resolve())
    payload["generated_at"] = utc_now()
    write_json_atomic(path, payload)
    print(f"Wrote {path}")
    return 0


def inject_summary(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state).resolve())
    summary_path = Path(args.summary).resolve()
    summary = load_json(summary_path)
    summary["dependency_status"] = state.get("dependency_status") or "ready"
    summary["bootstrap_actions"] = list(state.get("bootstrap_actions") or [])
    summary["dependency_failures"] = list(state.get("dependency_failures") or [])
    write_json_atomic(summary_path, summary)
    print(f"Wrote {summary_path}")
    return 0


def minimal_dependency_failure_finding(kind: str, title: str, summary: str, severity: str = "high") -> dict[str, Any]:
    return {
        "kind": kind,
        "title": title,
        "summary": summary,
        "severity": severity,
    }


def blocked_report_markdown(skill_id: str, repo: Path, state: dict[str, Any]) -> str:
    failures = state.get("dependency_failures") or []
    actions = state.get("bootstrap_actions") or []
    lines = [
        f"# {skill_id} blocked",
        "",
        "- status: `blocked`",
        "- repo: `{}`".format(repo.resolve()),
        "- dependency_status: `blocked`",
        "- current_action: {}".format(state.get("current_action") or "dependency bootstrap failed"),
        "",
        "## Dependency failures",
        "",
    ]
    if failures:
        for item in failures:
            lines.extend(
                [
                    f"- `{item['name']}` ({item['kind']})",
                    f"  required_for: {item['required_for']}",
                    f"  attempted_command: {item['attempted_command'] or '-'}",
                    f"  failure_reason: {item['failure_reason']}",
                ]
            )
    else:
        lines.append("- No failure detail was captured.")
    if actions:
        lines.extend(["", "## Bootstrap actions", ""])
        for action in actions:
            lines.append(f"- [{action['status']}] `{action['command']}`")
    lines.extend(
        [
            "",
            "## What happened",
            "",
            "The skill did not enter its main audit because a required runtime feature or locked shared tool was unavailable after bootstrap attempts.",
        ]
    )
    return "\n".join(lines)


def blocked_brief_markdown(skill_id: str, state: dict[str, Any]) -> str:
    failures = state.get("dependency_failures") or []
    lines = [
        f"# {skill_id} blocked agent brief",
        "",
        "- execution_mode: blocked",
        "- dependency_status: blocked",
        "- do_not_continue_audit: true",
        "",
        "## Failures",
        "",
    ]
    if failures:
        for item in failures:
            lines.extend(
                [
                    f"- name: {item['name']}",
                    f"  kind: {item['kind']}",
                    f"  required_for: {item['required_for']}",
                    f"  attempted_command: {item['attempted_command'] or '-'}",
                    f"  failure_reason: {item['failure_reason']}",
                ]
            )
    else:
        lines.append("- no failure detail captured")
    return "\n".join(lines)


def dependency_audit_blocked_summary(repo: Path, state: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    failure_names = [item["name"] for item in state.get("dependency_failures") or []]
    findings = [{
        "id": "dep-bootstrap-blocked-001",
        "tool": "manual",
        "category": "scan-blocker",
        "severity": "high",
        "confidence": "high",
        "scope": "repo",
        "title": "Shared toolchain bootstrap blocked the audit before graph tooling could run",
        "evidence_summary": "Required audit tooling or a runtime prerequisite was unavailable and shared bootstrap did not succeed.",
        "decision": "fix-config",
        "recommended_change_shape": "Restore the blocked prerequisites and rerun the dependency audit before trusting any boundary verdict.",
        "validation_checks": ["Make sure the blocked toolchain and prerequisites bootstrap cleanly on the host."],
        "autofix_allowed": False,
        "notes": ", ".join(failure_names) or "dependency bootstrap blocked the scan",
    }]
    return {
        "repo_profile": {
            "languages": list(profile["languages"]),
            "monorepo_shape": "unknown",
            "package_managers": list(profile["package_managers"]),
            "source_roots": [],
            "workspace_roots": [],
            "major_blockers": [item["failure_reason"] for item in state.get("dependency_failures") or []],
            "notes": ["Shared toolchain bootstrap blocked before the main audit could start."],
        },
        "tool_coverage": {
            "chosen_tools": [{
                "tool": "manual",
                "rationale": "Shared bootstrap blocked the skill before any graph tool could run.",
            }],
            "skipped_tools": [
                {"tool": item["name"], "reason": item["failure_reason"]}
                for item in state.get("dependency_failures") or []
                if item["name"] in {"tach", "dependency-cruiser", "knip", "python-toolchain", "node-toolchain"}
            ],
        },
        "overall_verdict": "scan-blocked",
        "findings": findings,
        "immediate_actions": ["Fix blocked prerequisites before running dependency governance."],
        "next_actions": [],
        "later_actions": [],
        "safe_automation": [],
        "avoid_now": ["Do not trust boundary conclusions while required tooling is blocked."],
        "assumptions": [],
    }


def contract_blocked_summary(skill: str, repo: Path, state: dict[str, Any], profile: dict[str, Any], *, overall_verdict: str, gate_names: list[str]) -> dict[str, Any]:
    failures = state.get("dependency_failures") or []
    gates = [
        {
            "gate": gate,
            "state": "unverified",
            "severity": "high",
            "confidence": "high",
            "summary": "Shared toolchain bootstrap blocked the skill before this gate could be audited.",
        }
        for gate in gate_names
    ]
    findings = [{
        "id": f"{skill}-bootstrap-blocked-001",
        "domain": "repo",
        "gate": gate_names[0],
        "severity": "high",
        "confidence": "high",
        "current_state": "unverified",
        "target_state": "enforced" if skill == "signature-contract-hardgate" else "sound",
        "title": "Shared toolchain bootstrap blocked the audit before gate evidence could be collected",
        "evidence_summary": "A required tool or runtime feature was unavailable after bootstrap attempts.",
        "decision": "defer",
        "change_shape": "Restore the blocked prerequisite, rerun the audit, then judge domain gates from fresh evidence.",
        "validation": "Prove the shared bootstrap succeeds and rerun the skill.",
        "merge_gate": "warn-only",
        "autofix_allowed": False,
        "notes": ", ".join(item["name"] for item in failures) or "bootstrap blocked the run",
    }]
    repo_profile = {
        "languages": list(profile["languages"]),
        "shape": "unknown",
        "notes": ["Shared toolchain bootstrap blocked before the main audit could start."],
    }
    if skill == "signature-contract-hardgate":
        repo_profile["contract_surface"] = []
        repo_profile["api_schema_sources"] = []
        return {
            "repo_profile": repo_profile,
            "overall_verdict": overall_verdict,
            "gate_states": gates,
            "findings": findings,
            "assumptions": [],
            "unverified": [item["failure_reason"] for item in failures],
            "immediate_actions": ["Restore blocked prerequisites before trusting contract gates."],
            "next_actions": [],
            "later_actions": [],
        }
    repo_profile["workflow_surface"] = []
    repo_profile["agent_surface"] = []
    repo_profile["docs_surface"] = []
    return {
        "repo_profile": repo_profile,
        "overall_verdict": overall_verdict,
        "gate_states": gates,
        "findings": findings,
        "wrong_rules": [],
        "unverified": [item["failure_reason"] for item in failures],
    }


def simple_findings_blocked_summary(skill: str, repo: Path, state: dict[str, Any], profile: dict[str, Any], *, summary_line: str, overall_verdict: str) -> dict[str, Any]:
    failures = state.get("dependency_failures") or []
    return {
        "schema_version": "1.0",
        "skill": skill,
        "generated_at": utc_now(),
        "repo_root": str(repo.resolve()),
        "overall_verdict": overall_verdict,
        "summary_line": summary_line,
        "coverage": {
            "files_scanned": int(profile["files_scanned"]),
            "relevant_files": 0,
            "relevant_signals": 0,
        },
        "severity_counts": {
            "critical": 0,
            "high": 1 if failures else 0,
            "medium": 0,
            "low": 0,
        },
        "scan_blockers": [item["failure_reason"] for item in failures],
        "findings": [{
            "id": f"{skill}-bootstrap-blocked-001",
            "category": "scan-blocker",
            "severity": "high",
            "confidence": "high",
            "title": "Shared toolchain bootstrap blocked the audit before runtime evidence could be collected",
            "path": ".",
            "line": 1,
            "evidence": [item["failure_reason"] for item in failures] or ["dependency bootstrap blocked the run"],
            "recommendation": "Restore the blocked prerequisite and rerun this audit before trusting any verdict.",
            "merge_gate": "block-now",
            "notes": ", ".join(item["name"] for item in failures),
        }],
    }


def pythonic_blocked_summary(repo: Path, state: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    failures = state.get("dependency_failures") or []
    return {
        "schema_version": "1.0",
        "skill": "pythonic-ddd-drift-audit",
        "generated_at": utc_now(),
        "repo_root": str(repo.resolve()),
        "overall_verdict": "watch",
        "summary_line": "Shared toolchain bootstrap blocked the Pythonic drift audit before it could inspect the repo.",
        "coverage": {
            "files_scanned": int(profile["files_scanned"]),
            "python_files": int(profile["python_files"]),
            "domain_files": 0,
        },
        "severity_counts": {
            "critical": 0,
            "high": 1 if failures else 0,
            "medium": 0,
            "low": 0,
        },
        "scan_blockers": [item["failure_reason"] for item in failures],
        "findings": [{
            "id": "py-drift-bootstrap-blocked-001",
            "category": "scan-blocker",
            "severity": "high",
            "confidence": "high",
            "title": "Shared toolchain bootstrap blocked the Pythonic DDD drift audit",
            "path": ".",
            "line": 1,
            "evidence": [item["failure_reason"] for item in failures] or ["dependency bootstrap blocked the run"],
            "recommendation": "Restore the blocked prerequisite and rerun the audit.",
            "merge_gate": "block-now",
            "notes": ", ".join(item["name"] for item in failures),
        }],
    }


def error_governance_blocked_summary(repo: Path, state: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    failures = state.get("dependency_failures") or []
    return {
        "schema_version": "1.0.0",
        "skill": "error-governance-hardgate",
        "generated_at": utc_now(),
        "repo_root": str(repo.resolve()),
        "overall_verdict": "blocked",
        "summary_line": "Shared runtime bootstrap blocked the error-governance audit before contract evidence could be collected.",
        "language_profile": {
            "languages": list(profile["languages"]),
            "frameworks": [],
            "protocols": [],
        },
        "coverage": {
            "files_scanned": int(profile["files_scanned"]),
            "relevant_files": 0,
            "openapi_surfaces": 0,
            "asyncapi_surfaces": 0,
            "catalogs_found": 0,
            "generated_type_surfaces": 0,
        },
        "severity_counts": {
            "critical": 0,
            "high": 1 if failures else 0,
            "medium": 0,
            "low": 0,
        },
        "gate_states": [
            {
                "name": gate,
                "status": "unverified",
                "severity_bias": "high",
                "summary": "Shared bootstrap blocked this gate before trustworthy evidence could be collected.",
            }
            for gate in (
                "universal-problem-shape",
                "stable-business-codes",
                "protocol-alignment",
                "boundary-safety",
                "ssot-and-codegen",
            )
        ],
        "scan_blockers": [item["failure_reason"] for item in failures],
        "findings": [{
            "id": "egh-bootstrap-blocked-001",
            "category": "scan-blocker",
            "severity": "high",
            "confidence": "high",
            "scope": "repo",
            "title": "Shared runtime bootstrap blocked error-governance evidence collection",
            "path": ".",
            "line": 1,
            "evidence_summary": "; ".join(item["failure_reason"] for item in failures) or "dependency bootstrap blocked the run",
            "decision": "restore-runtime",
            "recommended_change_shape": "Restore the blocked prerequisite, rerun the audit, and only then trust public error-contract conclusions.",
            "validation_checks": ["Make sure shared runtime bootstrap succeeds before rerunning the error-governance wrapper."],
            "merge_gate": "block-now",
            "notes": ", ".join(item["name"] for item in failures),
        }],
        "top_actions": ["Restore the blocked prerequisite before treating this skill as a source of truth."],
    }


def overdefensive_blocked_summary(repo: Path, state: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    failures = state.get("dependency_failures") or []
    return {
        "schema_version": "1.0.0",
        "skill": "overdefensive-silent-failure-hardgate",
        "generated_at": utc_now(),
        "repo_root": str(repo.resolve()),
        "overall_verdict": "scan-blocked",
        "summary_line": "Shared runtime bootstrap blocked the silent-failure audit before executable evidence could be collected.",
        "coverage": {
            "files_scanned": int(profile["files_scanned"]),
            "python_files": int(profile["python_files"]),
            "ts_files": int(profile["ts_files"]),
            "js_files": int(profile["js_files"]),
        },
        "severity_counts": {
            "critical": 0,
            "high": 1 if failures else 0,
            "medium": 0,
            "low": 0,
        },
        "category_counts": {"scan-blocker": 1} if failures else {},
        "scan_blockers": [item["failure_reason"] for item in failures],
        "findings": [{
            "id": "osf-bootstrap-blocked-001",
            "category": "scan-blocker",
            "severity": "high",
            "confidence": "high",
            "language": "mixed",
            "title": "Shared runtime bootstrap blocked silent-failure evidence collection",
            "path": ".",
            "line": 1,
            "evidence": [item["failure_reason"] for item in failures] or ["dependency bootstrap blocked the run"],
            "recommendation": "Restore the blocked prerequisite and rerun the audit before trusting fail-loud conclusions.",
            "merge_gate": "block-now",
            "notes": ", ".join(item["name"] for item in failures),
        }],
    }


def cleanup_blocked_summary(repo: Path, state: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    failures = state.get("dependency_failures") or []
    return {
        "repo_root": str(repo.resolve()),
        "generated_at": utc_now(),
        "repo_profile": {
            "languages": list(profile["languages"]),
            "manifests": list(profile["manifests"]),
            "docs_roots": list(profile["docs_roots"]),
            "tool_hints": [],
        },
        "counts": {
            "total": 1,
            "by_category": {"scan-blocker": 1},
        },
        "findings": [{
            "category": "scan-blocker",
            "severity": "high",
            "confidence": "high",
            "path": ".",
            "line": 1,
            "language": None,
            "summary": "Shared toolchain bootstrap blocked the removal-readiness audit before any evidence could be collected.",
            "cue": None,
            "replacement": None,
            "removal_target": None,
            "evidence": [item["failure_reason"] for item in failures] or ["dependency bootstrap blocked the run"],
        }],
        "notes": [", ".join(item["name"] for item in failures) or "dependency bootstrap blocked the run"],
    }


def llm_blocked_summary(repo: Path, state: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill": "llm-api-freshness-guard",
        "version": "2.0.0",
        "generated_at": utc_now(),
        "audit_mode": "blocked",
        "target_scope": "repo",
        "repo_profile": {
            "repo_root": str(repo.resolve()),
            "files_scanned": int(profile["files_scanned"]),
            "languages": list(profile["languages"]),
            "package_managers": list(profile["package_managers"]),
            "surface_count": 0,
            "wrapper_count": 0,
            "provider_count": 0,
        },
        "surface_resolution": [],
        "doc_verification": [],
        "findings": [],
        "priorities": {
            "now": ["Restore the blocked runtime feature or dependency before trusting any LLM API freshness verdict."],
            "next": ["Rerun the official verified audit after the blocked prerequisite is restored."],
            "later": ["Make provider / wrapper ownership more explicit so future freshness audits resolve faster."],
        },
        "scan_limitations": ["Official freshness verification was blocked before a trustworthy doc-backed result could be produced."],
    }


def build_blocked_summary(skill_id: str, repo: Path, state: dict[str, Any]) -> dict[str, Any]:
    profile = repo_profile(repo)
    if skill_id == "dependency-audit":
        return dependency_audit_blocked_summary(repo, state, profile)
    if skill_id == "signature-contract-hardgate":
        return contract_blocked_summary(
            skill_id,
            repo,
            state,
            profile,
            overall_verdict="soft-gates",
            gate_names=[
                "contract-surface",
                "compile-time-gates",
                "runtime-boundary-validation",
                "error-contract",
                "escape-hatch-governance",
                "architecture-boundaries",
                "contract-tests",
                "merge-governance",
            ],
        )
    if skill_id == "pydantic-ai-temporal-hardgate":
        return contract_blocked_summary(
            skill_id,
            repo,
            state,
            profile,
            overall_verdict="paper-guardrails",
            gate_names=[
                "workflow-determinism",
                "sandbox-discipline",
                "durable-agent-path",
                "agent-freeze-drift",
                "tool-contracts",
                "dependency-contracts",
                "validation-retry-path",
                "verification-harness",
                "doc-grounding",
                "merge-governance",
            ],
        )
    if skill_id == "distributed-side-effect-hardgate":
        return simple_findings_blocked_summary(
            "distributed-side-effect-hardgate",
            repo,
            state,
            profile,
            summary_line="Shared toolchain bootstrap blocked the distributed side-effect audit before it could inspect event paths.",
            overall_verdict="watch",
        )
    if skill_id == "error-governance-hardgate":
        return error_governance_blocked_summary(repo, state, profile)
    if skill_id == "overdefensive-silent-failure-hardgate":
        return overdefensive_blocked_summary(repo, state, profile)
    if skill_id == "pythonic-ddd-drift-audit":
        return pythonic_blocked_summary(repo, state, profile)
    if skill_id == "controlled-cleanup-hardgate":
        return cleanup_blocked_summary(repo, state, profile)
    if skill_id == "llm-api-freshness-guard":
        return llm_blocked_summary(repo, state, profile)
    if skill_id == "repo-health-orchestrator":
        failures = state.get("dependency_failures") or []
        return {
            "schema_version": "1.0",
            "skill": "repo-health-orchestrator",
            "generated_at": utc_now(),
            "repo_root": str(repo.resolve()),
            "overall_health": "blocked",
            "coverage_status": "partial",
            "summary_line": "Shared bootstrap blocked repo-health orchestration before child audits could start.",
            "skill_runs": [],
            "top_actions": ["Restore blocked orchestrator runtime features and shared prerequisites before retrying the fleet audit."],
            "missing_skills": [],
            "invalid_summaries": [],
            "dependency_status": "blocked",
            "bootstrap_actions": list(state.get("bootstrap_actions") or []),
            "dependency_failures": failures,
        }
    raise ValueError(f"unsupported blocked summary skill: {skill_id}")


def blocked_artifacts(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    state_path = Path(args.state).resolve()
    state = load_json(state_path)
    summary = build_blocked_summary(args.skill_id, repo, state)
    summary["dependency_status"] = "blocked"
    summary["bootstrap_actions"] = list(state.get("bootstrap_actions") or [])
    summary["dependency_failures"] = list(state.get("dependency_failures") or [])
    summary_path = Path(args.summary_path).resolve()
    report_path = Path(args.report_path).resolve()
    brief_path = Path(args.agent_brief_path).resolve()

    write_json_atomic(summary_path, summary)
    write_text(report_path, blocked_report_markdown(args.skill_id, repo, state))
    write_text(brief_path, blocked_brief_markdown(args.skill_id, state))

    state["stage"] = "blocked"
    state["dependency_status"] = "blocked"
    state["current_action"] = "Blocked artifacts written."
    state["generated_at"] = utc_now()
    write_json_atomic(state_path, state)
    print(f"Wrote {summary_path}")
    return 0


def extract_child_verdict(summary: dict[str, Any]) -> str:
    for key in ("overall_verdict", "overall_health", "audit_mode", "mode", "status"):
        value = summary.get(key)
        if isinstance(value, str):
            return value
    return ""


def finalize_sidecar(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    state = load_json(state_path)
    summary = load_json(Path(args.summary).resolve())
    dependency_status = str(summary.get("dependency_status") or state.get("dependency_status") or "ready")
    child_verdict = extract_child_verdict(summary)
    if dependency_status == "blocked":
        state["stage"] = "blocked"
        state["current_action"] = "Blocked summary finalized."
    elif child_verdict == "not-applicable":
        state["stage"] = "not-applicable"
        state["current_action"] = "Main audit finished as not applicable."
    else:
        state["stage"] = "complete"
        state["current_action"] = "Main audit completed successfully."
    state["dependency_status"] = dependency_status
    state["generated_at"] = utc_now()
    write_json_atomic(state_path, state)
    print(f"Wrote {state_path}")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "bootstrap":
        return bootstrap(args)
    if args.command == "bootstrap-shared":
        return bootstrap_shared(args)
    if args.command == "update-sidecar":
        return update_sidecar(args)
    if args.command == "inject-summary":
        return inject_summary(args)
    if args.command == "blocked-artifacts":
        return blocked_artifacts(args)
    if args.command == "finalize-sidecar":
        return finalize_sidecar(args)
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
