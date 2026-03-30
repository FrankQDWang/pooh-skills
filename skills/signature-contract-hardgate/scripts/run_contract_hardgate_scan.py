#!/usr/bin/env python3
"""Generate a conservative signature-contract-hardgate baseline summary."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RUNTIME_BIN_DIR = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN_DIR))

from tool_runner import ToolRun, run_locked_tool, run_semgrep_rules  # noqa: E402

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
}

TEXT_EXTS = {
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".graphql",
    ".gql",
}

GATE_ORDER = [
    "contract-surface",
    "compile-time-gates",
    "runtime-boundary-validation",
    "error-contract",
    "escape-hatch-governance",
    "architecture-boundaries",
    "contract-tests",
    "merge-governance",
]

SEMGRP_ESCAPE_HATCH_RULES = """
rules:
  - id: python-type-ignore
    languages: [python]
    severity: WARNING
    message: Escape hatch
    pattern: "# type: ignore"
  - id: ts-ignore
    languages: [typescript, javascript]
    severity: WARNING
    message: Escape hatch
    pattern-either:
      - pattern: "@ts-ignore"
      - pattern: "@ts-nocheck"
      - pattern: "eslint-disable"
"""


@dataclass
class GateState:
    gate: str
    state: str
    severity: str
    confidence: str
    summary: str


@dataclass
class Finding:
    id: str
    domain: str
    gate: str
    severity: str
    confidence: str
    current_state: str
    target_state: str
    title: str
    evidence_summary: str
    decision: str
    change_shape: str
    validation: str
    merge_gate: str
    autofix_allowed: bool
    notes: str = ""


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in filenames:
            path = Path(current_root) / name
            if path.suffix.lower() in TEXT_EXTS or name in {"CODEOWNERS", "pyproject.toml", "package.json", "tsconfig.json"}:
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
        if path.suffix in {".py", ".pyi"}:
            langs.add("python")
        elif path.suffix in {".ts", ".tsx"}:
            langs.add("typescript")
        elif path.suffix in {".js", ".jsx"}:
            langs.add("javascript")
    if not langs:
        langs.add("non-application")
    return sorted(langs)


def collect_signals(repo: Path, files: list[Path]) -> dict[str, object]:
    contract_surface: set[str] = set()
    api_schema_sources: set[str] = set()
    notes: list[str] = []
    workflow_files = sorted((repo / ".github" / "workflows").glob("*.y*ml")) if (repo / ".github" / "workflows").exists() else []
    codeowners_exists = any(path.exists() for path in (
        repo / ".github" / "CODEOWNERS",
        repo / "CODEOWNERS",
        repo / "docs" / "CODEOWNERS",
    ))

    signals = {
        "python_strict": False,
        "typed_lint": False,
        "ts_strict": False,
        "runtime_schema": False,
        "error_contract": False,
        "escape_hatch_count": 0,
        "architecture_config": False,
        "contract_tests": False,
        "workflow_files": [str(path.relative_to(repo)) for path in workflow_files],
        "codeowners": codeowners_exists,
    }

    for path in files:
        rel = str(path.relative_to(repo))
        text = read_text(path)
        lower = text.lower()
        name_lower = path.name.lower()

        if any(token in name_lower for token in ("openapi", "schema", "contract", "graphql")):
            contract_surface.add(rel)
            api_schema_sources.add(rel)
        if any(token in lower for token in ("basemodel", "typeddict", "annotated[", "zod.object", "jsonschema", "marshmallow", "pydantic")):
            contract_surface.add(rel)
        if any(token in lower for token in ("openapi", "graphql", "json schema", "response_model", "schema_extra", "zod.")):
            api_schema_sources.add(rel)

        if path.name == "pyproject.toml":
            if "[tool.basedpyright]" in lower and "strict = true" in lower:
                signals["python_strict"] = True
            if "[tool.pyright]" in lower and ("typecheckingmode = \"strict\"" in lower or "strict = true" in lower):
                signals["python_strict"] = True
            if "[tool.ruff]" in lower and ("per-file-ignores" in lower or "ignore =" in lower):
                signals["escape_hatch_count"] += lower.count("noqa")
            if "[tool.tach]" in lower:
                signals["architecture_config"] = True

        if path.name == "tsconfig.json" and '"strict"' in lower and "true" in lower:
            signals["ts_strict"] = True

        if path.name == "package.json":
            if "@typescript-eslint" in lower and ("projectservice" in lower or "recommendedtypechecked" in lower or "parseroptions" in lower):
                signals["typed_lint"] = True
            if "zod" in lower or "valibot" in lower or "io-ts" in lower or "joi" in lower:
                signals["runtime_schema"] = True
            if "dependency-cruiser" in lower or "depcruise" in lower:
                signals["architecture_config"] = True

        if any(token in lower for token in ("pydantic", "zod", "jsonschema.validate", "marshmallow", "schema.validate", "response_model")):
            signals["runtime_schema"] = True

        if any(token in lower for token in ("result[", "either[", "problem+json", "error_code", "errorcode", "typed error", "failure_reason")):
            signals["error_contract"] = True

        signals["escape_hatch_count"] += sum(lower.count(token) for token in (
            "# type: ignore",
            "@ts-ignore",
            "@ts-nocheck",
            "eslint-disable",
            "noqa",
        ))

        if "tests" in path.parts and any(token in lower for token in ("hypothesis", "schemathesis", "contract", "openapi", "schema")):
            signals["contract_tests"] = True

    if not contract_surface:
        notes.append("No obvious contract surface was detected in local code or schema files.")

    return {
        "repo_profile": {
            "languages": detect_languages(files),
            "shape": "workspace-monorepo" if len([path for path in files if path.name in {"package.json", "pyproject.toml"}]) > 2 else "single-repo",
            "contract_surface": sorted(contract_surface)[:12],
            "api_schema_sources": sorted(api_schema_sources)[:12],
            "notes": notes,
        },
        "signals": signals,
    }


def choose_js_targets(repo: Path, files: list[Path]) -> list[str]:
    targets: set[str] = set()
    for path in files:
        if path.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        rel = path.relative_to(repo)
        targets.add(rel.parts[0] if rel.parts else ".")
    return sorted(targets) or ["."]


def first_matching_file(files: list[Path], name: str) -> Path | None:
    for path in files:
        if path.name == name:
            return path
    return None


def collect_tool_signals(repo: Path, files: list[Path], repo_profile: dict[str, object], signals: dict[str, object]) -> list[ToolRun]:
    tool_runs: list[ToolRun] = []
    languages = set(repo_profile["languages"])

    if "python" in languages:
        for tool, args in (
            ("ruff", ["check", "--output-format", "json", str(repo)]),
            ("basedpyright", ["--outputjson", "-p", str(repo)]),
            ("tach", ["check", "--output", "json"]),
        ):
            run, payload = run_locked_tool(tool, args, repo, allow_exit_codes={0, 1})
            tool_runs.append(run)
            if tool == "basedpyright" and run.status in {"passed", "issues"}:
                signals["python_strict"] = True
            if tool == "tach" and run.status in {"passed", "issues"}:
                signals["architecture_config"] = True

    if {"typescript", "javascript"} & languages:
        tsconfig = first_matching_file(files, "tsconfig.json")
        if tsconfig is not None:
            tsc_run, _ = run_locked_tool("tsc", ["--noEmit", "--pretty", "false", "-p", str(tsconfig)], repo, allow_exit_codes={0, 1})
            tool_runs.append(tsc_run)
            if tsc_run.status in {"passed", "issues"}:
                signals["ts_strict"] = True
        js_targets = choose_js_targets(repo, files)
        eslint_run, _ = run_locked_tool(
            "typescript-eslint-stack",
            ["--format", "json", "--ext", ".js,.jsx,.ts,.tsx", *js_targets],
            repo,
            allow_exit_codes={0, 1},
        )
        tool_runs.append(eslint_run)
        if eslint_run.status in {"passed", "issues"}:
            signals["typed_lint"] = True

        dep_run, _ = run_locked_tool("dependency-cruiser", ["--no-config", "-T", "json", *js_targets], repo, allow_exit_codes={0, 1})
        tool_runs.append(dep_run)
        if dep_run.status in {"passed", "issues"}:
            signals["architecture_config"] = True

    semgrep_run, semgrep_payload = run_semgrep_rules(SEMGRP_ESCAPE_HATCH_RULES, repo, [str(repo)])
    tool_runs.append(semgrep_run)
    if isinstance(semgrep_payload, dict):
        signals["escape_hatch_count"] += len(semgrep_payload.get("results") or [])

    signals.setdefault("tool_notes", [])
    for item in tool_runs:
        if item.status == "failed":
            signals["tool_notes"].append(f"{item.tool}: {item.summary}")
    return tool_runs


def gate_state(gate: str, signals: dict[str, object], repo_profile: dict[str, object]) -> GateState:
    langs = set(repo_profile["languages"])
    contract_surface = repo_profile["contract_surface"]
    escape_hatches = int(signals["escape_hatch_count"])
    workflow_files = signals["workflow_files"]

    if gate == "contract-surface":
        if not contract_surface:
            return GateState(gate, "missing", "high", "high", "No clear contract layer, schema source, or boundary model surface is visible locally.")
        if len(contract_surface) < 3:
            return GateState(gate, "partial", "medium", "medium", "Some contract artifacts exist, but the surface is still thin and easy for AI to route around.")
        return GateState(gate, "enforced", "low", "medium", "A visible contract surface exists in code or schema artifacts.")

    if gate == "compile-time-gates":
        python_strict = bool(signals["python_strict"])
        ts_strict = bool(signals["ts_strict"])
        typed_lint = bool(signals["typed_lint"])
        if "python" in langs and python_strict and (("typescript" not in langs and "javascript" not in langs) or typed_lint or ts_strict):
            return GateState(gate, "enforced", "low", "medium", "Strict local type signals are visible for the languages present.")
        if python_strict or ts_strict or typed_lint:
            return GateState(gate, "partial", "medium", "medium", "Some compile-time gates exist, but the visible strictness is not strong enough to call this a hardened machine gate.")
        if any(path.endswith(".yml") or path.endswith(".yaml") for path in workflow_files):
            return GateState(gate, "theater", "high", "medium", "Workflow files exist, but no visible strict type or typed-lint gate is configured locally.")
        return GateState(gate, "missing", "high", "high", "No visible strict compile-time gate is present.")

    if gate == "runtime-boundary-validation":
        if bool(signals["runtime_schema"]):
            return GateState(gate, "partial", "medium", "medium", "Runtime schema signals exist, but local evidence does not prove all critical boundaries are covered.")
        return GateState(gate, "missing", "high", "high", "No convincing runtime-boundary validation surface is visible locally.")

    if gate == "error-contract":
        if bool(signals["error_contract"]):
            return GateState(gate, "partial", "medium", "medium", "The repo hints at explicit error modeling, but the local evidence is too thin to call it a real contract.")
        return GateState(gate, "missing", "medium", "medium", "Failure paths are not visibly modeled as a stable contract.")

    if gate == "escape-hatch-governance":
        if escape_hatches >= 8:
            return GateState(gate, "theater", "high", "high", "Escape hatches are common enough that any stated contract posture is easy to bypass.")
        if escape_hatches >= 2:
            return GateState(gate, "partial", "medium", "medium", "Some escape hatches are visible; governance exists at best in a weak form.")
        return GateState(gate, "enforced", "low", "low", "Very few visible escape hatches were found in the local checkout.")

    if gate == "architecture-boundaries":
        if bool(signals["architecture_config"]) and workflow_files:
            return GateState(gate, "enforced", "low", "medium", "Boundary tooling is configured locally and CI workflows are present.")
        if bool(signals["architecture_config"]):
            return GateState(gate, "theater", "medium", "medium", "Boundary tooling config exists, but local evidence does not prove it blocks merges.")
        return GateState(gate, "missing", "medium", "high", "No local boundary-governance config was detected.")

    if gate == "contract-tests":
        if bool(signals["contract_tests"]):
            return GateState(gate, "partial", "medium", "medium", "Contract-oriented tests exist, but local evidence does not prove they gate the right paths.")
        return GateState(gate, "missing", "medium", "medium", "No visible contract-test surface was detected.")

    if gate == "merge-governance":
        if workflow_files or bool(signals["codeowners"]):
            return GateState(gate, "unverified", "medium", "high", "Workflow or CODEOWNERS files exist locally, but remote enforcement is not visible from this checkout.")
        return GateState(gate, "missing", "medium", "high", "No local merge-governance surface was detected.")

    raise ValueError(f"Unsupported gate: {gate}")


def build_findings(gates: list[GateState], repo_profile: dict[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    next_id = 1

    state_priority = {"missing": 0, "theater": 1, "partial": 2, "unverified": 3, "enforced": 4, "hardened": 5}
    ordered = sorted(gates, key=lambda item: (state_priority.get(item.state, 9), item.gate))

    for gate in ordered:
        if gate.state in {"enforced", "hardened"}:
            continue
        target_state = "enforced" if gate.gate != "merge-governance" else "hardened"
        decision = "harden" if gate.state in {"partial", "unverified"} else "adopt"
        if gate.gate in {"architecture-boundaries", "compile-time-gates"} and gate.state == "theater":
            decision = "replace"
        merge_gate = "unverified" if gate.state == "unverified" else ("block-now" if gate.severity in {"critical", "high"} else "block-changed-files")
        autofix_allowed = gate.gate in {"contract-surface", "compile-time-gates"} and gate.state == "partial"
        title = {
            "contract-surface": "Contract surface is too thin or missing",
            "compile-time-gates": "Compile-time gates are softer than the repo claims",
            "runtime-boundary-validation": "Runtime boundary validation is not visibly guarding ingress/egress",
            "error-contract": "Failure paths are not modeled as a stable contract",
            "escape-hatch-governance": "Escape hatches are easier to use than the rules imply",
            "architecture-boundaries": "Boundary governance is missing or decorative",
            "contract-tests": "Contract tests are missing or too weak to trust",
            "merge-governance": "Merge governance exists only as a local hint",
        }[gate.gate]
        change_shape = {
            "contract-surface": "Centralize real boundary models and make them the only public contract layer.",
            "compile-time-gates": "Promote strict type and typed-lint checks into a real machine gate before adding more annotations.",
            "runtime-boundary-validation": "Put runtime schema validation on real ingress/egress paths instead of leaving types as documentation.",
            "error-contract": "Model recoverable failures explicitly instead of hiding them behind broad exceptions.",
            "escape-hatch-governance": "Reduce `ignore` / `noqa` / `ts-ignore` debt and make new escapes visible in review.",
            "architecture-boundaries": "Back the architecture story with Tach or dependency-cruiser enforcement that actually runs.",
            "contract-tests": "Add contract-oriented tests on the real public boundary instead of relying on green happy-path tests.",
            "merge-governance": "Treat local workflow files as hints only; verify required checks and CODEOWNERS on the remote platform.",
        }[gate.gate]
        validation = {
            "merge-governance": "Verify required checks, CODEOWNERS enforcement, and rulesets in the remote host instead of assuming they are active.",
        }.get(gate.gate, f"Rerun the hardgate after implementing a concrete {gate.gate} machine gate.")

        findings.append(Finding(
            id=f"sch-{next_id:03d}",
            domain="repo",
            gate=gate.gate,
            severity=gate.severity,
            confidence=gate.confidence,
            current_state=gate.state,
            target_state=target_state,
            title=title,
            evidence_summary=gate.summary,
            decision=decision,
            change_shape=change_shape,
            validation=validation,
            merge_gate=merge_gate,
            autofix_allowed=autofix_allowed,
            notes="This baseline is intentionally conservative and local-only." if gate.state == "unverified" else "",
        ))
        next_id += 1

    return findings[:6]


def infer_verdict(gates: list[GateState]) -> str:
    states = {gate.gate: gate.state for gate in gates}
    if states["contract-surface"] in {"missing", "theater"} and states["runtime-boundary-validation"] == "missing":
        return "contract-theater"
    if any(states[gate] in {"missing", "theater"} for gate in (
        "compile-time-gates",
        "runtime-boundary-validation",
        "architecture-boundaries",
    )):
        return "soft-gates"
    if sum(1 for gate in gates if gate.state in {"enforced", "hardened"}) >= 6 and states["merge-governance"] != "missing":
        return "hard-harness"
    return "real-gates"


def render_human_report(summary: dict[str, object]) -> str:
    findings = summary["findings"]
    unverified = summary.get("unverified", [])
    immediate_actions = summary.get("immediate_actions", [])
    next_actions = summary.get("next_actions", [])
    later_actions = summary.get("later_actions", [])
    repo_profile = summary["repo_profile"]
    tool_runs = summary.get("tool_runs", [])

    lines = [
        "# 签名即契约硬门控审计报告",
        "",
        "## 一句话判决",
        f"- **总体结论**：{summary['overall_verdict']}",
        f"- **一句人话**：{summary['assumptions'][0] if summary.get('assumptions') else '本地能看到的是线索，不是已经上锁的事实。'}",
        "",
        "## 这套仓库现在在教 AI 学坏什么",
        "- 看到配置文件就脑补已经有硬门。",
        "- 把类型注解当成运行时边界校验的替代品。",
        "- 只要 workflow 存在就默认 merge governance 已经上锁。",
        "",
        "## 仓库画像",
        f"- 语言 / 形态：{', '.join(repo_profile['languages'])} / {repo_profile['shape']}",
        f"- 契约表面：{', '.join(repo_profile.get('contract_surface', [])[:5]) or '未见明确契约层'}",
        f"- 可见门控：{', '.join(gate['gate'] for gate in summary['gate_states'] if gate['state'] in {'partial', 'enforced', 'hardened'}) or '很弱'}",
        f"- 不可见但关键：{'; '.join(unverified) or '无'}",
        "",
        "## 真实工具执行",
        *(f"- {item['tool']}: {item['status']} — {item['summary']}" for item in tool_runs),
        "",
        "## 关键问题（已确认）",
        "",
    ]
    if not findings:
        lines.append("- 当前 baseline 没抓到已确认问题，但这不等于远端合并门已经成立。")
    else:
        for idx, finding in enumerate(findings[:4], start=1):
            lines.extend([
                f"### {idx}. {finding['title']}",
                f"- **状态**：{finding['current_state']}",
                f"- **严重性**：{finding['severity']}",
                f"- **置信度**：{finding['confidence']}",
                "",
                "**是什么**  ",
                finding["evidence_summary"],
                "",
                "**为什么重要**  ",
                finding["change_shape"],
                "",
                "**建议做什么**  ",
                finding["validation"],
                "",
                "**给非程序员的人话解释**  ",
                "仓库里写了不少规则的影子，但机器能不能真的在关键入口把错拦下，还不能靠想象来证明。",
                "",
                "---",
                "",
            ])

    lines.extend([
        "## 无法从本地仓库证明，但必须说清楚的事",
        *(f"- {item}" for item in unverified or ["看不到远端 required checks、rulesets 和真实 CODEOWNERS 执行状态。"]),
        "",
        "## 行动顺序",
        "",
        "### 立刻做",
        *(f"- {item}" for item in immediate_actions),
        "",
        "### 本周做",
        *(f"- {item}" for item in next_actions),
        "",
        "### 之后做",
        *(f"- {item}" for item in later_actions),
        "",
        "## 最后一句",
        "规则写进仓库不够，写进合并门才算数。",
        "",
    ])
    return "\n".join(lines)


def render_agent_brief(summary: dict[str, object]) -> str:
    lines = [
        "# Signature Contract Hardgate — Agent Brief",
        "",
        "## Repo profile",
        f"- `repo_profile`: {summary['repo_profile']['shape']}",
        f"- `languages`: {', '.join(summary['repo_profile']['languages'])}",
        f"- `contract_surface`: {', '.join(summary['repo_profile'].get('contract_surface', [])) or 'none'}",
        f"- `overall_verdict`: {summary['overall_verdict']}",
        "",
        "## Tool runs",
        *(f"- {item['tool']}: {item['status']} ({item['summary']})" for item in summary.get("tool_runs", [])),
        "",
        "## Findings",
        "",
    ]
    if not summary["findings"]:
        lines.append("- No confirmed findings. Treat that as a local-baseline outcome, not proof that merge enforcement is real.")
    else:
        for finding in summary["findings"]:
            lines.extend([
                f"### {finding['id']} — {finding['title']}",
                f"- `domain`: {finding['domain']}",
                f"- `gate`: {finding['gate']}",
                f"- `severity`: {finding['severity']}",
                f"- `confidence`: {finding['confidence']}",
                f"- `current_state`: {finding['current_state']}",
                f"- `target_state`: {finding['target_state']}",
                f"- `evidence_summary`: {finding['evidence_summary']}",
                f"- `decision`: {finding['decision']}",
                f"- `change_shape`: {finding['change_shape']}",
                f"- `validation`: {finding['validation']}",
                f"- `merge_gate`: {finding['merge_gate']}",
                f"- `autofix_allowed`: {str(finding['autofix_allowed']).lower()}",
                f"- `notes`: {finding.get('notes') or 'none'}",
                "",
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
    collected = collect_signals(repo, files)
    repo_profile = collected["repo_profile"]
    signals = collected["signals"]
    tool_runs = collect_tool_signals(repo, files, repo_profile, signals)
    repo_profile["notes"].extend(signals.get("tool_notes", []))
    gates = [gate_state(name, signals, repo_profile) for name in GATE_ORDER]
    findings = build_findings(gates, repo_profile)
    overall_verdict = infer_verdict(gates)

    summary = {
        "repo_profile": repo_profile,
        "overall_verdict": overall_verdict,
        "gate_states": [asdict(item) for item in gates],
        "findings": [asdict(item) for item in findings],
        "assumptions": [
            "This baseline uses only local repository evidence and never assumes remote enforcement exists.",
            "CODEOWNERS and workflow files are treated as hints until platform-side required checks are verified.",
        ],
        "unverified": [
            "Merge governance is local-only evidence unless required checks, rulesets, and CODEOWNERS enforcement are confirmed remotely."
        ] if any(gate.state == "unverified" for gate in gates) else [],
        "immediate_actions": [
            "Stop calling comments and type hints a contract unless runtime validation and compile-time gates both exist.",
            "Make one visible contract surface the source of truth instead of letting each boundary invent its own shape.",
        ],
        "next_actions": [
            "Promote strict typing, runtime schemas, and architecture rules into CI-visible checks.",
            "Convert merge governance from local files into verified required checks and code-owner review.",
        ],
        "later_actions": [
            "Raise changed-files strictness only after the legacy surface is mapped and quarantined.",
            "Keep escape hatches exceptional, named, and review-visible.",
        ],
        "tool_runs": [item.to_dict() for item in tool_runs],
    }

    (out_dir / "contract-hardgate-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "contract-hardgate-human-report.md").write_text(
        render_human_report(summary) + "\n",
        encoding="utf-8",
    )
    (out_dir / "contract-hardgate-agent-brief.md").write_text(
        render_agent_brief(summary),
        encoding="utf-8",
    )
    print(f"Wrote {out_dir / 'contract-hardgate-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
