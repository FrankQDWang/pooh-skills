#!/usr/bin/env python3
"""Generate a conservative dependency-audit baseline summary.

This wrapper is intentionally honest about its limits:
- it produces a stable machine-readable baseline for orchestration
- it profiles repo shape and tool readiness
- it does not pretend to replace a full Tach / Dependency Cruiser / Knip run
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

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


def has_tool_toml_section(pyproject: Path, header: str) -> bool:
    if not pyproject.exists():
        return False
    return header in read_text(pyproject)


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
    if first in {"tests", "test", "docs", ".github", "scripts", "skills"}:
        return None
    if rel.suffix.lower() in PYTHON_EXTS and rel.name == "__init__.py":
        return first
    if rel.suffix.lower() in PYTHON_EXTS | TYPESCRIPT_EXTS | JAVASCRIPT_EXTS:
        return first
    return None


def collect_repo_profile(repo: Path, files: list[Path]) -> dict[str, object]:
    manifests: list[str] = []
    source_roots: set[str] = set()
    workspace_roots: set[str] = set()
    package_json_dirs: set[str] = set()
    pyproject_dirs: set[str] = set()
    notes: list[str] = []

    for path in files:
        rel = path.relative_to(repo)
        if path.name in MANIFEST_FILES:
            manifests.append(str(rel))
        root = bucket_source_root(rel)
        if root:
            source_roots.add(root)
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

    if "skills" in {root.split("/")[0] for root in source_roots} and len(source_roots) == 1:
        notes.append("Only skill metadata and helper scripts were detected; no Python or JS/TS app surface is visible.")

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
    }


def build_tool_coverage(repo: Path, profile: dict[str, object]) -> dict[str, object]:
    languages = set(profile["languages"])
    source_roots = profile["source_roots"]
    chosen_tools = [{
        "tool": "manual",
        "rationale": (
            "Wrapper emitted a conservative baseline summary from repo profiling and tool readiness checks. "
            "Use the full skill workflow to run Tach / Dependency Cruiser / Knip interactively."
        ),
    }]
    skipped_tools: list[dict[str, str]] = []

    pyproject = repo / "pyproject.toml"
    package_json = repo / "package.json"

    if "python" in languages:
        if not source_roots:
            skipped_tools.append({
                "tool": "tach",
                "reason": "Python files exist but source_roots are not credible yet; boundary claims would be scanner-confidence only.",
            })
        elif shutil.which("tach") is None:
            skipped_tools.append({
                "tool": "tach",
                "reason": "tach binary is not available to the wrapper on this machine.",
            })
        elif not ((repo / "tach.toml").exists() or has_tool_toml_section(pyproject, "[tool.tach]")):
            skipped_tools.append({
                "tool": "tach",
                "reason": "Python surface exists, but no tach.toml or [tool.tach] configuration was found.",
            })
        else:
            skipped_tools.append({
                "tool": "tach",
                "reason": "Tool appears ready, but baseline mode does not execute external graph tools automatically.",
            })

    if "typescript" in languages or "javascript" in languages:
        depcruise_config = any((repo / name).exists() for name in (
            ".dependency-cruiser.js",
            ".dependency-cruiser.cjs",
            ".dependency-cruiser.mjs",
            ".dependency-cruiser.json",
        ))
        if shutil.which("depcruise") is None and shutil.which("dependency-cruiser") is None:
            skipped_tools.append({
                "tool": "dependency-cruiser",
                "reason": "dependency-cruiser / depcruise binary is not available to the wrapper on this machine.",
            })
        elif not depcruise_config:
            skipped_tools.append({
                "tool": "dependency-cruiser",
                "reason": "JS/TS surface exists, but no dependency-cruiser config file was found.",
            })
        else:
            skipped_tools.append({
                "tool": "dependency-cruiser",
                "reason": "Tool appears ready, but baseline mode does not execute external graph tools automatically.",
            })

        package_json_text = read_text(package_json) if package_json.exists() else ""
        knip_config = any((repo / name).exists() for name in (
            "knip.json",
            "knip.jsonc",
            "knip.js",
            "knip.ts",
        )) or '"knip"' in package_json_text
        if shutil.which("knip") is None:
            skipped_tools.append({
                "tool": "knip",
                "reason": "knip binary is not available to the wrapper on this machine.",
            })
        elif not knip_config:
            skipped_tools.append({
                "tool": "knip",
                "reason": "JS/TS surface exists, but no Knip configuration was found.",
            })
        else:
            skipped_tools.append({
                "tool": "knip",
                "reason": "Tool appears ready, but baseline mode does not execute external dead-code scans automatically.",
            })

    return {"chosen_tools": chosen_tools, "skipped_tools": skipped_tools}


def build_findings(repo: Path, profile: dict[str, object], tool_coverage: dict[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    next_id = 1
    languages = set(profile["languages"])
    manifests = set(profile["manifests"])
    source_roots = profile["source_roots"]
    workspace_roots = profile["workspace_roots"]

    def add(
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
        autofix_allowed: bool = False,
        notes: str = "",
    ) -> None:
        nonlocal next_id
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
            autofix_allowed=autofix_allowed,
            notes=notes,
        ))
        next_id += 1

    if not ({"python", "typescript", "javascript"} & languages):
        profile["major_blockers"].append("No Python or JS/TS application surface was detected.")
        add(
            tool="manual",
            category="scan-blocker",
            severity="medium",
            confidence="high",
            scope="repo",
            title="This repository does not expose a real Python or JS/TS dependency graph target",
            evidence_summary="The repo only exposes markdown, shell, and skill metadata surfaces, so Tach / Dependency Cruiser / Knip would be theater here.",
            decision="defer",
            change_shape="Do not pretend this repo is a dependency-governance target until it contains real Python or JS/TS application code.",
            validation_checks=["Confirm whether any application code lives outside ignored directories."],
        )
        return findings

    if "python" in languages and not source_roots:
        profile["major_blockers"].append("Python source_roots are not yet credible.")
        add(
            tool="manual",
            category="config-gap",
            severity="high",
            confidence="high",
            scope="python",
            title="Python surface exists, but source_roots are too ambiguous for boundary claims",
            evidence_summary="The wrapper found Python files but could not derive credible source_roots, so Tach-style boundary conclusions would be guesswork.",
            decision="fix-config",
            change_shape="Define source_roots explicitly before turning Python boundary output into governance.",
            validation_checks=["Add source_roots to the repo config and rerun the dependency audit."],
        )

    if "python" in languages and not any("tach" == item["tool"] and "appears ready" in item["reason"] for item in tool_coverage["skipped_tools"]):
        add(
            tool="manual",
            category="config-gap",
            severity="medium",
            confidence="high",
            scope="python",
            title="Python boundary governance is not runnable yet",
            evidence_summary="Either Tach is missing, its config is missing, or the repo surface is not mature enough to trust Python boundary checks.",
            decision="fix-config",
            change_shape="Install Tach only after source_roots and config are credible, then gate new Python boundary violations instead of inventing manual rules.",
            validation_checks=["Verify tach.toml or [tool.tach] exists and that `tach check` can run locally."],
        )

    if {"typescript", "javascript"} & languages and not any(item["tool"] == "dependency-cruiser" and "appears ready" in item["reason"] for item in tool_coverage["skipped_tools"]):
        add(
            tool="manual",
            category="config-gap",
            severity="medium",
            confidence="high",
            scope="js-ts",
            title="JS/TS structure scanning is not ready for hard claims",
            evidence_summary="Dependency Cruiser is missing, unconfigured, or intentionally skipped in baseline mode, so cross-layer and cycle enforcement is not machine-backed yet.",
            decision="create-baseline",
            change_shape="Add a minimal dependency-cruiser config and baseline historical violations before making JS/TS boundary rules a real gate.",
            validation_checks=["Check `.dependency-cruiser.*` and prove `depcruise --validate` can run."],
        )

    if {"typescript", "javascript"} & languages and not any(item["tool"] == "knip" and "appears ready" in item["reason"] for item in tool_coverage["skipped_tools"]):
        add(
            tool="manual",
            category="config-gap",
            severity="low",
            confidence="high",
            scope="js-ts",
            title="Dead-code hygiene is not machine-backed yet",
            evidence_summary="Knip is missing, unconfigured, or intentionally skipped in baseline mode, so unused-file and unused-export findings are still manual debt.",
            decision="create-baseline",
            change_shape="Configure Knip only after entry/workspace coverage is credible; otherwise its output will mostly be noise.",
            validation_checks=["Confirm Knip config exists and entry/workspace coverage is explicit before trusting unused-export output."],
        )

    if "package.json" in manifests and not {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"} & manifests:
        add(
            tool="manual",
            category="dependency-declaration-gap",
            severity="medium",
            confidence="high",
            scope="package-manager",
            title="JS/TS dependency metadata has no visible lockfile",
            evidence_summary="A package.json is present but no npm, pnpm, or yarn lockfile was detected, which weakens both reproducibility and dependency scanning confidence.",
            decision="fix-config",
            change_shape="Add the real lockfile used by this repo before treating dependency findings as stable.",
            validation_checks=["Regenerate the lockfile with the repo's actual package manager and rerun the baseline audit."],
        )

    if len(workspace_roots) > 1 and not ((repo / "pnpm-workspace.yaml").exists() or (repo / "package.json").exists()):
        add(
            tool="manual",
            category="orphan-or-isolated-module",
            severity="medium",
            confidence="medium",
            scope="workspace",
            title="The repo looks multi-root, but workspace ownership is under-specified",
            evidence_summary="Multiple package or pyproject roots were detected without a clear top-level workspace declaration, which usually leads to fake monorepo governance.",
            decision="harden",
            change_shape="Make the workspace root explicit before layering more dependency rules on top of it.",
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
    chosen_tools = summary["tool_coverage"]["chosen_tools"]
    skipped_tools = summary["tool_coverage"]["skipped_tools"]
    immediate = summary.get("immediate_actions", [])
    next_actions = summary.get("next_actions", [])
    later = summary.get("later_actions", [])
    safe_automation = summary.get("safe_automation", [])
    avoid_now = summary.get("avoid_now", [])
    blockers = summary["repo_profile"].get("major_blockers", [])

    lines = [
        "# 仓库检测与规范化报告",
        "",
        "## 1. 摘要",
        f"- 仓库类型：{', '.join(summary['repo_profile']['languages'])} / {summary['repo_profile']['monorepo_shape']}",
        f"- 本次使用工具：{', '.join(item['tool'] for item in chosen_tools)}",
        f"- 本次跳过工具：{', '.join(item['tool'] for item in skipped_tools) if skipped_tools else '无'}",
        f"- 核心结论：{summary['overall_verdict']}",
        f"- 建议总策略：{'; '.join(immediate[:2] or ['先把扫描可信度做实，再谈更硬的依赖门控。'])}",
        "",
        "## 2. 为什么用了这些工具",
        "",
        "### 2.1 Tach",
        f"- 是否使用：{'是' if any(item['tool'] == 'tach' for item in chosen_tools) else '否'}",
        "- 用它看什么：Python 模块边界、方向、公共接口和外部依赖一致性。",
        f"- 为什么适合当前仓库：{next((item['reason'] for item in skipped_tools if item['tool'] == 'tach'), '当前 wrapper 只输出 baseline，不自动跑 Tach。')}",
        "",
        "### 2.2 Dependency Cruiser",
        f"- 是否使用：{'是' if any(item['tool'] == 'dependency-cruiser' for item in chosen_tools) else '否'}",
        "- 用它看什么：JS/TS 的依赖方向、跨层导入和循环依赖。",
        f"- 为什么适合当前仓库：{next((item['reason'] for item in skipped_tools if item['tool'] == 'dependency-cruiser'), '当前 wrapper 只输出 baseline，不自动跑 Dependency Cruiser。')}",
        "",
        "### 2.3 Knip",
        f"- 是否使用：{'是' if any(item['tool'] == 'knip' for item in chosen_tools) else '否'}",
        "- 用它看什么：unused files、unused dependencies、unused exports。",
        f"- 为什么适合当前仓库：{next((item['reason'] for item in skipped_tools if item['tool'] == 'knip'), '当前 wrapper 只输出 baseline，不自动跑 Knip。')}",
        "",
        "## 3. 最高优先级问题",
        "",
    ]

    if not findings:
        lines.extend(["- 当前 baseline 没抓到高优先级结构问题，但这不等于外部图工具已经跑过。"])
    else:
        for finding in findings[:5]:
            lines.extend([
                f"### {finding['id']} {finding['title']}",
                f"- 工具：{finding['tool']}",
                f"- 严重程度：{finding['severity']}",
                f"- 置信度：{finding['confidence']}",
                f"- 是什么：{finding['evidence_summary']}",
                f"- 为什么重要：{finding['recommended_change_shape']}",
                f"- 建议做什么：{'；'.join(finding['validation_checks'])}",
                f"- 影响范围：{finding['scope']}",
                f"- 备注：{finding.get('notes') or '无'}",
                "",
            ])

    lines.extend([
        "## 4. 按工具展开",
        "",
        "### 4.1 Tach",
        f"- 关键发现：{next((item['reason'] for item in skipped_tools if item['tool'] == 'tach'), '已在 full audit 中执行。')}",
        "- 代表性问题：Python boundary governance 只有在 source_roots 和配置可信时才有意义。",
        "- 解释：先把扫描可信度修好，再谈硬边界门控。",
        "- 建议：别拿猜出来的模块图去做治理。",
        "",
        "### 4.2 Dependency Cruiser",
        f"- 关键发现：{next((item['reason'] for item in skipped_tools if item['tool'] == 'dependency-cruiser'), '已在 full audit 中执行。')}",
        "- 代表性问题：legacy repo 先 baseline，再阻断新增违规。",
        "- 解释：没有 baseline 的 depcruise 只是把历史债一次性全吼出来。",
        "- 建议：先把规则变成可信机器门，再谈追债。",
        "",
        "### 4.3 Knip",
        f"- 关键发现：{next((item['reason'] for item in skipped_tools if item['tool'] == 'knip'), '已在 full audit 中执行。')}",
        "- 代表性问题：entry/workspace coverage 不清时，unused-export 结论非常容易飘。",
        "- 解释：如果 entry 定义不全，Knip 只是在猜。",
        "- 建议：先修 entry/workspace coverage，再让 Knip 说狠话。",
        "",
        "## 5. 分阶段落地建议",
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
        "## 6. 可以安全自动化的部分",
        *(f"- {item}" for item in safe_automation),
        "",
        "## 7. 暂时不要做的事",
        *(f"- {item}" for item in avoid_now),
        "",
        "## 8. 本次扫描的局限与跳过项",
        *(f"- {item}" for item in blockers or ["当前 wrapper 只交付 baseline，不代替 Tach / Dependency Cruiser / Knip 的完整输出。"]),
        *(f"- 跳过 {item['tool']}: {item['reason']}" for item in skipped_tools),
        "",
    ])
    return "\n".join(lines)


def render_agent_brief(summary: dict[str, object]) -> str:
    findings = summary["findings"]
    lines = [
        "# Repo Audit Agent Brief",
        "",
        "## Repo profile",
        f"- languages: {', '.join(summary['repo_profile']['languages'])}",
        f"- monorepo_shape: {summary['repo_profile']['monorepo_shape']}",
        f"- package_managers: {', '.join(summary['repo_profile']['package_managers']) or 'none'}",
        f"- chosen_tools: {', '.join(item['tool'] for item in summary['tool_coverage']['chosen_tools'])}",
        f"- skipped_tools: {', '.join(item['tool'] for item in summary['tool_coverage']['skipped_tools']) or 'none'}",
        f"- major_blockers: {', '.join(summary['repo_profile'].get('major_blockers', [])) or 'none'}",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("- No baseline findings. Do not confuse that with a full external-tool audit.")
    else:
        for finding in findings:
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
                f"- autofix_allowed: {str(finding['autofix_allowed']).lower()}",
                f"- notes: {finding.get('notes') or 'none'}",
                "",
            ])

    lines.extend([
        "## Rollout plan",
        f"1. now: {'; '.join(summary.get('immediate_actions', [])) or 'stabilize scan credibility'}",
        f"2. next: {'; '.join(summary.get('next_actions', [])) or 'promote one external tool at a time'}",
        f"3. later: {'; '.join(summary.get('later_actions', [])) or 'raise strictness only after the repo stops lying to the scanners'}",
        "",
        "## Guardrails",
        "- keep destructive changes opt-in",
        "- do not delete files by default",
        "- prefer baseline before hard enforcement in legacy repos",
        "- separate scanner-confidence problems from real repo problems",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    files = iter_files(repo)
    profile = collect_repo_profile(repo, files)
    tool_coverage = build_tool_coverage(repo, profile)
    findings = build_findings(repo, profile, tool_coverage)
    overall_verdict = infer_verdict(findings)

    immediate_actions = []
    next_actions = []
    later_actions = []
    safe_automation = [
        "Validate the generated summary in CI before trying to fail merges on dependency rules.",
        "Keep lockfile and workspace metadata checks deterministic.",
    ]
    avoid_now = [
        "Do not pretend a graph tool ran when the wrapper only produced a baseline summary.",
        "Do not fail CI on every historical violation before a baseline exists.",
    ]

    if overall_verdict == "scan-blocked":
        immediate_actions.append("Fix repo shape and tool readiness before treating dependency conclusions as real governance.")
    if any(item.category == "config-gap" for item in findings):
        immediate_actions.append("Repair source_roots, workspace metadata, and tool config before tightening rules.")
    if any(item.category == "dependency-declaration-gap" for item in findings):
        next_actions.append("Restore trustworthy dependency metadata and lockfiles.")
    if not next_actions:
        next_actions.append("Promote one external graph tool at a time once the baseline stops lying.")
    later_actions.append("Turn changed-file dependency violations into a merge gate only after the baseline is trusted.")

    assumptions = [
        "Baseline mode does not execute external graph tools automatically.",
        "Tool coverage and repo profile are trusted more than speculative architecture findings in this wrapper.",
    ]

    summary = {
        "repo_profile": {
            key: value
            for key, value in profile.items()
            if key in {"languages", "monorepo_shape", "package_managers", "source_roots", "workspace_roots", "major_blockers", "notes"}
        },
        "tool_coverage": tool_coverage,
        "overall_verdict": overall_verdict,
        "findings": [asdict(item) for item in findings],
        "immediate_actions": immediate_actions,
        "next_actions": next_actions,
        "later_actions": later_actions,
        "safe_automation": safe_automation,
        "avoid_now": avoid_now,
        "assumptions": assumptions,
    }

    (out_dir / "repo-audit-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "repo-audit-report.md").write_text(render_human_report(summary) + "\n", encoding="utf-8")
    (out_dir / "repo-audit-agent-brief.md").write_text(render_agent_brief(summary), encoding="utf-8")
    print(f"Wrote {out_dir / 'repo-audit-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
