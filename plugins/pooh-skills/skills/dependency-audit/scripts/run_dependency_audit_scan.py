#!/usr/bin/env python3
"""Run dependency-audit with the locked shared toolchain."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RUNTIME_BIN_DIR = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN_DIR))

from tool_runner import ToolRun, run_locked_tool, skipped_tool_run, tool_run_map  # noqa: E402

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".repo-harness",
    ".next",
    ".turbo",
    ".idea",
    ".vscode",
}

PYTHON_EXTS = {".py", ".pyi"}
TYPESCRIPT_EXTS = {".ts", ".tsx"}
JAVASCRIPT_EXTS = {".js", ".jsx", ".mjs", ".cjs"}
TEXT_EXTS = PYTHON_EXTS | TYPESCRIPT_EXTS | JAVASCRIPT_EXTS | {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".md",
    ".sh",
}

MANIFEST_FILES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "package.json",
    "pnpm-workspace.yaml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "poetry.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

DEPCRUISE_CONFIGS = (
    ".dependency-cruiser.js",
    ".dependency-cruiser.cjs",
    ".dependency-cruiser.mjs",
    ".dependency-cruiser.json",
)
KNIP_CONFIGS = ("knip.json", "knip.jsonc", "knip.js", "knip.ts", "knip.config.ts", "knip.config.js")


@dataclass
class Finding:
    id: str
    tool: str
    category: str
    severity: str
    confidence: str
    scope: str
    title: str
    evidence_summary: str
    decision: str
    recommended_change_shape: str
    validation_checks: list[str]
    autofix_allowed: bool
    notes: str = ""


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in filenames:
            path = Path(current_root) / name
            if path.suffix.lower() in TEXT_EXTS or name in MANIFEST_FILES:
                files.append(path)
    return files


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def detect_languages(files: list[Path]) -> list[str]:
    langs: set[str] = set()
    for path in files:
        suffix = path.suffix.lower()
        if suffix in PYTHON_EXTS:
            langs.add("python")
        elif suffix in TYPESCRIPT_EXTS:
            langs.add("typescript")
        elif suffix in JAVASCRIPT_EXTS:
            langs.add("javascript")
    if not langs:
        langs.add("non-application")
    return sorted(langs)


def detect_package_managers(repo: Path) -> list[str]:
    managers: list[str] = []
    if (repo / "pnpm-lock.yaml").exists():
        managers.append("pnpm")
    if (repo / "package-lock.json").exists():
        managers.append("npm")
    if (repo / "yarn.lock").exists():
        managers.append("yarn")
    if (repo / "poetry.lock").exists():
        managers.append("poetry")
    if (repo / "Pipfile").exists():
        managers.append("pipenv")
    if (repo / "requirements.txt").exists():
        managers.append("pip")
    return managers


def bucket_source_root(rel: Path) -> str | None:
    if not rel.parts:
        return None
    first = rel.parts[0]
    if first in {"packages", "apps", "libs", "services", "modules"}:
        if len(rel.parts) >= 3 and rel.parts[2] == "src":
            return "/".join(rel.parts[:3])
        if len(rel.parts) >= 2:
            return "/".join(rel.parts[:2])
    if first == "src":
        return "src"
    if first in {"tests", "test", "docs", ".github", "scripts"}:
        return None
    if rel.suffix.lower() in PYTHON_EXTS | TYPESCRIPT_EXTS | JAVASCRIPT_EXTS:
        return first
    return None


def collect_repo_profile(repo: Path, files: list[Path]) -> dict[str, object]:
    manifests: list[str] = []
    source_roots: set[str] = set()
    workspace_roots: set[str] = set()
    package_json_dirs: set[str] = set()
    pyproject_dirs: set[str] = set()
    python_targets: set[str] = set()
    js_targets: set[str] = set()
    notes: list[str] = []

    for path in files:
        rel = path.relative_to(repo)
        if path.name in MANIFEST_FILES:
            manifests.append(str(rel))
        root = bucket_source_root(rel)
        if root:
            source_roots.add(root)
            if path.suffix.lower() in PYTHON_EXTS:
                python_targets.add(root)
            elif path.suffix.lower() in TYPESCRIPT_EXTS | JAVASCRIPT_EXTS:
                js_targets.add(root)
        if path.name == "package.json":
            package_json_dirs.add(str(rel.parent))
        elif path.name == "pyproject.toml":
            pyproject_dirs.add(str(rel.parent))

    if (repo / "pnpm-workspace.yaml").exists():
        workspace_roots.add(".")
    for candidate in sorted(package_json_dirs | pyproject_dirs):
        if candidate != ".":
            workspace_roots.add(candidate)

    if len(workspace_roots) > 1:
        monorepo_shape = "workspace-monorepo"
    elif source_roots:
        monorepo_shape = "single-package"
    else:
        monorepo_shape = "repo-without-app-surface"

    if not python_targets and not js_targets:
        notes.append("No Python or JS/TS application surface was detected outside ignored directories.")

    return {
        "languages": detect_languages(files),
        "monorepo_shape": monorepo_shape,
        "package_managers": detect_package_managers(repo),
        "source_roots": sorted(source_roots),
        "workspace_roots": sorted(workspace_roots),
        "major_blockers": [],
        "notes": notes,
        "manifests": sorted(manifests),
        "package_json_dirs": sorted(package_json_dirs),
        "pyproject_dirs": sorted(pyproject_dirs),
        "python_targets": sorted(python_targets),
        "js_targets": sorted(js_targets),
    }


def detect_depcruise_config(repo: Path) -> str | None:
    for name in DEPCRUISE_CONFIGS:
        if (repo / name).exists():
            return name
    return None


def detect_knip_directory(repo: Path, profile: dict[str, object]) -> str | None:
    package_json_dirs = [item for item in profile.get("package_json_dirs", []) if item]
    if (repo / "package.json").exists():
        return "."
    if package_json_dirs:
        return sorted(package_json_dirs)[0]
    return None


def detect_tach_config(repo: Path) -> bool:
    pyproject = repo / "pyproject.toml"
    if (repo / "tach.toml").exists():
        return True
    if pyproject.exists():
        return "[tool.tach]" in read_text(pyproject)
    return False


def run_tool_suite(repo: Path, profile: dict[str, object]) -> tuple[list[ToolRun], dict[str, Any]]:
    tool_runs: list[ToolRun] = []
    payloads: dict[str, Any] = {}
    languages = set(profile["languages"])

    if "python" in languages:
        run, payload = run_locked_tool(
            "tach",
            ["check", "--output", "json"],
            repo,
            allow_exit_codes={0, 1},
        )
        tool_runs.append(run)
        payloads["tach"] = payload
    else:
        tool_runs.append(skipped_tool_run("tach", "No Python application surface was detected."))

    if {"typescript", "javascript"} & languages:
        dep_targets = profile.get("js_targets") or ["."]
        depcruise_args = ["-T", "json", "--no-config", *dep_targets]
        depcruise_run, depcruise_payload = run_locked_tool(
            "dependency-cruiser",
            depcruise_args,
            repo,
            allow_exit_codes={0, 1},
        )
        tool_runs.append(depcruise_run)
        payloads["dependency-cruiser"] = depcruise_payload

        knip_dir = detect_knip_directory(repo, profile)
        if knip_dir is None:
            tool_runs.append(skipped_tool_run("knip", "No package.json root was found for a Knip project scan."))
        else:
            knip_run, knip_payload = run_locked_tool(
                "knip",
                ["--reporter", "json", "--no-progress", "--directory", str(repo / knip_dir)],
                repo,
                allow_exit_codes={0, 1},
            )
            tool_runs.append(knip_run)
            payloads["knip"] = knip_payload
    else:
        tool_runs.append(skipped_tool_run("dependency-cruiser", "No JS/TS application surface was detected."))
        tool_runs.append(skipped_tool_run("knip", "No JS/TS application surface was detected."))

    return tool_runs, payloads


def parse_knip_issue_totals(payload: Any) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    if not isinstance(payload, dict):
        return {}
    for item in payload.get("issues") or []:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if key == "file" or not isinstance(value, list):
                continue
            totals[key] += len(value)
    return dict(totals)


def build_tool_coverage(repo: Path, profile: dict[str, object], tool_runs: list[ToolRun]) -> dict[str, object]:
    chosen_tools: list[dict[str, str]] = []
    skipped_tools: list[dict[str, str]] = []
    runs = tool_run_map(tool_runs)

    for tool in ("tach", "dependency-cruiser", "knip"):
        run = runs[tool]
        if run.status == "skipped":
            skipped_tools.append({"tool": tool, "reason": run.summary})
            continue
        chosen_tools.append({
            "tool": tool,
            "rationale": run.summary,
        })

    if not chosen_tools:
        chosen_tools.append({
            "tool": "manual",
            "rationale": "No relevant Python or JS/TS surface was detected for a real dependency graph audit.",
        })

    return {"chosen_tools": chosen_tools, "skipped_tools": skipped_tools}


def make_finding(
    findings: list[Finding],
    next_id: int,
    *,
    tool: str,
    category: str,
    severity: str,
    confidence: str,
    scope: str,
    title: str,
    evidence_summary: str,
    decision: str,
    change_shape: str,
    validation_checks: list[str],
    notes: str = "",
) -> int:
    findings.append(Finding(
        id=f"dep-{next_id:03d}",
        tool=tool,
        category=category,
        severity=severity,
        confidence=confidence,
        scope=scope,
        title=title,
        evidence_summary=evidence_summary,
        decision=decision,
        recommended_change_shape=change_shape,
        validation_checks=validation_checks,
        autofix_allowed=False,
        notes=notes,
    ))
    return next_id + 1


def build_findings(repo: Path, profile: dict[str, object], tool_runs: list[ToolRun], payloads: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    next_id = 1
    languages = set(profile["languages"])
    runs = tool_run_map(tool_runs)

    if not ({"python", "typescript", "javascript"} & languages):
        profile["major_blockers"].append("No Python or JS/TS application surface was detected.")
        next_id = make_finding(
            findings,
            next_id,
            tool="manual",
            category="scan-blocker",
            severity="medium",
            confidence="high",
            scope="repo",
            title="This repository does not expose a real Python or JS/TS dependency graph target",
            evidence_summary="No Python or JS/TS application surface was found outside ignored directories, so a dependency graph audit would be theater.",
            decision="defer",
            change_shape="Scope this skill to repositories with real Python or JS/TS application code.",
            validation_checks=["Confirm whether application code exists outside ignored directories."],
        )
        return findings

    tach_run = runs["tach"]
    if tach_run.status == "failed" or ("configuration file not found" in " ".join(tach_run.details).lower()):
        profile["major_blockers"].append("Tach could not validate Python boundaries from this checkout.")
        next_id = make_finding(
            findings,
            next_id,
            tool="tach",
            category="config-gap",
            severity="high",
            confidence="high",
            scope="python",
            title="Python boundary governance is not runnable yet",
            evidence_summary=tach_run.summary,
            decision="fix-config",
            change_shape="Add a real Tach configuration and source-root model before trusting Python boundary claims.",
            validation_checks=["Create tach.toml or [tool.tach] and rerun `tach check --output json`."],
            notes=" | ".join(tach_run.details[:2]),
        )
    elif tach_run.status == "issues":
        next_id = make_finding(
            findings,
            next_id,
            tool="tach",
            category="architecture-violation",
            severity="high",
            confidence="high",
            scope="python",
            title="Tach reported Python boundary or interface violations",
            evidence_summary=tach_run.summary,
            decision="harden",
            change_shape="Fix the live Python boundary leaks before claiming the repo has real architectural discipline.",
            validation_checks=["Inspect Tach output and remove live dependency or interface violations."],
            notes=" | ".join(tach_run.details[:3]),
        )

    depcruise_run = runs["dependency-cruiser"]
    if depcruise_run.status == "failed":
        next_id = make_finding(
            findings,
            next_id,
            tool="dependency-cruiser",
            category="config-gap",
            severity="medium",
            confidence="high",
            scope="js-ts",
            title="Dependency Cruiser did not complete successfully",
            evidence_summary=depcruise_run.summary,
            decision="fix-config",
            change_shape="Restore a runnable JS/TS graph scan before using dependency direction claims in governance.",
            validation_checks=["Rerun Dependency Cruiser and resolve parsing or configuration errors."],
            notes=" | ".join(depcruise_run.details[:2]),
        )
    elif depcruise_run.status == "issues":
        category = "cycle" if "circular" in json.dumps(payloads.get("dependency-cruiser") or {}, ensure_ascii=False).lower() else "architecture-violation"
        next_id = make_finding(
            findings,
            next_id,
            tool="dependency-cruiser",
            category=category,
            severity="high" if category == "cycle" else "medium",
            confidence="medium",
            scope="js-ts",
            title="Dependency Cruiser reported JS/TS graph violations",
            evidence_summary=depcruise_run.summary,
            decision="harden",
            change_shape="Fix live JS/TS dependency violations before pretending the layering story is enforced.",
            validation_checks=["Inspect depcruise JSON output and baseline or remove the current violations."],
            notes=" | ".join(depcruise_run.details[:3]),
        )

    knip_run = runs["knip"]
    if knip_run.status == "failed":
        next_id = make_finding(
            findings,
            next_id,
            tool="knip",
            category="config-gap",
            severity="medium",
            confidence="high",
            scope="js-ts",
            title="Knip did not complete successfully",
            evidence_summary=knip_run.summary,
            decision="fix-config",
            change_shape="Restore a runnable Knip project definition before treating dead-code conclusions as trustworthy.",
            validation_checks=["Rerun Knip from the correct package root and resolve project detection failures."],
            notes=" | ".join(knip_run.details[:2]),
        )
    elif knip_run.status == "issues":
        knip_totals = parse_knip_issue_totals(payloads.get("knip"))
        if knip_totals.get("files"):
            next_id = make_finding(
                findings,
                next_id,
                tool="knip",
                category="unused-file",
                severity="medium",
                confidence="high",
                scope="js-ts",
                title="Knip reported unused files",
                evidence_summary=f"Knip reported {knip_totals['files']} unused file finding(s).",
                decision="remove",
                change_shape="Delete or quarantine genuinely unused files once live entrypoints are confirmed.",
                validation_checks=["Confirm each reported file is not loaded dynamically before deletion."],
            )
        if knip_totals.get("dependencies"):
            next_id = make_finding(
                findings,
                next_id,
                tool="knip",
                category="unused-dependency",
                severity="medium",
                confidence="high",
                scope="js-ts",
                title="Knip reported unused dependencies",
                evidence_summary=f"Knip reported {knip_totals['dependencies']} unused dependency finding(s).",
                decision="remove",
                change_shape="Remove genuinely unused dependencies after confirming build and runtime entrypoints are complete.",
                validation_checks=["Confirm dependency usage is not hidden behind generators or dynamic entrypoints."],
            )
        export_total = sum(knip_totals.get(key, 0) for key in ("exports", "nsExports", "types", "nsTypes", "enumMembers", "namespaceMembers"))
        if export_total:
            next_id = make_finding(
                findings,
                next_id,
                tool="knip",
                category="unused-export",
                severity="low",
                confidence="medium",
                scope="js-ts",
                title="Knip reported unused exports",
                evidence_summary=f"Knip reported {export_total} unused export finding(s).",
                decision="quarantine",
                change_shape="Treat unused-export findings as advisory until entry/workspace coverage is proven complete.",
                validation_checks=["Confirm barrel exports, CLI entrypoints, and framework entry exports are fully declared before deletion."],
            )
        unresolved_total = knip_totals.get("unresolved", 0) + knip_totals.get("unlisted", 0)
        if unresolved_total:
            next_id = make_finding(
                findings,
                next_id,
                tool="knip",
                category="unresolved-import",
                severity="high",
                confidence="high",
                scope="js-ts",
                title="Knip reported unresolved or unlisted imports",
                evidence_summary=f"Knip reported {unresolved_total} unresolved / unlisted dependency finding(s).",
                decision="fix-config",
                change_shape="Repair package metadata or import paths before trusting dead-code cleanup output.",
                validation_checks=["Resolve unlisted or unresolved imports and rerun Knip."],
            )

    manifests = set(profile["manifests"])
    if "package.json" in manifests and not {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"} & manifests:
        next_id = make_finding(
            findings,
            next_id,
            tool="manual",
            category="dependency-declaration-gap",
            severity="medium",
            confidence="high",
            scope="package-manager",
            title="JS/TS dependency metadata has no visible lockfile",
            evidence_summary="A package.json is present but no npm, pnpm, or yarn lockfile was detected.",
            decision="fix-config",
            change_shape="Commit the real lockfile before treating dependency findings as reproducible engineering evidence.",
            validation_checks=["Generate and commit the lockfile used by this repo."],
        )

    if len(profile["workspace_roots"]) > 1 and not ((repo / "pnpm-workspace.yaml").exists() or (repo / "package.json").exists()):
        next_id = make_finding(
            findings,
            next_id,
            tool="manual",
            category="orphan-or-isolated-module",
            severity="medium",
            confidence="medium",
            scope="workspace",
            title="The repo looks multi-root, but workspace ownership is under-specified",
            evidence_summary="Multiple package or pyproject roots were detected without a clear top-level workspace declaration.",
            decision="harden",
            change_shape="Declare the real workspace root before layering stricter dependency governance on top of it.",
            validation_checks=["Confirm the intended workspace root and package graph in repo metadata."],
        )

    return findings


def infer_verdict(findings: list[Finding]) -> str:
    categories = Counter(item.category for item in findings)
    severities = Counter(item.severity for item in findings)
    if categories["scan-blocker"] or severities["high"] > 0:
        return "scan-blocked"
    if categories["config-gap"] >= 2:
        return "baseline-needed"
    if categories["unused-file"] or categories["unused-dependency"] or categories["unused-export"]:
        return "cleanup-first"
    if categories["architecture-violation"] or categories["cycle"]:
        return "boundary-hardening"
    if findings:
        return "incremental-governance"
    return "well-governed"


def render_human_report(summary: dict[str, object]) -> str:
    findings = summary["findings"]
    tool_runs = summary.get("tool_runs", [])
    immediate = summary.get("immediate_actions", [])
    next_actions = summary.get("next_actions", [])
    later = summary.get("later_actions", [])
    blockers = summary["repo_profile"].get("major_blockers", [])

    lines = [
        "# 仓库依赖审计报告",
        "",
        "## 1. 摘要",
        f"- 仓库类型：{', '.join(summary['repo_profile']['languages'])} / {summary['repo_profile']['monorepo_shape']}",
        f"- 核心结论：{summary['overall_verdict']}",
        f"- 已执行工具：{', '.join(item['tool'] for item in tool_runs if item['status'] != 'skipped') or '无'}",
        "",
        "## 2. 工具执行证据",
        "",
    ]

    for item in tool_runs:
        lines.extend([
            f"### {item['tool']}",
            f"- 状态：{item['status']}",
            f"- 命令：{item['command'] or 'n/a'}",
            f"- 结果：{item['summary']}",
            *(f"- 细节：{detail}" for detail in item.get("details", [])[:2]),
            "",
        ])

    lines.extend(["## 3. 关键问题", ""])
    if not findings:
        lines.append("- 当前真实工具执行没有报出高信号问题。")
    else:
        for finding in findings[:6]:
            lines.extend([
                f"### {finding['id']} {finding['title']}",
                f"- 工具：{finding['tool']}",
                f"- 严重程度：{finding['severity']}",
                f"- 置信度：{finding['confidence']}",
                f"- 是什么：{finding['evidence_summary']}",
                f"- 建议：{'；'.join(finding['validation_checks'])}",
                f"- 备注：{finding.get('notes') or '无'}",
                "",
            ])

    lines.extend([
        "## 4. 行动顺序",
        "",
        "### 现在",
        *(f"- {item}" for item in immediate),
        "",
        "### 下一步",
        *(f"- {item}" for item in next_actions),
        "",
        "### 之后",
        *(f"- {item}" for item in later),
        "",
        "## 5. 局限",
        *(f"- {item}" for item in blockers or ["本次已经真实执行锁定工具，但远端 CI / ruleset 仍需单独验证。"]),
        "",
    ])
    return "\n".join(lines)


def render_agent_brief(summary: dict[str, object]) -> str:
    lines = [
        "# Repo Audit Handoff Brief",
        "",
        "## Repo profile",
        f"- languages: {', '.join(summary['repo_profile']['languages'])}",
        f"- monorepo_shape: {summary['repo_profile']['monorepo_shape']}",
        f"- package_managers: {', '.join(summary['repo_profile']['package_managers']) or 'none'}",
        f"- overall_verdict: {summary['overall_verdict']}",
        "",
        "## Tool runs",
        "",
    ]
    for item in summary.get("tool_runs", []):
        lines.extend([
            f"- {item['tool']}: {item['status']} ({item['summary']})",
        ])

    lines.extend(["", "## Findings", ""])
    if not summary["findings"]:
        lines.append("- No dependency findings were confirmed by the locked toolchain.")
    else:
        for finding in summary["findings"]:
            lines.extend([
                f"### {finding['id']} {finding['title']}",
                f"- tool: {finding['tool']}",
                f"- severity: {finding['severity']}",
                f"- confidence: {finding['confidence']}",
                f"- scope: {finding['scope']}",
                f"- evidence_summary: {finding['evidence_summary']}",
                f"- decision: {finding['decision']}",
                f"- recommended_change_shape: {finding['recommended_change_shape']}",
                f"- validation_checks: {', '.join(finding['validation_checks'])}",
                f"- notes: {finding.get('notes') or 'none'}",
                "",
            ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--summary-out", default=None)
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--agent-brief-out", default=None)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    files = iter_files(repo)
    profile = collect_repo_profile(repo, files)
    tool_runs, payloads = run_tool_suite(repo, profile)
    tool_coverage = build_tool_coverage(repo, profile, tool_runs)
    findings = build_findings(repo, profile, tool_runs, payloads)
    overall_verdict = infer_verdict(findings)

    immediate_actions: list[str] = []
    next_actions: list[str] = []
    later_actions: list[str] = []
    if overall_verdict == "scan-blocked":
        immediate_actions.append("Fix the blocked or failing dependency tool runs before trusting repo boundary claims.")
    if any(item.category == "config-gap" for item in findings):
        immediate_actions.append("Repair repo config and rerun the locked tools until they stop failing locally.")
    if any(item.category in {"architecture-violation", "cycle"} for item in findings):
        next_actions.append("Remove live boundary leaks and cycles before tightening merge gates.")
    if any(item.category in {"unused-file", "unused-dependency", "unused-export"} for item in findings):
        next_actions.append("Quarantine and validate dead-code candidates before deleting them.")
    if not next_actions:
        next_actions.append("Keep the locked toolchain green before raising merge strictness.")
    later_actions.append("Promote changed-file dependency violations into CI only after the current repo shape is stable.")

    summary = {
        "repo_profile": {
            key: value
            for key, value in profile.items()
            if key in {"languages", "monorepo_shape", "package_managers", "source_roots", "workspace_roots", "major_blockers", "notes"}
        },
        "tool_coverage": tool_coverage,
        "overall_verdict": overall_verdict,
        "tool_runs": [item.to_dict() for item in tool_runs],
        "findings": [asdict(item) for item in findings],
        "immediate_actions": immediate_actions,
        "next_actions": next_actions,
        "later_actions": later_actions,
        "safe_automation": [
            "Keep the locked toolchain green in CI before tightening merge rules.",
            "Baseline historical dependency violations before blocking new ones in legacy repos.",
        ],
        "avoid_now": [
            "Do not treat repo-shape or config failures as architecture proof.",
            "Do not delete exports just because Knip found them before entry coverage is trusted.",
        ],
        "assumptions": [
            "This summary comes from real locked tool executions where the repo surface was applicable.",
            "Remote merge enforcement still needs separate platform-side verification.",
        ],
    }

    summary_path = Path(args.summary_out).resolve() if args.summary_out else out_dir / "repo-audit-summary.json"
    report_path = Path(args.report_out).resolve() if args.report_out else out_dir / "repo-audit-report.md"
    brief_path = Path(args.agent_brief_out).resolve() if args.agent_brief_out else out_dir / "repo-audit-agent-brief.md"

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_path.write_text(render_human_report(summary) + "\n", encoding="utf-8")
    brief_path.write_text(render_agent_brief(summary), encoding="utf-8")
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
