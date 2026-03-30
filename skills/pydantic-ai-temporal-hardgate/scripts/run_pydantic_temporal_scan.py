#!/usr/bin/env python3
"""Generate a conservative Pydantic AI + Temporal baseline summary."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
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
}

TEXT_EXTS = {".py", ".toml", ".json", ".yaml", ".yml", ".md"}
GATE_ORDER = [
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
]

TEMPORAL_MARKERS = (
    "temporalio.workflow",
    "@workflow.defn",
    "@workflow.run",
    "Worker(",
    "workflow.execute_activity",
)
AGENT_MARKERS = (
    "pydantic_ai",
    "Agent(",
    "TemporalAgent(",
    "PydanticAIPlugin",
    "PydanticAIWorkflow",
)
DOC_HINTS = ("temporal", "pydantic-ai", "pydantic_ai")
SEMGRP_TEMPORAL_RULES = """
rules:
  - id: workflow-network-call
    languages: [python]
    severity: ERROR
    message: Network or remote side effect inside Python workflow surface
    patterns:
      - pattern-either:
          - pattern: requests.$METHOD(...)
          - pattern: httpx.$METHOD(...)
          - pattern: subprocess.$METHOD(...)
  - id: raw-agent-construction
    languages: [python]
    severity: WARNING
    message: Raw Agent construction
    pattern: Agent(...)
  - id: temporal-agent-model-param
    languages: [python]
    severity: WARNING
    message: TemporalAgent receives an explicit model argument
    pattern: TemporalAgent(..., model=$MODEL, ...)
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
    gate: str
    severity: str
    confidence: str
    current_state: str
    target_state: str
    locus: str
    title: str
    evidence_summary: str
    decision: str
    change_shape: str
    validation: str
    merge_gate: str
    autofix_allowed: bool
    notes: str = ""


def blocked_dependency_failure() -> dict[str, object]:
    return {
        "name": "context7",
        "kind": "mcp",
        "required_for": "pydantic-ai-temporal-hardgate",
        "attempted_command": "Context7 live-doc verification",
        "failure_reason": "Context7-backed live documentation evidence was not provided",
        "blocked_by_security": False,
        "blocked_by_permissions": False,
        "blocked_by_network": False,
    }


def load_doc_evidence(path: str | None) -> list[dict[str, object]]:
    if not path:
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("doc_verification", [])
    else:
        raise ValueError("doc evidence must be a list or object with doc_verification")
    required = {
        "subject",
        "library",
        "library_id",
        "version_hint",
        "queries",
        "status",
        "checked_at",
        "source_ref",
        "notes",
    }
    normalized: list[dict[str, object]] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"doc_verification[{idx}] must be an object")
        missing = required - set(entry)
        if missing:
            raise ValueError(f"doc_verification[{idx}] missing keys: {sorted(missing)}")
        normalized.append(
            {
                "subject": str(entry["subject"]),
                "library": str(entry["library"]),
                "library_id": str(entry["library_id"]),
                "version_hint": str(entry["version_hint"]),
                "queries": [str(item) for item in entry["queries"]],
                "status": str(entry["status"]),
                "checked_at": str(entry["checked_at"]),
                "source_ref": str(entry["source_ref"]),
                "notes": str(entry["notes"]),
            }
        )
    return normalized


