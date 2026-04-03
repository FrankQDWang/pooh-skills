#!/usr/bin/env python3
"""Pythonic DDD drift scan backed by locked Tach / Ruff / BasedPyright runs."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

RUNTIME_BIN_DIR = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN_DIR))

from standard_audit_utils import describe_surface_source, first_party_text_files  # noqa: E402
from standard_audit_utils import foreign_runtime_anchors, foreign_runtime_text_files  # noqa: E402
from standard_audit_utils import format_surface_note, surface_source  # noqa: E402
from tool_runner import ToolRun, run_locked_tool  # noqa: E402

FORBIDDEN_DOMAIN_MODULES = {
    "fastapi", "flask", "django", "sqlalchemy", "requests", "httpx", "aiohttp",
    "boto3", "botocore", "redis", "celery", "kombu", "aiokafka", "confluent_kafka",
    "grpc", "pika",
}
SOFT_DOMAIN_MODULES = {"pydantic", "marshmallow"}
FRAMEWORKISH_NAME_PARTS = {
    "adapter", "adapters", "infra", "infrastructure", "api", "routes", "router",
    "controller", "controllers", "persistence", "orm", "sql", "repository", "repositories",
}
ENTRYPOINT_NAMES = {"main.py", "app.py", "bootstrap.py", "container.py", "__main__.py"}


@dataclass
class Finding:
    id: str
    category: str
    severity: str
    confidence: str
    title: str
    path: str
    line: int
    evidence: list[str]
    recommendation: str
    merge_gate: str
    notes: str = ""


def iter_py_files(root: Path) -> Iterable[Path]:
    yield from (
        path
        for path in first_party_text_files(root, suffixes={".py"})
        if path.suffix == ".py"
    )


def path_parts_lower(path: Path) -> list[str]:
    return [p.lower() for p in path.parts]


def is_domain_file(rel: Path) -> bool:
    parts = path_parts_lower(rel)
    return "domain" in parts or "domains" in parts


def extract_context_name(rel: Path) -> str | None:
    parts = path_parts_lower(rel)
    for marker in ("contexts", "bounded_contexts"):
        if marker in parts:
            idx = parts.index(marker)
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return None


def read_ast(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_imports(tree: ast.AST) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "", node.lineno))
    return imports


def base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return ""


def is_notimplemented(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Raise):
        exc = stmt.exc
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
            return exc.func.id == "NotImplementedError"
        if isinstance(exc, ast.Name):
            return exc.id == "NotImplementedError"
    return False


def body_is_interface_shell(body: list[ast.stmt]) -> bool:
    meaningful = [s for s in body if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)]
    if not meaningful:
        return True
    for stmt in meaningful:
        if isinstance(stmt, ast.Pass):
            continue
        if is_notimplemented(stmt):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
            continue
        return False
    return True


def stmt_is_thin_delegation(stmt: ast.stmt) -> bool:
    call = None
    if isinstance(stmt, ast.Return):
        call = stmt.value
    elif isinstance(stmt, ast.Expr):
        call = stmt.value
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
        return isinstance(func.value.value, ast.Name) and func.value.value.id == "self"
    return False


def class_public_methods(node: ast.ClassDef) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        item for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_")
    ]


def class_is_thin_wrapper(node: ast.ClassDef) -> bool:
    methods = class_public_methods(node)
    if not methods or len(methods) > 3:
        return False
    delegated = 0
    for method in methods:
        body = [s for s in method.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
        if len(body) == 1 and stmt_is_thin_delegation(body[0]):
            delegated += 1
    return delegated == len(methods)


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    counter = Counter(f.severity for f in findings)
    return {k: int(counter.get(k, 0)) for k in ("critical", "high", "medium", "low")}


def build_tool_runs(repo: Path, python_files: int, files: list[Path]) -> tuple[list[ToolRun], dict[str, Any]]:
    if python_files == 0 or not files:
        return [], {}

    tool_runs: list[ToolRun] = []
    payloads: dict[str, Any] = {}
    target_args = [str(path.relative_to(repo)) for path in files]
    exclude_args: list[str] = []
    excluded = foreign_runtime_anchors(repo, suffixes={".py"})
    if excluded:
        exclude_args = ["-e", ",".join(excluded)]
    for tool, args in (
        ("tach", ["check", "--output", "json", *exclude_args]),
        ("ruff", ["check", "--output-format", "json", *target_args]),
        ("basedpyright", ["--outputjson", "-p", str(repo), *target_args]),
    ):
        run, payload = run_locked_tool(tool, args, repo, allow_exit_codes={0, 1})
        tool_runs.append(run)
        payloads[tool] = payload
    return tool_runs, payloads


def add_tool_findings(findings: list[Finding], tool_runs: list[ToolRun], payloads: dict[str, Any]) -> None:
    next_id = len(findings) + 1
    run_by_tool = {item.tool: item for item in tool_runs}

    tach_run = run_by_tool.get("tach")
    if tach_run and tach_run.status in {"issues", "failed"}:
        findings.append(Finding(
            id=f"pdd-{next_id:03d}",
            category="boundary-tool-signal",
            severity="high" if tach_run.status == "issues" else "medium",
            confidence="medium",
            title="Tach reported Python boundary pressure or could not validate the boundary model cleanly",
            path=".",
            line=1,
            evidence=tach_run.details[:3] or [tach_run.summary],
            recommendation="Treat Python boundary drift as a real signal now that Tach is in the loop; repair config or boundary leaks before adding more ceremony.",
            merge_gate="block-changed-files",
        ))
        next_id += 1

    ruff_run = run_by_tool.get("ruff")
    if ruff_run and ruff_run.status == "issues":
        findings.append(Finding(
            id=f"pdd-{next_id:03d}",
            category="lint-drift",
            severity="medium",
            confidence="high",
            title="Ruff reported Python hygiene issues inside the audited surface",
            path=".",
            line=1,
            evidence=ruff_run.details[:3] or [ruff_run.summary],
            recommendation="Fix the live Ruff issues before layering more DDD ceremony on top of already noisy Python code.",
            merge_gate="warn-only",
        ))
        next_id += 1

    based_run = run_by_tool.get("basedpyright")
    diagnostics = payloads.get("basedpyright", {}).get("generalDiagnostics", []) if isinstance(payloads.get("basedpyright"), dict) else []
    if based_run and based_run.status == "issues":
        findings.append(Finding(
            id=f"pdd-{next_id:03d}",
            category="type-contract-drift",
            severity="medium",
            confidence="high",
            title="BasedPyright reported Python type contract issues in the audited surface",
            path=".",
            line=1,
            evidence=based_run.details[:3] or [based_run.summary],
            recommendation="Use the type errors as first-class architecture feedback instead of compensating with more nominal abstraction layers.",
            merge_gate="warn-only",
            notes=f"generalDiagnostics={len(diagnostics)}",
        ))


def infer_verdict(findings: list[Finding], python_files: int, tool_runs: list[ToolRun]) -> tuple[str, str]:
    if python_files == 0:
        return "not-applicable", "No Python files were detected."
    if any(item.status == "failed" for item in tool_runs):
        return "watch", "The locked Python toolchain did not complete cleanly, so boundary drift evidence is incomplete."
    sev = severity_counts(findings)
    cats = Counter(f.category for f in findings)
    if cats["domain-boundary-leak"] or cats["cross-context-model-bleed"] or cats["boundary-tool-signal"]:
        return "drifting", "The repo shows real boundary drift, not just stylistic preferences."
    if sev["medium"] >= 3 or cats["thin-wrapper"] >= 2 or cats["abc-overuse"] >= 2:
        return "ceremonial", "The repo is accumulating Python-unfriendly abstraction ceremony faster than it is preserving useful boundaries."
    if findings:
        return "contained", "The repo shows some architecture drift, but the damage still looks locally repairable."
    return "disciplined", "No strong Pythonic / DDD drift signals were found by the locked scan."


def render_human_report(summary: dict[str, Any]) -> str:
    findings = summary["findings"]
    tool_runs = summary.get("tool_runs", [])
    lines = [
        "# Pythonic DDD Drift Audit Report",
        "",
        "## 1. Executive summary",
        f"- overall_verdict: `{summary.get('overall_verdict')}`",
        f"- summary_line: {summary.get('summary_line')}",
        f"- dependency_status: `{summary.get('dependency_status')}`",
        f"- surface_source: `{summary.get('surface_source_note', '')}`",
        f"- scan_surface: `{summary.get('surface_note', '')}`",
        "",
        "## 2. Locked tool runs",
        "",
    ]
    if not tool_runs:
        lines.append("- No locked Python tool runs were recorded for this repository surface.")
    else:
        for item in tool_runs:
            lines.extend([
                f"### {item['tool']}",
                f"- status: `{item['status']}`",
                f"- summary: {item['summary']}",
                *(f"- detail: {detail}" for detail in item.get("details", [])[:3]),
                "",
            ])

    lines.extend(["## 3. Highest-signal drift findings", ""])
    if not findings:
        lines.append("- No Pythonic / DDD drift findings were detected.")
    else:
        for finding in findings[:8]:
            lines.extend([
                f"### {finding['title']}",
                f"- category: `{finding['category']}`",
                f"- severity: `{finding['severity']}`",
                f"- confidence: `{finding['confidence']}`",
                f"- locus: {finding['path']}:{finding['line']}",
                *(f"- evidence: {item}" for item in finding.get('evidence', [])[:3]),
                f"- recommendation: {finding['recommendation']}",
                "",
            ])

    lines.extend([
        "## 4. Handoff guidance",
        "- Treat these findings as boundary and modeling evidence, not as permission for automatic refactors.",
        "- Fix boundary leaks and ceremonial layers manually, then rerun the locked audit stack.",
        "- Prefer simpler Python structures once the evidence no longer supports the extra abstraction.",
        "",
    ])
    return "\n".join(lines)


def render_agent_brief(summary: dict[str, Any]) -> str:
    findings = summary["findings"]
    lines = [
        "# Pythonic DDD Drift Handoff Brief",
        "",
        "## Context",
        f"- overall_verdict: `{summary.get('overall_verdict')}`",
        f"- dependency_status: `{summary.get('dependency_status')}`",
        f"- summary_line: {summary.get('summary_line')}",
        f"- surface_source: `{summary.get('surface_source_note', '')}`",
        f"- scan_surface: `{summary.get('surface_note', '')}`",
        "",
        "## Ordered actions",
        "1. Remove boundary leaks and framework imports from domain surfaces first.",
        "2. Collapse abstraction shells that add naming but not policy.",
        "3. Re-run the locked Python audit stack after manual restructuring work.",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("- No Pythonic / DDD drift findings were detected by the locked stack.")
    else:
        for finding in findings[:8]:
            lines.extend([
                f"### {finding['id']} {finding['title']}",
                f"- category: {finding['category']}",
                f"- severity: {finding['severity']}",
                f"- confidence: {finding['confidence']}",
                f"- evidence_summary: {('; '.join(finding.get('evidence', [])[:2])) or 'none'}",
                f"- validation: {finding['recommendation']}",
                "",
            ])
    return "\n".join(lines) + "\n"


def scan(repo: Path) -> dict[str, Any]:
    findings: list[Finding] = []
    seen: set[tuple] = set()
    python_files = 0
    domain_files = 0
    cqrs_name_count = 0
    read_model_clues = 0
    entrypoint_clues = 0
    python_paths = list(iter_py_files(repo))
    surface_kind, _ = surface_source(repo)
    surface_note = format_surface_note(
        first_party_count=len(python_paths),
        foreign_runtime_excluded=sum(
            1
            for path in foreign_runtime_text_files(repo, suffixes={".py"})
            if path.suffix == ".py"
        ),
        source=surface_kind,
    )
    surface_source_note = describe_surface_source(repo)

    def add(f: Finding) -> None:
        key = (f.category, f.path, f.line, f.title)
        if key not in seen:
            findings.append(f)
            seen.add(key)

    for path in python_paths:
        python_files += 1
        rel = path.relative_to(repo)
        if is_domain_file(rel):
            domain_files += 1
        if path.name in ENTRYPOINT_NAMES:
            entrypoint_clues += 1

        tree = read_ast(path)
        if tree is None:
            continue

        imports = get_imports(tree)
        rel_str = str(rel)
        context = extract_context_name(rel)

        if is_domain_file(rel):
            for module, lineno in imports:
                top = module.split(".")[0] if module else ""
                module_parts = set(module.lower().split("."))
                if top in FORBIDDEN_DOMAIN_MODULES or module_parts & FRAMEWORKISH_NAME_PARTS:
                    add(Finding(
                        id=f"pdd-{len(findings)+1:03d}",
                        category="domain-boundary-leak",
                        severity="high",
                        confidence="high",
                        title="Domain code imports framework / infrastructure detail directly",
                        path=rel_str,
                        line=lineno,
                        evidence=[module],
                        recommendation="Move framework or infrastructure dependency behind an adapter / port and keep domain code dependency-light.",
                        merge_gate="block-now",
                    ))
                elif top in SOFT_DOMAIN_MODULES:
                    add(Finding(
                        id=f"pdd-{len(findings)+1:03d}",
                        category="framework-coupling-signal",
                        severity="medium",
                        confidence="medium",
                        title="Domain code imports a boundary-shaping library directly",
                        path=rel_str,
                        line=lineno,
                        evidence=[module],
                        recommendation="Decide whether this dependency is a real modeling requirement or should stay at the boundary edge.",
                        merge_gate="warn-only",
                    ))

        if context and is_domain_file(rel):
            for module, lineno in imports:
                lower_mod = module.lower()
                if ".domain" in lower_mod and f".{context}." not in lower_mod:
                    for marker in ("contexts.", "bounded_contexts."):
                        if marker in lower_mod:
                            add(Finding(
                                id=f"pdd-{len(findings)+1:03d}",
                                category="cross-context-model-bleed",
                                severity="high",
                                confidence="high",
                                title="One bounded context imports another context's domain model directly",
                                path=rel_str,
                                line=lineno,
                                evidence=[module],
                                recommendation="Replace cross-context domain imports with an event, boundary DTO, public application service, or translation layer.",
                                merge_gate="block-now",
                            ))
                            break

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            name = node.name
            if name.endswith(("Command", "Query", "Handler")):
                cqrs_name_count += 1
            if name.endswith(("Projection", "ReadModel", "ViewModel")):
                read_model_clues += 1

            bases = {base_name(b) for b in node.bases}
            methods = class_public_methods(node)

            if "ABC" in bases and all(
                not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) or body_is_interface_shell(item.body)
                for item in node.body
            ):
                add(Finding(
                    id=f"pdd-{len(findings)+1:03d}",
                    category="abc-overuse",
                    severity="medium",
                    confidence="high",
                    title="Abstract base looks like a nominal interface shell",
                    path=rel_str,
                    line=node.lineno,
                    evidence=[name],
                    recommendation="Replace nominal interface ceremony with Protocol or a lighter structural dependency shape unless inheritance carries real meaning.",
                    merge_gate="warn-only",
                ))

            if class_is_thin_wrapper(node):
                add(Finding(
                    id=f"pdd-{len(findings)+1:03d}",
                    category="thin-wrapper",
                    severity="medium",
                    confidence="high",
                    title="Class mainly forwards calls and adds almost no policy",
                    path=rel_str,
                    line=node.lineno,
                    evidence=[name],
                    recommendation="Collapse the wrapper into the caller or keep only the policy-bearing parts.",
                    merge_gate="warn-only",
                ))

            if is_domain_file(rel) and methods:
                nontrivial = 0
                for method in methods:
                    body = [s for s in method.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
                    if not body:
                        continue
                    if len(body) == 1 and isinstance(body[0], (ast.Return, ast.Assign, ast.AnnAssign)):
                        continue
                    if len(body) == 1 and stmt_is_thin_delegation(body[0]):
                        continue
                    nontrivial += 1
                if nontrivial == 0:
                    add(Finding(
                        id=f"pdd-{len(findings)+1:03d}",
                        category="anemic-domain-model-signal",
                        severity="medium",
                        confidence="low",
                        title="Domain class appears mostly data-shaped with little visible behavior",
                        path=rel_str,
                        line=node.lineno,
                        evidence=[name],
                        recommendation="Move invariant-bearing logic back toward the domain model where appropriate.",
                        merge_gate="warn-only",
                    ))

    if cqrs_name_count >= 6 and read_model_clues == 0:
        add(Finding(
            id=f"pdd-{len(findings)+1:03d}",
            category="cqrs-ceremony-signal",
            severity="medium",
            confidence="low",
            title="CQRS naming is common but read-model payoff is not obvious",
            path=".",
            line=1,
            evidence=[f"command/query/handler class count: {cqrs_name_count}", f"read-model clue count: {read_model_clues}"],
            recommendation="Keep CQRS only where the read/write split earns its complexity with clear read-side needs.",
            merge_gate="warn-only",
        ))

    if python_files > 0 and entrypoint_clues == 0:
        add(Finding(
            id=f"pdd-{len(findings)+1:03d}",
            category="composition-root-gap",
            severity="low",
            confidence="low",
            title="No obvious composition-root / bootstrap file was detected",
            path=".",
            line=1,
            evidence=["No main.py / app.py / bootstrap.py / container.py clue found"],
            recommendation="Check whether dependency wiring is scattered across the codebase instead of being concentrated at process entrypoints.",
            merge_gate="warn-only",
        ))

    tool_runs, payloads = build_tool_runs(repo, python_files, python_paths)
    add_tool_findings(findings, tool_runs, payloads)
    verdict, summary_line = infer_verdict(findings, python_files, tool_runs)
    return {
        "schema_version": "1.0",
        "skill": "pythonic-ddd-drift-audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo),
        "overall_verdict": verdict,
        "summary_line": summary_line,
        "surface_source_note": surface_source_note,
        "surface_note": surface_note,
        "tool_runs": [item.to_dict() for item in tool_runs],
        "coverage": {
            "files_scanned": python_files,
            "python_files": python_files,
            "domain_files": domain_files,
        },
        "severity_counts": severity_counts(findings),
        "scan_blockers": [item.summary for item in tool_runs if item.status == "failed"],
        "signals": {
            "cqrs_name_count": cqrs_name_count,
            "read_model_clues": read_model_clues,
            "entrypoint_clues": entrypoint_clues,
        },
        "findings": [asdict(f) for f in findings],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--agent-brief-out", default=None)
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if not repo.exists():
        print(f"Repository does not exist: {repo}", file=sys.stderr)
        return 2

    data = scan(repo)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_path = Path(args.report_out).resolve() if args.report_out else out.with_name("pythonic-ddd-drift-report.md")
    brief_path = Path(args.agent_brief_out).resolve() if args.agent_brief_out else out.with_name("pythonic-ddd-drift-agent-brief.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_human_report(data) + "\n", encoding="utf-8")
    brief_path.write_text(render_agent_brief(data), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
