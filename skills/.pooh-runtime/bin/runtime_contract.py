#!/usr/bin/env python3
"""Shared runtime contract helpers for pooh-skills.

This module owns three cross-skill guarantees:

1. A skill may declare installable dependencies and runtime features in a
   machine-readable manifest.
2. Missing installable dependencies are bootstrapped before the main audit.
3. Any blocked bootstrap still produces standard machine-readable artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

SCHEMA_VERSION = "1.0"
BOOTSTRAP_BLOCKED_EXIT = 10
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
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".rs": "rust",
    ".swift": "swift",
}
MANIFEST_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "poetry.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "uv.lock",
    "Pipfile",
    "Pipfile.lock",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared runtime contract helpers for pooh-skills.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="Run preflight and bootstrap dependencies.")
    bootstrap.add_argument("--skill-id", required=True)
    bootstrap.add_argument("--manifest", required=True)
    bootstrap.add_argument("--repo", required=True)
    bootstrap.add_argument("--state", required=True)
    bootstrap.add_argument("--summary-path", required=True)
    bootstrap.add_argument("--report-path", required=True)
    bootstrap.add_argument("--agent-brief-path", required=True)

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
            if suffix in {".md", ".mdx", ".rst"}:
                try:
                    docs_roots.add(str(path.parent.relative_to(repo)))
                except ValueError:
                    docs_roots.add(str(path.parent))

    manifests_list = sorted(manifests)
    package_managers: list[str] = []
    if "pnpm-lock.yaml" in manifests:
        package_managers.append("pnpm")
    if "package-lock.json" in manifests:
        package_managers.append("npm")
    if "yarn.lock" in manifests:
        package_managers.append("yarn")
    if "poetry.lock" in manifests:
        package_managers.append("poetry")
    if "Pipfile.lock" in manifests:
        package_managers.append("pipenv")
    if "requirements.txt" in manifests or "pyproject.toml" in manifests or "uv.lock" in manifests:
        package_managers.append("pip")
    if "uv.lock" in manifests:
        package_managers.append("uv")

    return {
        "repo_root": str(repo.resolve()),
        "languages": sorted(languages),
        "manifests": manifests_list,
        "package_managers": package_managers,
        "files_scanned": files_scanned,
        "python_files": python_files,
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


def required_when_matches(requirement: dict[str, Any], profile: dict[str, Any]) -> bool:
    if not requirement:
        return True
    if requirement.get("always") is True:
        return True
    languages = set(profile["languages"])
    manifests = set(profile["manifests"])
    if requirement.get("languages_any"):
        if not languages.intersection(requirement["languages_any"]):
            return False
    if requirement.get("manifests_any"):
        if not manifests.intersection(requirement["manifests_any"]):
            return False
    if requirement.get("python_min_files") is not None:
        if int(profile.get("python_files", 0) or 0) < int(requirement["python_min_files"]):
            return False
    return True


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def detect_target(spec: dict[str, Any]) -> bool:
    detect_type = spec.get("type")
    if detect_type == "any_command":
        return any(command_exists(command) for command in spec.get("commands") or [])
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
        env_spec = {"type": "env_flag", "env": spec.get("env")}
        if detect_target(env_spec):
            return True
        http_spec = {"type": "http_reachable", "url": spec.get("url"), "timeout_seconds": spec.get("timeout_seconds", 5)}
        return detect_target(http_spec)
    return False


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


def run_install_attempt(command: list[str], repo: Path) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        return False, str(exc)
    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part).strip()
    if completed.returncode == 0:
        return True, output or "installation command completed successfully"
    return False, output or f"command exited with code {completed.returncode}"


def current_platform_tags() -> set[str]:
    tags = {sys.platform}
    if sys.platform.startswith("darwin"):
        tags.add("darwin")
        tags.add("macos")
    elif sys.platform.startswith("linux"):
        tags.add("linux")
    elif sys.platform.startswith(("win32", "cygwin", "msys")):
        tags.add("windows")
    return tags


def install_attempt_matches(attempt: dict[str, Any]) -> bool:
    platforms = attempt.get("platforms")
    if not platforms:
        return True
    platform_tags = current_platform_tags()
    return bool(platform_tags.intersection(str(item).lower() for item in platforms))


def bootstrap(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest).resolve())
    repo = Path(args.repo).resolve()
    state_path = Path(args.state).resolve()
    summary_path = Path(args.summary_path).resolve()
    report_path = Path(args.report_path).resolve()
    brief_path = Path(args.agent_brief_path).resolve()
    profile = repo_profile(repo)
    sidecar = default_sidecar(args.skill_id, repo, summary_path, report_path, brief_path)
    write_json_atomic(state_path, sidecar)

    bootstrap_actions: list[dict[str, Any]] = []
    dependency_failures: list[dict[str, Any]] = []
    installed_any = False

    for feature in manifest.get("runtime_features") or []:
        if not required_when_matches(feature.get("required_when") or {}, profile):
            continue
        detect = feature.get("detect") or {}
        sidecar["stage"] = "preflight"
        sidecar["current_action"] = f"Checking runtime feature: {feature['name']}"
        write_json_atomic(state_path, sidecar)
        if detect_target(detect):
            continue
        dependency_failures.append({
            "name": feature["name"],
            "kind": feature.get("kind") or "runtime-feature",
            "required_for": feature.get("required_for") or args.skill_id,
            "attempted_command": "",
            "failure_reason": feature.get("failure_reason") or "required runtime capability is unavailable on this host",
            "blocked_by_security": False,
            "blocked_by_permissions": False,
            "blocked_by_network": detect.get("type") in {"http_reachable", "env_or_http"},
        })

    for dependency in manifest.get("dependencies") or []:
        if not required_when_matches(dependency.get("required_when") or {}, profile):
            continue
        detect = dependency.get("detect") or {}
        if detect_target(detect):
            continue

        attempts = dependency.get("install_attempts") or []
        sidecar["stage"] = "bootstrapping"
        sidecar["current_action"] = f"Installing dependency: {dependency['name']}"
        write_json_atomic(state_path, sidecar)

        attempt_failures: list[tuple[str, str]] = []
        installed = False
        for attempt in attempts:
            if not install_attempt_matches(attempt):
                continue
            command = [str(item) for item in attempt.get("command") or []]
            if not command:
                continue
            success, output = run_install_attempt(command, repo)
            bootstrap_actions.append({
                "name": dependency["name"],
                "kind": dependency.get("kind") or "dependency",
                "status": "installed" if success else "failed",
                "command": shlex.join(command),
                "details": output,
            })
            sidecar["bootstrap_actions"] = bootstrap_actions
            write_json_atomic(state_path, sidecar)
            if success and detect_target(detect):
                installed = True
                installed_any = True
                break
            attempt_failures.append((shlex.join(command), output))

        if installed:
            continue

        attempted_command = attempt_failures[-1][0] if attempt_failures else ""
        failure_reason = attempt_failures[-1][1] if attempt_failures else "no install attempts were declared"
        blocked_by_security, blocked_by_permissions, blocked_by_network = classify_failure(failure_reason)
        dependency_failures.append({
            "name": dependency["name"],
            "kind": dependency.get("kind") or "dependency",
            "required_for": dependency.get("required_for") or args.skill_id,
            "attempted_command": attempted_command,
            "failure_reason": failure_reason,
            "blocked_by_security": blocked_by_security,
            "blocked_by_permissions": blocked_by_permissions,
            "blocked_by_network": blocked_by_network,
        })

    if dependency_failures:
        sidecar["stage"] = "blocked"
        sidecar["dependency_status"] = "blocked"
        sidecar["current_action"] = "Dependency bootstrap blocked this skill before the main audit could start."
        sidecar["bootstrap_actions"] = bootstrap_actions
        sidecar["dependency_failures"] = dependency_failures
        sidecar["generated_at"] = utc_now()
        write_json_atomic(state_path, sidecar)
        return BOOTSTRAP_BLOCKED_EXIT

    sidecar["dependency_status"] = "auto-installed" if installed_any else "ready"
    sidecar["bootstrap_actions"] = bootstrap_actions
    sidecar["dependency_failures"] = dependency_failures
    sidecar["current_action"] = "Preflight complete. Main audit may start."
    sidecar["generated_at"] = utc_now()
    write_json_atomic(state_path, sidecar)
    return 0


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
            "The skill did not enter its main audit because a required runtime feature or installable dependency was unavailable after bootstrap attempts.",
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
        "title": "Dependency bootstrap blocked the audit before graph tooling could run",
        "evidence_summary": "Required dependency tooling was unavailable and automatic installation attempts did not succeed.",
        "decision": "fix-config",
        "recommended_change_shape": "Restore the blocked dependencies and rerun the dependency audit before trusting any boundary verdict.",
        "validation_checks": ["Make sure the blocked dependency installs cleanly on the host."],
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
            "notes": ["Dependency bootstrap blocked before the main audit could start."],
        },
        "tool_coverage": {
            "chosen_tools": [{
                "tool": "manual",
                "rationale": "Dependency bootstrap blocked the skill before any graph tool could run.",
            }],
            "skipped_tools": [
                {"tool": item["name"], "reason": item["failure_reason"]}
                for item in state.get("dependency_failures") or []
                if item["name"] in {"tach", "dependency-cruiser", "knip"}
            ],
        },
        "overall_verdict": "scan-blocked",
        "findings": findings,
        "immediate_actions": ["Fix blocked dependency bootstrap before running dependency governance."],
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
            "summary": "Dependency bootstrap blocked the skill before this gate could be audited.",
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
        "title": "Dependency bootstrap blocked the audit before gate evidence could be collected",
        "evidence_summary": "A required dependency or runtime feature was unavailable after bootstrap attempts.",
        "decision": "defer",
        "change_shape": "Restore the blocked dependency, rerun the audit, then judge domain gates from fresh evidence.",
        "validation": "Prove the dependency bootstrap succeeds and rerun the skill.",
        "merge_gate": "warn-only",
        "autofix_allowed": False,
        "notes": ", ".join(item["name"] for item in failures) or "bootstrap blocked the run",
    }]
    repo_profile = {
        "languages": list(profile["languages"]),
        "shape": "unknown",
        "notes": ["Dependency bootstrap blocked before the main audit could start."],
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
            "immediate_actions": ["Restore blocked dependencies before trusting contract gates."],
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
            "title": "Dependency bootstrap blocked the audit before runtime evidence could be collected",
            "path": ".",
            "line": 1,
            "evidence": [item["failure_reason"] for item in failures] or ["dependency bootstrap blocked the run"],
            "recommendation": "Restore the blocked dependency and rerun this audit before trusting any verdict.",
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
        "summary_line": "Dependency bootstrap blocked the Pythonic drift audit before it could inspect the repo.",
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
            "title": "Dependency bootstrap blocked the Pythonic DDD drift audit",
            "path": ".",
            "line": 1,
            "evidence": [item["failure_reason"] for item in failures] or ["dependency bootstrap blocked the run"],
            "recommendation": "Restore the blocked dependency and rerun the audit.",
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
            "summary": "Dependency bootstrap blocked the cleanup audit before any evidence could be collected.",
            "cue": None,
            "replacement": None,
            "removal_target": None,
            "evidence": [item["failure_reason"] for item in failures] or ["dependency bootstrap blocked the run"],
        }],
        "notes": [", ".join(item["name"] for item in failures) or "dependency bootstrap blocked the run"],
    }


def llm_blocked_summary(repo: Path, state: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    failures = state.get("dependency_failures") or []
    return {
        "skill": "llm-api-freshness-guard",
        "version": "1.0.0",
        "generated_at": utc_now(),
        "mode": "blocked",
        "repo_profile": {
            "repo_root": str(repo.resolve()),
            "files_scanned": int(profile["files_scanned"]),
            "languages": list(profile["languages"]),
            "providers_detected": [],
            "provider_scores": {},
            "wrappers_detected": [],
            "version_hints": {},
            "model_hints": {},
            "base_url_hints": {},
        },
        "doc_verification": [],
        "findings": [{
            "id": "bootstrap-blocked-llm-001",
            "provider": "unknown",
            "kind": "scan-blocker",
            "severity": "high",
            "confidence": "high",
            "status": "present",
            "scope": [],
            "title": "Runtime bootstrap blocked live LLM API freshness verification",
            "stale_usage": "The skill could not verify current docs because a required runtime feature or dependency was unavailable.",
            "current_expectation": "Restore the blocked dependency or runtime feature before treating this skill as a source of truth.",
            "evidence": [{"path": ".", "line": 1, "snippet": item["failure_reason"]} for item in failures] or [{"path": ".", "line": 1, "snippet": "dependency bootstrap blocked the run"}],
            "recommended_change_shape": "Restore the blocked dependency, then rerun the Context7-backed verification flow.",
            "docs_verified": False,
            "autofix_allowed": False,
            "notes": ", ".join(item["name"] for item in failures),
        }],
        "priorities": {
            "now": ["Restore the blocked runtime feature or dependency before trusting any LLM API freshness verdict."],
            "next": [],
            "later": [],
        },
        "scan_limitations": [item["failure_reason"] for item in failures] or ["Dependency bootstrap blocked the run."],
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
            summary_line="Dependency bootstrap blocked the distributed side-effect audit before it could inspect event paths.",
            overall_verdict="watch",
        )
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
            "summary_line": "Runtime bootstrap blocked repo-health orchestration before child audits could start.",
            "skill_runs": [],
            "top_actions": ["Restore blocked orchestrator runtime features before retrying the fleet audit."],
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
    for key in ("overall_verdict", "overall_health", "mode", "status"):
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