def live_doc_ready(entries: list[dict[str, object]]) -> bool:
    verified_subjects = {str(entry["subject"]).lower() for entry in entries if entry.get("status") == "verified"}
    return any("temporal" in subject for subject in verified_subjects) and any("pydantic" in subject for subject in verified_subjects)


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in filenames:
            path = Path(current_root) / name
            if path.suffix.lower() in TEXT_EXTS or name in {"README.md", "AGENTS.md", "CODEOWNERS", "pyproject.toml"}:
                files.append(path)
    return files


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def annotation_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = annotation_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return annotation_name(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return decorator_name(node.func)
    if isinstance(node, ast.Attribute):
        base = decorator_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def collect_signals(repo: Path, files: list[Path]) -> dict[str, object]:
    temporal_surface: list[str] = []
    agent_surface: list[str] = []
    docs_surface: list[str] = []
    workflow_files: list[str] = []
    py_files: list[Path] = []
    signal_text_chunks: list[str] = []

    workflow_hazards: list[str] = []
    sandbox_escapes: list[str] = []
    raw_agent_in_workflow: list[str] = []
    raw_model_in_temporal_agent: list[str] = []
    tool_contract_issues: list[str] = []
    deps_mismatch: list[str] = []

    official_path_markers = {
        "TemporalAgent": False,
        "PydanticAIPlugin": False,
        "PydanticAIWorkflow": False,
    }

    replay_signals = 0
    time_skipping_signals = 0
    fake_model_signals = 0
    wrong_docs = []

    workflow_hazard_patterns = (
        re.compile(r"\brequests\.(get|post|put|patch|delete)\s*\("),
        re.compile(r"\bhttpx\.(get|post|put|patch|delete)\s*\("),
        re.compile(r"\bsubprocess\.", re.IGNORECASE),
        re.compile(r"\bopen\s*\("),
        re.compile(r"\bdatetime\.now\s*\("),
        re.compile(r"\btime\.time\s*\("),
        re.compile(r"\buuid\.uuid4\s*\("),
        re.compile(r"\brandom\.", re.IGNORECASE),
    )

    for path in files:
        rel_path = path.relative_to(repo)
        if rel_path.parts and rel_path.parts[0] == "skills":
            continue
        rel = str(rel_path)
        text = read_text(path)
        lower = text.lower()
        if path.suffix == ".py":
            py_files.append(path)
            signal_text_chunks.append(text[:12000])
        elif path.name == "pyproject.toml":
            signal_text_chunks.append(text[:12000])

        if path.suffix == ".py" and any(marker.lower() in lower for marker in TEMPORAL_MARKERS):
            temporal_surface.append(rel)
        if path.suffix == ".py" and any(marker.lower() in lower for marker in AGENT_MARKERS):
            agent_surface.append(rel)
        if path.name.startswith(("README", "AGENTS")) or "docs" in path.parts:
            if any(hint in lower for hint in DOC_HINTS):
                docs_surface.append(rel)
        if path.suffix == ".py" and ("@workflow.defn" in lower or "temporalio.workflow" in lower):
            workflow_files.append(rel)

        if path.suffix == ".py" and "temporalagent(" in lower:
            official_path_markers["TemporalAgent"] = True
        if path.suffix == ".py" and "pydanticaiplugin" in lower:
            official_path_markers["PydanticAIPlugin"] = True
        if path.suffix == ".py" and "pydanticaiworkflow" in lower:
            official_path_markers["PydanticAIWorkflow"] = True

        if path.suffix == ".py" and workflow_files and rel in workflow_files:
            for idx, line in enumerate(text.splitlines(), start=1):
                if any(pattern.search(line) for pattern in workflow_hazard_patterns):
                    workflow_hazards.append(f"{rel}:{idx}: {line.strip()}")
                if "agent(" in line and "temporalagent(" not in line.lower():
                    raw_agent_in_workflow.append(f"{rel}:{idx}: {line.strip()}")

        if path.suffix == ".py" and ("sandbox_unrestricted" in lower or "sandboxed=false" in lower or "unsandboxedworkflowrunner" in lower):
            sandbox_escapes.append(rel)

        if path.suffix == ".py" and "temporalagent(" in lower and ("openaimodel(" in lower or "anthropicmodel(" in lower or "model=" in lower):
            raw_model_in_temporal_agent.append(rel)

        if path.suffix == ".py" and ("workflowreplayer" in lower or "replay" in lower):
            replay_signals += 1
        if path.suffix == ".py" and ("start_time_skipping" in lower or "time_skipping" in lower):
            time_skipping_signals += 1
        if path.suffix == ".py" and ("testmodel" in lower or "functionmodel" in lower or "agent.override" in lower or "allow_model_requests" in lower):
            fake_model_signals += 1

        if "asyncio.sleep" in lower and ("always wrong" in lower or "forbidden" in lower):
            wrong_docs.append(f"{rel}: docs treat asyncio.sleep as universally forbidden in workflows")

    joined = "\n".join(signal_text_chunks).lower()
    if "args_validator" in joined and "modelretry" not in joined:
        tool_contract_issues.append("args_validator appears without visible ModelRetry handling")
    if "deps=" in joined and "deps_type" not in joined:
        deps_mismatch.append("`deps=` appears, but no visible `deps_type=` contract was found")

    for path in py_files:
        try:
            tree = ast.parse(read_text(path))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decos = {decorator_name(item).split(".")[-1] for item in node.decorator_list}
            if "tool" in decos:
                if not node.args.args:
                    tool_contract_issues.append(f"{path.relative_to(repo)}:{node.lineno}: @agent.tool without arguments")
                else:
                    first = node.args.args[0]
                    if "RunContext" not in annotation_name(first.annotation):
                        tool_contract_issues.append(
                            f"{path.relative_to(repo)}:{node.lineno}: @agent.tool first parameter is not annotated as RunContext"
                        )
            if "tool_plain" in decos and node.args.args:
                first = node.args.args[0]
                if "RunContext" in annotation_name(first.annotation):
                    tool_contract_issues.append(
                        f"{path.relative_to(repo)}:{node.lineno}: @agent.tool_plain unexpectedly takes RunContext"
                    )

    applicable = bool(temporal_surface and agent_surface)
    return {
        "applicable": applicable,
        "repo_profile": {
            "languages": ["python"] if py_files else ["non-application"],
            "shape": "single-repo",
            "workflow_surface": sorted(set(workflow_files or temporal_surface))[:12],
            "agent_surface": sorted(set(agent_surface))[:12],
            "docs_surface": sorted(set(docs_surface))[:12],
            "notes": [
                "Applicability requires both Temporal and pydantic-ai surfaces."
            ],
        },
        "signals": {
            "workflow_hazards": workflow_hazards,
            "sandbox_escapes": sorted(set(sandbox_escapes)),
            "raw_agent_in_workflow": raw_agent_in_workflow,
            "raw_model_in_temporal_agent": raw_model_in_temporal_agent,
            "tool_contract_issues": tool_contract_issues,
            "deps_mismatch": deps_mismatch,
            "official_path_markers": official_path_markers,
            "replay_signals": replay_signals,
            "time_skipping_signals": time_skipping_signals,
            "fake_model_signals": fake_model_signals,
            "wrong_docs": wrong_docs,
            "workflow_files": workflow_files,
            "has_governance_files": bool((repo / ".github" / "workflows").exists() or (repo / ".github" / "CODEOWNERS").exists() or (repo / "CODEOWNERS").exists()),
        },
    }


def collect_tool_runs(repo: Path, applicable: bool) -> tuple[list[ToolRun], dict[str, Any]]:
    tool_runs: list[ToolRun] = []
    payloads: dict[str, Any] = {}
    if not applicable:
        return tool_runs, payloads

    for tool, args in (
        ("ruff", ["check", "--output-format", "json", str(repo)]),
        ("basedpyright", ["--outputjson", "-p", str(repo)]),
    ):
        run, payload = run_locked_tool(tool, args, repo, allow_exit_codes={0, 1})
        tool_runs.append(run)
        payloads[tool] = payload

    semgrep_run, semgrep_payload = run_semgrep_rules(SEMGRP_TEMPORAL_RULES, repo, [str(repo)])
    tool_runs.append(semgrep_run)
    payloads["semgrep"] = semgrep_payload
    return tool_runs, payloads


def not_applicable_gate(gate: str) -> GateState:
    return GateState(gate, "not-applicable", "low", "high", "This repository does not expose both Temporal and pydantic-ai durable surfaces.")


def build_gate_state(gate: str, applicable: bool, signals: dict[str, object], repo_profile: dict[str, object]) -> GateState:
    if not applicable:
        return not_applicable_gate(gate)

    official = signals["official_path_markers"]
    official_count = sum(1 for value in official.values() if value)
    verification_ready = int(signals["replay_signals"]) + int(signals["time_skipping_signals"]) + int(signals["fake_model_signals"])

    if gate == "workflow-determinism":
        if signals["workflow_hazards"]:
            return GateState(gate, "broken", "critical", "high", "Workflow files contain direct I/O, wall-clock, randomness, or similar non-deterministic calls.")
        return GateState(gate, "sound", "low", "medium", "No direct workflow determinism break was found by the local scan.")

    if gate == "sandbox-discipline":
        if signals["sandbox_escapes"]:
            return GateState(gate, "unsafe", "high", "high", "Local code explicitly disables or bypasses the Temporal sandbox.")
        return GateState(gate, "sound", "low", "medium", "No sandbox escape marker was found locally.")

    if gate == "durable-agent-path":
        if signals["raw_agent_in_workflow"]:
            return GateState(gate, "broken", "critical", "high", "Raw Agent usage is visible inside workflow code instead of staying on the official durable path.")
        if signals["raw_model_in_temporal_agent"]:
            return GateState(gate, "unsafe", "high", "medium", "TemporalAgent usage appears to pass a raw model instance directly, which is not a safe durable default.")
        if official_count == 0:
            return GateState(gate, "fragile", "high", "medium", "Temporal and pydantic-ai are both present, but no official durable-path marker was found.")
        return GateState(gate, "sound", "low", "medium", "At least one official durable-path marker is visible locally.")

    if gate == "agent-freeze-drift":
        if official_count == 0:
            return GateState(gate, "fragile", "medium", "low", "Without the official durable path, durable-agent freeze behavior is hard to trust.")
        return GateState(gate, "sound", "low", "low", "No direct agent-freeze drift signal was found locally.")

    if gate == "tool-contracts":
        if signals["tool_contract_issues"]:
            return GateState(gate, "broken", "high", "high", "Local tool decorators and signatures disagree with the documented Pydantic AI contract.")
        return GateState(gate, "sound", "low", "medium", "No obvious local tool-contract violation was detected.")

    if gate == "dependency-contracts":
        if signals["deps_mismatch"]:
            return GateState(gate, "unsafe", "medium", "medium", "Runtime deps usage is visible without a matching deps_type contract.")
        return GateState(gate, "sound", "low", "low", "No obvious deps contract mismatch was detected.")

    if gate == "validation-retry-path":
        if "args_validator appears without visible ModelRetry handling" in signals["tool_contract_issues"]:
            return GateState(gate, "unsafe", "high", "medium", "args_validator usage is visible without local evidence of the intended ModelRetry recovery path.")
        return GateState(gate, "sound", "low", "low", "No obvious validation/retry path break was found locally.")

    if gate == "verification-harness":
        if verification_ready == 0:
            return GateState(gate, "unsafe", "high", "high", "No replay, time-skipping, or fake-model harness evidence was found.")
        if verification_ready < 3:
            return GateState(gate, "fragile", "medium", "medium", "Some verification signals exist, but the harness still looks partial.")
        return GateState(gate, "hardened", "low", "medium", "Replay, time-skipping, and fake-model style verification signals are all visible.")

    if gate == "doc-grounding":
        if signals["wrong_docs"]:
            return GateState(gate, "fragile", "medium", "high", "Local docs teach at least one rule that is too blunt or simply wrong.")
        if repo_profile["docs_surface"]:
            return GateState(gate, "sound", "low", "low", "Docs mention the durable surface without obvious local rule pollution.")
        return GateState(gate, "fragile", "low", "low", "No visible docs surface was found to ground future agent behavior.")

    if gate == "merge-governance":
        if signals["has_governance_files"]:
            return GateState(gate, "unverified", "medium", "high", "Local workflows or CODEOWNERS exist, but remote enforcement is not visible from this checkout.")
        return GateState(gate, "fragile", "medium", "high", "No visible merge-governance surface was found locally.")

    raise ValueError(f"Unsupported gate: {gate}")


def build_findings(gates: list[GateState], signals: dict[str, object], tool_runs: list[ToolRun]) -> list[Finding]:
    findings: list[Finding] = []
    next_id = 1
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    for gate in sorted(gates, key=lambda item: (severity_rank[item.severity], item.gate)):
        if gate.state in {"sound", "hardened", "not-applicable"}:
            continue
        evidence = {
            "workflow-determinism": signals["workflow_hazards"][:2],
            "sandbox-discipline": signals["sandbox_escapes"][:2],
            "durable-agent-path": (signals["raw_agent_in_workflow"] or signals["raw_model_in_temporal_agent"])[:2],
            "tool-contracts": signals["tool_contract_issues"][:2],
            "dependency-contracts": signals["deps_mismatch"][:2],
            "validation-retry-path": signals["tool_contract_issues"][:2],
            "verification-harness": [
                f"replay={signals['replay_signals']}",
                f"time_skipping={signals['time_skipping_signals']}",
                f"fake_model={signals['fake_model_signals']}",
            ],
            "doc-grounding": signals["wrong_docs"][:2],
            "merge-governance": ["Remote required checks and CODEOWNERS enforcement are not visible locally."],
            "agent-freeze-drift": ["Official durable-path markers are too weak to trust freeze behavior."],
        }.get(gate.gate, [gate.summary])

        title = {
            "workflow-determinism": "Workflow determinism is locally broken",
            "sandbox-discipline": "Sandbox discipline is bypassed",
            "durable-agent-path": "Durable agent path is weaker than the repo claims",
            "agent-freeze-drift": "Durable-agent freeze behavior is not well anchored",
            "tool-contracts": "Tool contracts disagree with Pydantic AI expectations",
            "dependency-contracts": "Dependency contracts look weaker than runtime usage",
            "validation-retry-path": "Validation/retry semantics are not locally proven",
            "verification-harness": "Verification harness is too thin to trust replay safety",
            "doc-grounding": "Docs are missing or teach an unsafe simplification",
            "merge-governance": "Merge governance is still only a local hint",
        }[gate.gate]
        decision = "harden"
        if gate.state in {"broken", "unsafe"} and gate.gate in {"workflow-determinism", "durable-agent-path", "tool-contracts"}:
            decision = "replace"
        elif gate.state == "unverified":
            decision = "defer"
        merge_gate = "unverified" if gate.state == "unverified" else ("block-now" if gate.severity in {"critical", "high"} else "block-changed-files")

        findings.append(Finding(
            id=f"pta-{next_id:03d}",
            gate=gate.gate,
            severity=gate.severity,
            confidence=gate.confidence,
            current_state=gate.state,
            target_state="sound" if gate.gate != "verification-harness" else "hardened",
            locus=", ".join(evidence) or "repo",
            title=title,
            evidence_summary=gate.summary,
            decision=decision,
            change_shape={
                "workflow-determinism": "Move non-deterministic work out of workflows and back into activities or guarded edges.",
                "sandbox-discipline": "Remove unsandboxed workflow paths unless they are narrowly justified and isolated.",
                "durable-agent-path": "Use TemporalAgent / PydanticAIPlugin / PydanticAIWorkflow instead of raw agent glue in workflow paths.",
                "agent-freeze-drift": "Instantiate and freeze the durable agent configuration on a stable path instead of mutating it opportunistically.",
                "tool-contracts": "Align `@agent.tool` / `@agent.tool_plain`, RunContext position, and validator behavior with the documented contract.",
                "dependency-contracts": "Make deps_type and runtime deps agree before trusting agent execution to stay deterministic.",
                "validation-retry-path": "Treat recoverable validation failures as ModelRetry paths instead of generic exceptions.",
                "verification-harness": "Add replay, time-skipping, and fake-model coverage before claiming durable safety.",
                "doc-grounding": "Teach the durable rules accurately in README / AGENTS so future agents stop copying bad folklore.",
                "merge-governance": "Verify required checks and code-owner enforcement remotely instead of assuming local files are enough.",
            }[gate.gate],
            validation="Rerun the Temporal hardgate wrapper and confirm the gate state improved with local evidence.",
            merge_gate=merge_gate,
            autofix_allowed=False,
            notes="This baseline never upgrades a remote-only claim beyond unverified.",
        ))
        next_id += 1

    run_by_tool = {item.tool: item for item in tool_runs}
    if run_by_tool.get("ruff") and run_by_tool["ruff"].status == "issues":
        findings.append(Finding(
            id=f"pta-{next_id:03d}",
            gate="tool-contracts",
            severity="medium",
            confidence="high",
            current_state="fragile",
            target_state="sound",
            locus="locked ruff run",
            title="Ruff reported Python issues inside the durable surface",
            evidence_summary=run_by_tool["ruff"].summary,
            decision="harden",
            change_shape="Resolve live Ruff findings before relying on higher-level durable guarantees.",
            validation="Rerun Ruff and the Temporal hardgate after cleanup.",
            merge_gate="block-changed-files",
            autofix_allowed=False,
            notes=" | ".join(run_by_tool["ruff"].details[:2]),
        ))
        next_id += 1
    if run_by_tool.get("basedpyright") and run_by_tool["basedpyright"].status == "issues":
        findings.append(Finding(
            id=f"pta-{next_id:03d}",
            gate="dependency-contracts",
            severity="medium",
            confidence="high",
            current_state="fragile",
            target_state="sound",
            locus="locked basedpyright run",
            title="BasedPyright reported Python type contract issues in the durable surface",
            evidence_summary=run_by_tool["basedpyright"].summary,
            decision="harden",
            change_shape="Treat Python type contract failures as durability evidence, not as optional lint debt.",
            validation="Rerun BasedPyright and the Temporal hardgate after repair.",
            merge_gate="block-changed-files",
            autofix_allowed=False,
            notes=" | ".join(run_by_tool["basedpyright"].details[:2]),
        ))
        next_id += 1
    if run_by_tool.get("semgrep") and run_by_tool["semgrep"].status == "issues":
        findings.append(Finding(
            id=f"pta-{next_id:03d}",
            gate="workflow-determinism",
            severity="high",
            confidence="medium",
            current_state="unsafe",
            target_state="sound",
            locus="locked semgrep rule pack",
            title="Semgrep matched workflow or raw-agent hazard patterns",
            evidence_summary=run_by_tool["semgrep"].summary,
            decision="replace",
            change_shape="Resolve the Semgrep hazard hits instead of assuming the workflow path is still safe.",
            validation="Rerun the locked Semgrep rule pack and this hardgate after changes.",
            merge_gate="block-now",
            autofix_allowed=False,
            notes=" | ".join(run_by_tool["semgrep"].details[:3]),
        ))
    return findings[:8]


def infer_verdict(applicable: bool, gates: list[GateState]) -> str:
    if not applicable:
        return "not-applicable"
    states = {gate.gate: gate.state for gate in gates}
    if states["workflow-determinism"] == "broken" or states["durable-agent-path"] == "broken":
        return "workflow-time-bomb"
    if states["sandbox-discipline"] == "unsafe" or states["tool-contracts"] == "broken":
        return "workflow-time-bomb"
    if states["durable-agent-path"] == "fragile" and states["verification-harness"] in {"unsafe", "fragile"}:
        return "paper-guardrails"
    if any(gate.state in {"unsafe", "fragile", "unverified"} for gate in gates):
        return "partially-contained"
    return "durable-harness"


def render_human_report(summary: dict[str, object]) -> str:
    tool_runs = summary.get("tool_runs", [])
    verified_doc_entries = [
        entry for entry in summary.get("doc_verification", [])
        if isinstance(entry, dict) and entry.get("status") == "verified"
    ]
    if summary["overall_verdict"] == "not-applicable":
        return "\n".join([
            "# Pydantic AI + Temporal 审计报告",
            "",
            "## 一句话判决",
            "- **总体结论**：not-applicable",
            "- **一句狠话**：这个仓库没有同时暴露 Temporal 和 pydantic-ai 的 durable 面，硬判只会制造假问题。",
            "",
            "## 真实工具执行",
            *(f"- {item['tool']}: {item['status']} — {item['summary']}" for item in tool_runs),
            "",
            "## 仓库画像",
            f"- Workflow 面：{', '.join(summary['repo_profile']['workflow_surface']) or 'none'}",
            f"- Agent 面：{', '.join(summary['repo_profile']['agent_surface']) or 'none'}",
            f"- 已见门控：none",
            f"- 看不到但关键：none",
            "",
            "## 无法从本地仓库证明，但必须说清楚的事",
            "- 不适用不等于安全，只是说明这份专项审计没有命中目标面。",
            "",
        ])

    lines = [
        "# Pydantic AI + Temporal 审计报告",
        "",
        "## 一句话判决",
        f"- **总体结论**：{summary['overall_verdict']}",
        "- **一句狠话**：Workflow 里顺手写 I/O，不叫快，叫把重放模型写废。",
        f"- **live-doc 状态**：{'verified' if verified_doc_entries else 'blocked / missing'}",
        "",
        "## 这套仓库现在在教 AI 学什么坏习惯",
        "- 把 local green test 当成 durable execution 证据。",
        "- 把 raw Agent 和 TemporalAgent 混成一个东西。",
        "- 把有 workflow 文件当成 merge gate 已经上锁。",
        "",
        "## 仓库画像",
        f"- Workflow 面：{', '.join(summary['repo_profile']['workflow_surface']) or 'none'}",
        f"- Agent 面：{', '.join(summary['repo_profile']['agent_surface']) or 'none'}",
        f"- 已见门控：{', '.join(gate['gate'] for gate in summary['gate_states'] if gate['state'] in {'sound', 'hardened'}) or 'weak'}",
        f"- 看不到但关键：{'; '.join(summary.get('unverified', [])) or 'none'}",
        "",
        "## 真实工具执行",
        *(f"- {item['tool']}: {item['status']} — {item['summary']}" for item in tool_runs),
        "",
        "## 关键问题（已确认）",
        "",
    ]
    if not summary["findings"]:
        lines.append("- 当前 baseline 没抓到已确认问题，但这不等于 durable harness 已经成立。")
    else:
        for idx, finding in enumerate(summary["findings"][:4], start=1):
            lines.extend([
                f"### {idx}. {finding['title']}",
                f"- **Gate**：{finding['gate']}",
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
                "这套系统要靠重放历史来保证正确。只要主路径里混进了不稳定的外部行为，之前跑通一次也没有意义。",
                "",
                "---",
                "",
            ])
    lines.extend([
        "## 别再教错规则",
        *(f"- {item}" for item in summary.get("wrong_rules", [])),
        "",
        "## 无法从本地仓库证明，但必须说清楚的事",
        *(f"- {item}" for item in summary.get("unverified", [])),
        "",
        "## 行动顺序",
        "",
        "### 现在就做",
        "- 先把 workflow 主路和 durable-agent path 变成可证明的正确路径。",
        "- 再把 replay / time-skipping / fake-model harness 补齐。",
        "",
        "### 下一步",
        "- 把 README / AGENTS 里的 durable 规则写准，避免 agent 学错。",
        "- 把 local workflow 文件升级成真的 required checks。",
        "",
        "### 之后再做",
        "- 收紧 changed-files gate，减少未来回归。",
        "",
        "## 最后一句",
        "规则写在 README 不够，写进 replay、测试和合并门才算数。",
        "",
    ])
    return "\n".join(lines)


def render_agent_brief(summary: dict[str, object]) -> str:
    verified_doc_entries = [
        entry for entry in summary.get("doc_verification", [])
        if isinstance(entry, dict) and entry.get("status") == "verified"
    ]
    lines = [
        "# Pydantic AI + Temporal Hardgate — Agent Brief",
        "",
        "## Repo profile",
        f"- `repo_profile`: {summary['repo_profile']['shape']}",
        f"- `workflow_surface`: {', '.join(summary['repo_profile']['workflow_surface']) or 'none'}",
        f"- `agent_surface`: {', '.join(summary['repo_profile']['agent_surface']) or 'none'}",
        f"- `overall_verdict`: {summary['overall_verdict']}",
        f"- `live_doc_verification`: {'verified' if verified_doc_entries else 'blocked-or-missing'}",
        "",
        "## Tool runs",
        *(f"- {item['tool']}: {item['status']} ({item['summary']})" for item in summary.get('tool_runs', [])),
        "",
        "## Findings",
        "",
    ]
    if not summary["findings"]:
        lines.append("- No confirmed findings. Either the repo is not applicable, or the local baseline did not catch a hard failure.")
    else:
        for finding in summary["findings"]:
            lines.extend([
                f"### {finding['id']} — {finding['title']}",
                f"- `gate`: {finding['gate']}",
                f"- `severity`: {finding['severity']}",
                f"- `confidence`: {finding['confidence']}",
                f"- `current_state`: {finding['current_state']}",
                f"- `target_state`: {finding['target_state']}",
                f"- `locus`: {finding['locus']}",
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
    parser.add_argument("--doc-evidence-json")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc_verification = load_doc_evidence(args.doc_evidence_json)
    except Exception as exc:
        print(f"error: could not load doc evidence: {exc}", file=sys.stderr)
        return 2

    files = iter_files(repo)
    collected = collect_signals(repo, files)
    repo_profile = collected["repo_profile"]
    signals = collected["signals"]
    applicable = bool(collected["applicable"])
    gates = [build_gate_state(name, applicable, signals, repo_profile) for name in GATE_ORDER]
    tool_runs, _ = collect_tool_runs(repo, applicable)
    findings = build_findings(gates, signals, tool_runs) if applicable else []
    dependency_status = "ready"
    dependency_failures: list[dict[str, object]] = []
    overall_verdict = infer_verdict(applicable, gates)
    if applicable and not live_doc_ready(doc_verification):
        overall_verdict = "scan-blocked"
        dependency_status = "blocked"
        dependency_failures = [blocked_dependency_failure()]

    summary = {
        "repo_profile": repo_profile,
        "overall_verdict": overall_verdict,
        "doc_verification": doc_verification,
        "gate_states": [asdict(item) for item in gates],
        "findings": [asdict(item) for item in findings],
        "dependency_status": dependency_status,
        "bootstrap_actions": [],
        "dependency_failures": dependency_failures,
        "wrong_rules": [
            "Do not treat `asyncio.sleep()` as a universal workflow violation without looking at the actual Temporal usage.",
            "Do not confuse local CI files with remote merge enforcement.",
        ],
        "tool_runs": [item.to_dict() for item in tool_runs],
        "unverified": [
            "Local workflow files and CODEOWNERS do not prove remote required checks, rulesets, or code-owner enforcement."
        ] if applicable else [],
    }

    (out_dir / "pydantic-temporal-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "pydantic-temporal-human-report.md").write_text(
        render_human_report(summary) + "\n",
        encoding="utf-8",
    )
    (out_dir / "pydantic-temporal-agent-brief.md").write_text(
        render_agent_brief(summary),
        encoding="utf-8",
    )
    print(f"Wrote {out_dir / 'pydantic-temporal-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
