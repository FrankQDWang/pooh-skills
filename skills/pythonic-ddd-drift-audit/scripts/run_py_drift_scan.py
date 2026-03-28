#!/usr/bin/env python3
"""Heuristic Pythonic / DDD drift scanner.

Focuses on:
- domain-boundary leaks
- cross-context model bleed
- abstract-base ceremony
- thin wrappers / pass-through classes
- CQRS ceremony signals
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "dist", "build",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".repo-harness",
}

FORBIDDEN_DOMAIN_MODULES = {
    "fastapi", "flask", "django", "sqlalchemy", "requests", "httpx", "aiohttp",
    "boto3", "botocore", "redis", "celery", "kombu", "aiokafka", "confluent_kafka",
    "grpc", "pika",
}

SOFT_DOMAIN_MODULES = {
    "pydantic", "marshmallow",
}

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
    evidence: List[str]
    recommendation: str
    merge_gate: str
    notes: str = ""


def iter_py_files(root: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d != "skills"]
        for name in files:
            if name.endswith(".py"):
                yield Path(current_root) / name


def path_parts_lower(path: Path) -> list[str]:
    return [p.lower() for p in path.parts]


def is_domain_file(rel: Path) -> bool:
    parts = path_parts_lower(rel)
    return "domain" in parts or "domains" in parts


def is_application_file(rel: Path) -> bool:
    parts = path_parts_lower(rel)
    return "application" in parts or "use_cases" in parts or "services" in parts


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
            module = node.module or ""
            imports.append((module, node.lineno))
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
    methods = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_"):
            methods.append(item)
    return methods


def class_is_thin_wrapper(node: ast.ClassDef) -> bool:
    methods = class_public_methods(node)
    if not methods or len(methods) > 3:
        return False
    delegated = 0
    for method in methods:
        body = [s for s in method.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
        if not body:
            return False
        if len(body) == 1 and stmt_is_thin_delegation(body[0]):
            delegated += 1
    return delegated == len(methods)


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    counter = Counter(f.severity for f in findings)
    return {k: int(counter.get(k, 0)) for k in ("critical", "high", "medium", "low")}


def infer_verdict(findings: list[Finding], python_files: int) -> tuple[str, str]:
    if python_files == 0:
        return "not-applicable", "No Python files were detected."
    sev = severity_counts(findings)
    cats = Counter(f.category for f in findings)
    if cats["domain-boundary-leak"] or cats["cross-context-model-bleed"]:
        return "drifting", "The repo shows strong evidence that architecture boundaries are leaking in code, not just in taste."
    if sev["medium"] >= 3 or cats["thin-wrapper"] >= 2 or cats["abc-overuse"] >= 2:
        return "ceremonial", "The repo is accumulating Python-unfriendly abstraction ceremony faster than it is preserving useful boundaries."
    if findings:
        return "contained", "The repo shows some architecture drift, but the damage still looks locally repairable."
    return "disciplined", "No strong Pythonic / DDD drift signals were found by the deterministic scan."


def scan(repo: Path) -> dict:
    findings: list[Finding] = []
    seen: set[tuple] = set()
    python_files = 0
    domain_files = 0
    cqrs_name_count = 0
    read_model_clues = 0
    entrypoint_clues = 0

    def add(f: Finding) -> None:
        key = (f.category, f.path, f.line, f.title)
        if key not in seen:
            findings.append(f)
            seen.add(key)

    for path in iter_py_files(repo):
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
        rel_parts = path_parts_lower(rel)

        # Domain-boundary leaks
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
                        recommendation="Decide whether this dependency is a real modeling requirement or should stay at the boundary / adapter edge.",
                        merge_gate="warn-only",
                    ))

        # Cross-context model bleed
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
            if isinstance(node, ast.ClassDef):
                name = node.name
                if name.endswith(("Command", "Query", "Handler")):
                    cqrs_name_count += 1
                if name.endswith(("Projection", "ReadModel", "ViewModel")):
                    read_model_clues += 1

                bases = {base_name(b) for b in node.bases}
                methods = class_public_methods(node)

                if "ABC" in bases or "Protocol" in bases or "Base" in name:
                    shell_like = True
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if not body_is_interface_shell(item.body):
                                shell_like = False
                                break
                    if "ABC" in bases and shell_like:
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
                        add(Finding(
                            id=f"pdd-{len(findings)+1:03d}",
                            category="protocol-opportunity",
                            severity="low",
                            confidence="medium",
                            title="Interface shell is a candidate for structural typing",
                            path=rel_str,
                            line=node.lineno,
                            evidence=[name],
                            recommendation="Prefer Protocol or direct callable injection when the dependency is purely behavioral and structural.",
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

                if name.endswith(("Service", "Manager", "Factory")) and class_is_thin_wrapper(node):
                    add(Finding(
                        id=f"pdd-{len(findings)+1:03d}",
                        category="abstraction-bloat",
                        severity="medium",
                        confidence="medium",
                        title="Service / manager / factory layer looks ceremonial rather than policy-bearing",
                        path=rel_str,
                        line=node.lineno,
                        evidence=[name],
                        recommendation="Delete or flatten layers that only rename collaborators instead of enforcing a boundary or policy.",
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
                            recommendation="Check whether domain behavior has leaked into services / handlers and move invariant-bearing logic back toward the model where appropriate.",
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

    verdict, summary_line = infer_verdict(findings, python_files)
    return {
        "schema_version": "1.0",
        "skill": "pythonic-ddd-drift-audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo),
        "overall_verdict": verdict,
        "summary_line": summary_line,
        "coverage": {
            "files_scanned": python_files,
            "python_files": python_files,
            "domain_files": domain_files,
        },
        "severity_counts": severity_counts(findings),
        "scan_blockers": [],
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
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if not repo.exists():
        print(f"Repository does not exist: {repo}", file=sys.stderr)
        return 2

    data = scan(repo)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
