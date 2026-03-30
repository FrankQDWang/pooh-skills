#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".repo-harness",
    ".pooh-runtime",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "out",
    "target",
    ".next",
    ".turbo",
}
SUPPORTED_SUFFIXES = {".py": "python", ".ts": "typescript", ".tsx": "typescript"}
GENERATED_MARKERS = {
    "generated",
    "vendor",
    "vendors",
    "__generated__",
    ".generated",
    "gen",
}
MIGRATION_MARKERS = {
    "migrations",
    "alembic",
    "versions",
}
TEST_PATH_MARKERS = ("/tests/", "/test/", "/__tests__/", "/spec/")
TS_IMPORT_RE = re.compile(
    r"""(?mx)
    ^\s*import\s+.*?\s+from\s+["']([^"']+)["']
    |
    ^\s*export\s+.*?\s+from\s+["']([^"']+)["']
    |
    require\(\s*["']([^"']+)["']\s*\)
    """
)
TS_EXPORT_DECL_RE = re.compile(
    r"""(?mx)
    ^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|type|interface|enum)\s+([A-Za-z_$][\w$]*)
    """
)
TS_NAMED_EXPORT_RE = re.compile(r"""(?ms)export\s*\{\s*([^}]+)\s*\}""")
TS_FUNCTION_STARTERS = [
    re.compile(r'^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\).*?\{'),
    re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>\s*\{'),
    re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?([A-Za-z_$][\w$]*)\s*=>\s*\{'),
    re.compile(r'^\s*(?:public\s+|private\s+|protected\s+|static\s+|readonly\s+|async\s+)*(constructor|[A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*\{'),
]
CONTROL_KEYWORDS = {"if", "for", "while", "switch", "catch", "else", "do", "try"}
RESPONSIBILITY_IMPORT_PREFIXES = {
    "http": (
        "fastapi",
        "flask",
        "starlette",
        "django.http",
        "aiohttp",
        "httpx",
        "requests",
        "express",
        "next/server",
        "hono",
        "koa",
    ),
    "db": (
        "sqlalchemy",
        "django.db",
        "psycopg",
        "asyncpg",
        "peewee",
        "pymongo",
        "motor",
        "alembic",
        "typeorm",
        "prisma",
        "sequelize",
        "mongoose",
        "drizzle",
        "knex",
    ),
    "schema": (
        "pydantic",
        "marshmallow",
        "dataclasses_json",
        "zod",
        "yup",
        "io-ts",
        "valibot",
    ),
    "worker": (
        "celery",
        "dramatiq",
        "rq",
        "arq",
        "bullmq",
        "bull",
    ),
    "cli": (
        "click",
        "typer",
        "argparse",
        "commander",
        "yargs",
    ),
    "ui": (
        "react",
        "react-dom",
        "preact",
        "vue",
        "solid-js",
        "svelte",
        "next/link",
        "next/navigation",
        "next/image",
        "next/router",
    ),
}
RESPONSIBILITY_PATH_MARKERS = {
    "http": {"api", "apis", "route", "routes", "router", "routers", "endpoint", "endpoints", "controller", "controllers"},
    "db": {"db", "database", "databases", "model", "models", "repository", "repositories", "orm", "query", "queries"},
    "schema": {"schema", "schemas", "serializer", "serializers", "dto", "dtos", "type", "types"},
    "worker": {"worker", "workers", "job", "jobs", "task", "tasks", "consumer", "consumers", "queue", "queues", "webhook", "webhooks", "cron"},
    "cli": {"cli", "cmd", "command", "commands", "bin"},
    "ui": {".tsx", "ui", "view", "views", "page", "pages", "screen", "screens", "layout", "layouts", "component", "components", "hook", "hooks"},
}
THRESHOLDS = {
    "file_warn_nloc": 500,
    "file_block_nloc": 900,
    "file_critical_nloc": 1800,
    "function_warn_nloc": 80,
    "function_block_nloc": 120,
    "function_critical_nloc": 200,
    "complexity_warn": 15,
    "complexity_block": 25,
    "complexity_critical": 40,
    "fanout_warn": 12,
    "fanout_block": 18,
    "fanout_critical": 25,
    "export_warn": 15,
    "export_block": 25,
    "export_critical": 40,
    "duplicate_warn": 3,
    "duplicate_block": 6,
}
SUMMARY_FILENAME = "module-shape-hardgate-summary.json"
REPORT_FILENAME = "module-shape-hardgate-report.md"
BRIEF_FILENAME = "module-shape-hardgate-agent-brief.md"


@dataclass
class FunctionMetric:
    name: str
    line: int
    end_line: int
    nloc: int
    complexity: int
    params: int


@dataclass
class FileMetrics:
    path: str
    language: str
    total_lines: int
    code_lines: int
    imports: list[str] = field(default_factory=list)
    internal_imports: list[str] = field(default_factory=list)
    exports_count: int = 0
    functions: list[FunctionMetric] = field(default_factory=list)
    responsibility_tags: list[str] = field(default_factory=list)
    duplicate_windows: int = 0
    duplicate_partners: int = 0
    generated_like: bool = False
    migration_like: bool = False
    barrel_like: bool = False
    test_like: bool = False
    scan_error: Optional[str] = None

    @property
    def fan_out(self) -> int:
        return len(set(self.imports))

    @property
    def max_function_nloc(self) -> int:
        return max((f.nloc for f in self.functions), default=0)

    @property
    def max_function_complexity(self) -> int:
        return max((f.complexity for f in self.functions), default=0)


class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.score = 1

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.Try, ast.IfExp, ast.Match)):
            self.score += 1
        elif isinstance(node, ast.BoolOp):
            self.score += max(1, len(node.values) - 1)
        elif isinstance(node, ast.comprehension):
            self.score += 1
        super().generic_visit(node)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_excluded_path(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDED_DIRS:
            return True
    return False


def iter_source_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded_path(path.relative_to(repo_root)):
            continue
        if path.suffix not in SUPPORTED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def strip_ts_comments(line: str, in_block: bool) -> tuple[str, bool]:
    i = 0
    out = []
    while i < len(line):
        if in_block:
            end = line.find("*/", i)
            if end == -1:
                return "", True
            i = end + 2
            in_block = False
            continue
        if line.startswith("/*", i):
            in_block = True
            i += 2
            continue
        if line.startswith("//", i):
            break
        out.append(line[i])
        i += 1
    return "".join(out), in_block


def code_lines(text: str, language: str) -> int:
    count = 0
    in_block = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if language == "python":
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            count += 1
        else:
            stripped, in_block = strip_ts_comments(line, in_block)
            stripped = stripped.strip()
            if not stripped:
                continue
            count += 1
    return count


def normalized_code_lines(text: str, language: str) -> list[str]:
    lines: list[str] = []
    in_block = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if language == "python":
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            stripped = re.sub(r"\s+", "", stripped)
            if stripped:
                lines.append(stripped)
        else:
            stripped, in_block = strip_ts_comments(line, in_block)
            stripped = stripped.strip()
            if not stripped:
                continue
            stripped = re.sub(r"\s+", "", stripped)
            if stripped:
                lines.append(stripped)
    return lines


def is_test_file(rel_path: str) -> bool:
    lowered = "/" + rel_path.replace("\\", "/").lower()
    if any(marker in lowered for marker in TEST_PATH_MARKERS):
        return True
    name = lowered.rsplit("/", 1)[-1]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".spec.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".spec.tsx")
    )


def classify_special_path(rel_path: str) -> tuple[bool, bool]:
    parts = [p.lower() for p in Path(rel_path).parts]
    generated_like = any(part in GENERATED_MARKERS for part in parts)
    migration_like = any(part in MIGRATION_MARKERS for part in parts)
    return generated_like, migration_like


def candidate_python_packages(files: Sequence[Path], repo_root: Path) -> set[str]:
    candidates: set[str] = set()
    for path in files:
        rel = path.relative_to(repo_root)
        parts = rel.parts
        if not parts:
            continue
        first = parts[0]
        if first in {"src", "app", "apps", "services", "packages"} and len(parts) >= 2:
            candidates.add(parts[1])
        if first not in {"scripts", "tests"}:
            candidates.add(first.split(".")[0])
    return {c for c in candidates if c and re.match(r"^[A-Za-z_]\w*$", c)}


def clean_module_name(module: str) -> str:
    return module.lstrip(".").split(".")[0]


def parse_python_file(path: Path, rel_path: str, package_candidates: set[str]) -> FileMetrics:
    text = path.read_text(encoding="utf-8", errors="ignore")
    total_lines = len(text.splitlines())
    metrics = FileMetrics(
        path=rel_path,
        language="python",
        total_lines=total_lines,
        code_lines=code_lines(text, "python"),
        test_like=is_test_file(rel_path),
    )
    generated_like, migration_like = classify_special_path(rel_path)
    metrics.generated_like = generated_like
    metrics.migration_like = migration_like
    metrics.barrel_like = path.name == "__init__.py"
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        metrics.scan_error = f"python parse error: {exc.msg} (line {exc.lineno})"
        return metrics

    metrics.imports = []
    metrics.internal_imports = []
    public_symbols: list[str] = []
    explicit_all: Optional[list[str]] = None

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                if node.module:
                    modules.append(node.module)
                elif node.level:
                    modules.append("." * node.level)
            metrics.imports.extend(modules)
            for mod in modules:
                clean = clean_module_name(mod)
                if mod.startswith(".") or clean in package_candidates:
                    metrics.internal_imports.append(mod)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                public_symbols.append(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                public_symbols.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "__all__":
                        explicit_all = extract_python___all__(node.value)
                    elif not target.id.startswith("_"):
                        public_symbols.append(target.id)

    if explicit_all is not None:
        metrics.exports_count = len(explicit_all)
    else:
        metrics.exports_count = len(set(public_symbols))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            segment = "\n".join(text.splitlines()[start - 1 : end])
            visitor = ComplexityVisitor()
            visitor.visit(node)
            params = len(getattr(node.args, "args", [])) + len(getattr(node.args, "kwonlyargs", []))
            if getattr(node.args, "vararg", None):
                params += 1
            if getattr(node.args, "kwarg", None):
                params += 1
            metrics.functions.append(
                FunctionMetric(
                    name=node.name,
                    line=start,
                    end_line=end,
                    nloc=code_lines(segment, "python"),
                    complexity=visitor.score,
                    params=params,
                )
            )

    metrics.responsibility_tags = detect_responsibility_tags(metrics.imports, rel_path)
    return metrics


def extract_python___all__(value: ast.AST) -> Optional[list[str]]:
    if isinstance(value, (ast.List, ast.Tuple)):
        out: list[str] = []
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
        return out
    return None


def strip_strings_for_brace_count(line: str) -> str:
    line = re.sub(r'".*?(?<!\\)"', '""', line)
    line = re.sub(r"'.*?(?<!\\)'", "''", line)
    line = re.sub(r"`.*?(?<!\\)`", "``", line)
    return line


def count_params(signature: str) -> int:
    signature = signature.strip()
    if not signature:
        return 0
    parts = [p for p in signature.split(",") if p.strip()]
    return len(parts)


def extract_ts_functions(text: str) -> list[FunctionMetric]:
    lines = text.splitlines()
    out: list[FunctionMetric] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        matched = None
        for regex in TS_FUNCTION_STARTERS:
            m = regex.match(line)
            if m:
                matched = m
                break
        if not matched:
            i += 1
            continue

        name = matched.group(1)
        if name in CONTROL_KEYWORDS:
            i += 1
            continue

        params_raw = matched.group(2) if matched.lastindex and matched.lastindex >= 2 else ""
        start_line = i + 1
        brace_balance = 0
        end_line = start_line
        found_open = False
        j = i
        while j < len(lines):
            current = strip_strings_for_brace_count(lines[j])
            current, _ = strip_ts_comments(current, False)
            brace_balance += current.count("{")
            brace_balance -= current.count("}")
            if "{" in current:
                found_open = True
            if found_open and brace_balance <= 0:
                end_line = j + 1
                break
            j += 1
        segment = "\n".join(lines[start_line - 1 : end_line])
        nloc = code_lines(segment, "typescript")
        complexity = estimate_ts_complexity(segment)
        out.append(
            FunctionMetric(
                name=name,
                line=start_line,
                end_line=end_line,
                nloc=nloc,
                complexity=complexity,
                params=count_params(params_raw),
            )
        )
        i = max(j + 1, i + 1)
    return out


def estimate_ts_complexity(text: str) -> int:
    score = 1
    patterns = [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"\bcatch\b", r"\?\s*[^:]", r"&&", r"\|\|"]
    for pattern in patterns:
        score += len(re.findall(pattern, text))
    return score


def parse_typescript_file(path: Path, rel_path: str) -> FileMetrics:
    text = path.read_text(encoding="utf-8", errors="ignore")
    total_lines = len(text.splitlines())
    metrics = FileMetrics(
        path=rel_path,
        language="typescript",
        total_lines=total_lines,
        code_lines=code_lines(text, "typescript"),
        test_like=is_test_file(rel_path),
    )
    generated_like, migration_like = classify_special_path(rel_path)
    metrics.generated_like = generated_like
    metrics.migration_like = migration_like
    metrics.barrel_like = path.name in {"index.ts", "index.tsx"}

    imports: list[str] = []
    for match in TS_IMPORT_RE.finditer(text):
        for idx in range(1, 4):
            group = match.group(idx)
            if group:
                imports.append(group)
    metrics.imports = imports
    metrics.internal_imports = [x for x in imports if x.startswith(".") or x.startswith("@/") or x.startswith("src/")]

    export_count = len(TS_EXPORT_DECL_RE.findall(text))
    for match in TS_NAMED_EXPORT_RE.finditer(text):
        names = [n.strip() for n in match.group(1).split(",") if n.strip()]
        export_count += len(names)
    metrics.exports_count = export_count

    metrics.functions = extract_ts_functions(text)
    metrics.responsibility_tags = detect_responsibility_tags(metrics.imports, rel_path)
    return metrics


def import_matches_prefix(import_path: str, prefixes: Sequence[str]) -> bool:
    lowered = import_path.lower()
    return any(
        lowered == prefix
        or lowered.startswith(f"{prefix}.")
        or lowered.startswith(f"{prefix}/")
        for prefix in prefixes
    )


def path_markers(rel_path: str) -> set[str]:
    path = Path(rel_path)
    markers = {part.lower() for part in path.parts}
    markers.add(path.stem.lower())
    markers.add(path.suffix.lower())
    return markers


def detect_responsibility_tags(imports: Sequence[str], rel_path: str) -> list[str]:
    markers = path_markers(rel_path)
    tags = []
    for tag, prefixes in RESPONSIBILITY_IMPORT_PREFIXES.items():
        if any(import_matches_prefix(import_path, prefixes) for import_path in imports):
            tags.append(tag)
    for tag, tag_markers in RESPONSIBILITY_PATH_MARKERS.items():
        if markers & tag_markers:
            tags.append(tag)
    return sorted(set(tags))


def build_duplicate_index(metrics_by_path: dict[str, FileMetrics], texts: dict[str, str]) -> None:
    window_size = 8
    hashes: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for rel_path, metrics in metrics_by_path.items():
        if metrics.generated_like or metrics.migration_like:
            continue
        norm = normalized_code_lines(texts[rel_path], metrics.language)
        if len(norm) < window_size:
            continue
        for i in range(len(norm) - window_size + 1):
            chunk = norm[i : i + window_size]
            if sum(len(x) for x in chunk) < 60:
                continue
            digest = hashlib.sha1("||".join(chunk).encode("utf-8")).hexdigest()
            hashes[digest].append((rel_path, i + 1))

    duplicates_by_file: dict[str, set[tuple[str, int]]] = defaultdict(set)
    partners_by_file: dict[str, set[str]] = defaultdict(set)
    for occs in hashes.values():
        if len(occs) < 2:
            continue
        for rel_path, start in occs:
            duplicates_by_file[rel_path].add((rel_path, start))
            for other_path, _ in occs:
                if other_path != rel_path:
                    partners_by_file[rel_path].add(other_path)

    for rel_path, metrics in metrics_by_path.items():
        metrics.duplicate_windows = len(duplicates_by_file.get(rel_path, set()))
        metrics.duplicate_partners = len(partners_by_file.get(rel_path, set()))


def severity_from_numeric(value: int, warn: int, block: int, critical: int | None = None) -> Optional[str]:
    if critical is not None and value >= critical:
        return "critical"
    if value >= block:
        return "high"
    if value >= warn:
        return "medium"
    return None


def lower_severity_if_test(severity: str, is_test: bool) -> str:
    if not is_test:
        return severity
    order = ["low", "medium", "high", "critical"]
    idx = order.index(severity)
    return order[max(0, idx - 1)]


def merge_gate_for(severity: str, extreme: bool = False, generated_like: bool = False) -> str:
    if generated_like:
        return "warn-only"
    if extreme or severity == "critical":
        return "block-now"
    if severity == "high":
        return "block-changed-files"
    if severity == "medium":
        return "warn-only"
    return "warn-only"


def decision_for(category: str) -> str:
    return {
        "scan-blocker": "fix-scan",
        "oversized-file": "split",
        "long-function": "extract",
        "hub-module": "narrow",
        "mixed-responsibility": "separate",
        "export-surface-sprawl": "narrow",
        "duplication-cluster": "deduplicate",
        "god-module": "split",
    }[category]


def finding_id(prefix: str, rel_path: str, suffix: str = "") -> str:
    digest = hashlib.sha1(f"{prefix}:{rel_path}:{suffix}".encode("utf-8")).hexdigest()[:8]
    return f"msh-{digest}"


def build_findings(metrics_by_path: dict[str, FileMetrics]) -> list[dict]:
    findings: list[dict] = []

    # scan blockers first
    for metrics in metrics_by_path.values():
        if metrics.scan_error:
            findings.append({
                "id": finding_id("scan-blocker", metrics.path),
                "category": "scan-blocker",
                "severity": "low",
                "confidence": "high",
                "title": "Scanner could not fully parse file",
                "path": metrics.path,
                "line": 1,
                "evidence_summary": metrics.scan_error,
                "recommendation": "Fix parseability first or treat downstream conclusions for this file as incomplete.",
                "merge_gate": "unverified",
                "decision": "fix-scan",
                "metrics": {"code_lines": metrics.code_lines},
                "notes": "Parsing errors reduce confidence for this file only.",
            })

    # file-level findings
    for metrics in metrics_by_path.values():
        if metrics.generated_like or metrics.migration_like:
            continue

        oversized = severity_from_numeric(
            metrics.code_lines,
            THRESHOLDS["file_warn_nloc"],
            THRESHOLDS["file_block_nloc"],
            THRESHOLDS["file_critical_nloc"],
        )
        function_pressure = severity_from_numeric(
            max(metrics.max_function_nloc, metrics.max_function_complexity),
            max(THRESHOLDS["function_warn_nloc"], THRESHOLDS["complexity_warn"]),
            max(THRESHOLDS["function_block_nloc"], THRESHOLDS["complexity_block"]),
            max(THRESHOLDS["function_critical_nloc"], THRESHOLDS["complexity_critical"]),
        )
        hub = severity_from_numeric(
            metrics.fan_out,
            THRESHOLDS["fanout_warn"],
            THRESHOLDS["fanout_block"],
            THRESHOLDS["fanout_critical"],
        )
        export_sprawl = severity_from_numeric(
            metrics.exports_count,
            THRESHOLDS["export_warn"],
            THRESHOLDS["export_block"],
            THRESHOLDS["export_critical"],
        )
        dup = None
        if metrics.duplicate_windows >= 12:
            dup = "high"
        elif metrics.duplicate_windows >= THRESHOLDS["duplicate_warn"]:
            dup = "medium"

        mixed_signal = None
        tag_count = len(metrics.responsibility_tags)
        if tag_count >= 4 and metrics.code_lines >= 200:
            mixed_signal = "high" if metrics.code_lines >= THRESHOLDS["file_block_nloc"] else "medium"
        elif tag_count >= 3 and metrics.code_lines >= 180:
            mixed_signal = "medium"
        elif tag_count >= 2 and metrics.fan_out >= THRESHOLDS["fanout_warn"] and metrics.code_lines >= 250:
            mixed_signal = "medium"

        if metrics.barrel_like and metrics.code_lines < 150 and not metrics.functions:
            export_sprawl = None

        if metrics.test_like:
            oversized = lower_severity_if_test(oversized, True) if oversized else None
            hub = lower_severity_if_test(hub, True) if hub else None
            export_sprawl = lower_severity_if_test(export_sprawl, True) if export_sprawl else None
            if mixed_signal:
                mixed_signal = lower_severity_if_test(mixed_signal, True)
            if dup:
                dup = lower_severity_if_test(dup, True)

        composite_signals = sum(bool(x) for x in [oversized, function_pressure, hub, export_sprawl, mixed_signal, dup])
        extreme = metrics.code_lines >= THRESHOLDS["file_critical_nloc"] or composite_signals >= 4

        if composite_signals >= 3 and metrics.code_lines >= THRESHOLDS["file_warn_nloc"]:
            severity = "critical" if extreme else "high"
            findings.append({
                "id": finding_id("god-module", metrics.path),
                "category": "god-module",
                "severity": severity,
                "confidence": "high",
                "title": "File is acting like a god module",
                "path": metrics.path,
                "line": 1,
                "evidence_summary": (
                    f"{metrics.code_lines} code lines, fan-out {metrics.fan_out}, "
                    f"exports {metrics.exports_count}, responsibilities {', '.join(metrics.responsibility_tags) or 'n/a'}, "
                    f"duplicate windows {metrics.duplicate_windows}, max function {metrics.max_function_nloc} lines."
                ),
                "recommendation": "Split by responsibility first: entrypoints, orchestration, data access, schema shaping, and helpers should stop living in the same module.",
                "merge_gate": merge_gate_for(severity, extreme=extreme),
                "decision": "split",
                "metrics": {
                    "code_lines": metrics.code_lines,
                    "fan_out": metrics.fan_out,
                    "exports": metrics.exports_count,
                    "responsibility_tags": metrics.responsibility_tags,
                    "duplicate_windows": metrics.duplicate_windows,
                    "max_function_nloc": metrics.max_function_nloc,
                    "max_function_complexity": metrics.max_function_complexity,
                    "composite_signals": composite_signals,
                },
                "notes": "Composite signal chosen to avoid flooding the report with one finding per metric for the same hotspot.",
            })
            # suppress single-signal file findings for this file; long-function findings still added later
            continue

        if oversized:
            severity = oversized
            findings.append({
                "id": finding_id("oversized-file", metrics.path),
                "category": "oversized-file",
                "severity": severity,
                "confidence": "high",
                "title": "File is too large for a healthy unit of change",
                "path": metrics.path,
                "line": 1,
                "evidence_summary": f"{metrics.code_lines} code lines in one file.",
                "recommendation": "Split the file by one real reason to change; do not just move code into a random helpers module.",
                "merge_gate": merge_gate_for(severity, extreme=metrics.code_lines >= THRESHOLDS['file_critical_nloc']),
                "decision": "split",
                "metrics": {"code_lines": metrics.code_lines},
                "notes": "",
            })

        if hub:
            severity = hub
            findings.append({
                "id": finding_id("hub-module", metrics.path),
                "category": "hub-module",
                "severity": severity,
                "confidence": "high",
                "title": "Module fan-out is too wide",
                "path": metrics.path,
                "line": 1,
                "evidence_summary": f"Imports {metrics.fan_out} unique modules.",
                "recommendation": "Narrow this module's role so future changes do not keep accumulating here.",
                "merge_gate": merge_gate_for(severity, extreme=metrics.fan_out >= THRESHOLDS['fanout_critical']),
                "decision": "narrow",
                "metrics": {"fan_out": metrics.fan_out, "internal_imports": len(metrics.internal_imports)},
                "notes": "",
            })

        if export_sprawl:
            severity = export_sprawl
            findings.append({
                "id": finding_id("export-surface", metrics.path),
                "category": "export-surface-sprawl",
                "severity": severity,
                "confidence": "high",
                "title": "Public surface is too wide",
                "path": metrics.path,
                "line": 1,
                "evidence_summary": f"Exports {metrics.exports_count} public symbols.",
                "recommendation": "Narrow the public surface and avoid turning one module into the default place everyone imports from.",
                "merge_gate": merge_gate_for(severity, extreme=metrics.exports_count >= THRESHOLDS['export_critical']),
                "decision": "narrow",
                "metrics": {"exports": metrics.exports_count},
                "notes": "",
            })

        if mixed_signal:
            severity = mixed_signal
            findings.append({
                "id": finding_id("mixed-responsibility", metrics.path),
                "category": "mixed-responsibility",
                "severity": severity,
                "confidence": "medium",
                "title": "Module is mixing too many responsibilities",
                "path": metrics.path,
                "line": 1,
                "evidence_summary": f"Responsibility tags: {', '.join(metrics.responsibility_tags)}.",
                "recommendation": "Separate the module by responsibility, not by arbitrary file count. Keep one coherent reason to change per file.",
                "merge_gate": merge_gate_for(severity),
                "decision": "separate",
                "metrics": {"responsibility_tags": metrics.responsibility_tags, "fan_out": metrics.fan_out, "code_lines": metrics.code_lines},
                "notes": "Responsibility mixing is heuristic; confirm with local context before broad redesigns.",
            })

        if dup:
            severity = dup
            findings.append({
                "id": finding_id("duplication-cluster", metrics.path),
                "category": "duplication-cluster",
                "severity": severity,
                "confidence": "medium",
                "title": "Repeated code blocks are accumulating in the same hotspot",
                "path": metrics.path,
                "line": 1,
                "evidence_summary": f"{metrics.duplicate_windows} duplicate windows across {metrics.duplicate_partners} partner files.",
                "recommendation": "Extract repeated control flow only after identifying the stable shared shape; do not deduplicate by inventing a worse abstraction.",
                "merge_gate": merge_gate_for(severity),
                "decision": "deduplicate",
                "metrics": {"duplicate_windows": metrics.duplicate_windows, "duplicate_partners": metrics.duplicate_partners},
                "notes": "",
            })

    # function-level findings
    long_functions: list[tuple[FileMetrics, FunctionMetric]] = []
    for metrics in metrics_by_path.values():
        if metrics.generated_like or metrics.migration_like:
            continue
        for fn in metrics.functions:
            severity = function_severity(fn)
            if severity:
                long_functions.append((metrics, fn))
    long_functions.sort(key=lambda item: (severity_rank(function_severity(item[1]) or "low"), item[1].nloc, item[1].complexity), reverse=True)
    for metrics, fn in long_functions[:12]:
        severity = function_severity(fn)
        assert severity
        findings.append({
            "id": finding_id("long-function", metrics.path, fn.name),
            "category": "long-function",
            "severity": lower_severity_if_test(severity, metrics.test_like),
            "confidence": "high",
            "title": f"Function '{fn.name}' is too large or too branch-heavy",
            "path": metrics.path,
            "line": fn.line,
            "evidence_summary": f"{fn.nloc} code lines, approx complexity {fn.complexity}, {fn.params} parameters.",
            "recommendation": "Extract coherent sub-steps and keep this function as orchestration, not as the place every branch and detail accumulates.",
            "merge_gate": merge_gate_for(lower_severity_if_test(severity, metrics.test_like), extreme=fn.nloc >= THRESHOLDS['function_critical_nloc'] or fn.complexity >= THRESHOLDS['complexity_critical']),
            "decision": "extract",
            "metrics": {"function_nloc": fn.nloc, "complexity": fn.complexity, "params": fn.params, "end_line": fn.end_line},
            "notes": "",
        })

    findings.sort(key=lambda f: (severity_rank(f["severity"]), f["path"], f["line"]), reverse=True)
    return findings


def function_severity(fn: FunctionMetric) -> Optional[str]:
    if fn.nloc >= THRESHOLDS["function_critical_nloc"] or fn.complexity >= THRESHOLDS["complexity_critical"]:
        return "critical"
    if fn.nloc >= THRESHOLDS["function_block_nloc"] or fn.complexity >= THRESHOLDS["complexity_block"]:
        return "high"
    if fn.nloc >= THRESHOLDS["function_warn_nloc"] or fn.complexity >= THRESHOLDS["complexity_warn"]:
        return "medium"
    return None


def severity_rank(severity: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}[severity]


def meaningful_source_metrics(metrics_by_path: dict[str, FileMetrics]) -> list[FileMetrics]:
    return [metrics for metrics in metrics_by_path.values() if not metrics.generated_like and not metrics.migration_like]


def overall_verdict(findings: list[dict], metrics_by_path: dict[str, FileMetrics], languages: list[str]) -> str:
    meaningful_files = meaningful_source_metrics(metrics_by_path)
    if not languages or not meaningful_files:
        return "not-applicable"
    if any(metrics.scan_error for metrics in meaningful_files):
        return "scan-blocked"
    severities = Counter(f["severity"] for f in findings if f["category"] != "scan-blocker")
    if severities["critical"] > 0:
        return "split-before-merge"
    if severities["high"] >= 2:
        return "sprawling"
    if severities["high"] >= 1 or severities["medium"] >= 3:
        return "contained"
    return "disciplined"


def summary_line(verdict: str, findings: list[dict], metrics_by_path: dict[str, FileMetrics]) -> str:
    if verdict == "not-applicable":
        return "No meaningful Python / TypeScript source surface was found for this skill."
    if verdict == "scan-blocked":
        blocker = next(
            (
                metrics
                for metrics in meaningful_source_metrics(metrics_by_path)
                if metrics.scan_error
            ),
            None,
        )
        if blocker:
            return f"Official verdict blocked until parse blockers are fixed; first blocker: {blocker.path}."
        return "Official verdict blocked until parse blockers are fixed."
    if verdict == "split-before-merge":
        hotspot = next((f for f in findings if f["severity"] in {"critical", "high"}), None)
        if hotspot:
            return f"At least one hotspot should be split before merge; worst file: {hotspot['path']}."
        return "At least one hotspot should be split before merge."
    if verdict == "sprawling":
        return "Module shape debt is spreading across several hotspots and should stop normalizing."
    if verdict == "contained":
        return "The repo has visible module-shape debt, but it still looks recoverable without major surgery."
    return "No major giant-file or god-module pressure was detected by the baseline scan."


def immediate_actions(findings: list[dict]) -> list[str]:
    actions: list[str] = []
    critical = [f for f in findings if f["severity"] == "critical" and f["category"] != "scan-blocker"]
    high = [f for f in findings if f["severity"] == "high" and f["category"] != "scan-blocker"]
    if critical:
        actions.append(f"Freeze growth in {critical[0]['path']} and split by responsibility before new feature work lands there.")
    if any(f["category"] == "long-function" and f["severity"] in {"critical", "high"} for f in findings):
        actions.append("Extract the largest orchestration functions first; they are the fastest place to stop future AI edits from compounding.")
    if any(f["category"] == "scan-blocker" for f in findings):
        actions.append("Fix parseability blockers so later runs do not overstate or understate module-shape risk.")
    return actions[:3]


def next_actions(findings: list[dict]) -> list[str]:
    actions = []
    if any(f["category"] == "hub-module" for f in findings):
        actions.append("Narrow import-heavy hub modules so fewer unrelated changes keep converging on the same file.")
    if any(f["category"] == "export-surface-sprawl" for f in findings):
        actions.append("Reduce public surfaces and stop using one module as the default import bucket.")
    if any(f["category"] == "duplication-cluster" for f in findings):
        actions.append("Deduplicate repeated control flow only after identifying a stable shared abstraction.")
    return actions[:3]


def later_actions(findings: list[dict]) -> list[str]:
    actions = []
    if any(f["category"] == "mixed-responsibility" for f in findings):
        actions.append("Document preferred file shapes for handlers, schemas, orchestration, persistence, and helpers so AI stops rebuilding catch-all files.")
    actions.append("Add this skill to merge review / CI reporting so giant files stop growing invisibly.")
    return actions[:3]


def render_human_report(summary: dict) -> str:
    scan_blocked = summary["overall_verdict"] == "scan-blocked"
    scan_blockers = [f for f in summary["findings"] if f["category"] == "scan-blocker"]
    findings = [f for f in summary["findings"] if f["category"] != "scan-blocker"]
    top = scan_blockers[:5] if scan_blocked and scan_blockers else findings[:5]
    lines: list[str] = []
    lines.append("# Module Shape Hardgate Report")
    lines.append("")
    lines.append("## 1. Executive summary")
    lines.append("")
    lines.append(f"- Overall verdict: `{summary['overall_verdict']}`")
    lines.append(f"- One-line diagnosis: `{summary['summary_line']}`")
    lines.append(f"- Files scanned: `{summary['coverage']['files_scanned']}`")
    if scan_blocked:
        lines.append(f"- Parse blockers: `{len(scan_blockers)}`")
    lines.append("")
    lines.append("## 2. Files that are too big to be trusted")
    lines.append("")
    if not top:
        if scan_blocked:
            lines.append("- Official structural verdict is blocked until parse blockers are fixed.")
        else:
            lines.append("- No major hotspots found by the deterministic baseline.")
    for finding in top:
        lines.append(f"### {finding['title']}")
        lines.append(f"- Category: `{finding['category']}`")
        lines.append(f"- Severity: `{finding['severity']}`")
        lines.append(f"- Confidence: `{finding['confidence']}`")
        lines.append(f"- Evidence: `{finding['path']}:{finding['line']}`")
        lines.append("")
        lines.append("**是什么**")
        lines.append(finding["evidence_summary"])
        lines.append("")
        lines.append("**为什么重要**")
        lines.append(explain_why_it_matters(finding))
        lines.append("")
        lines.append("**建议做什么**")
        lines.append(finding["recommendation"])
        lines.append("")
        lines.append("**给非程序员的人话解释**")
        lines.append(explain_plain_language(finding))
        lines.append("")
    lines.append("## 3. Where cohesion is broken")
    lines.append("")
    if scan_blocked:
        lines.append("- Official cohesion conclusions remain blocked until parseability is fixed.")
    else:
        lines.extend(section_bullets(findings, {"god-module", "mixed-responsibility", "long-function", "duplication-cluster"}))
    lines.append("")
    lines.append("## 4. Where coupling will spread future AI mistakes")
    lines.append("")
    if scan_blocked:
        lines.append("- Coupling conclusions remain provisional until parse blockers are removed.")
    else:
        lines.extend(section_bullets(findings, {"hub-module", "export-surface-sprawl", "god-module"}))
    lines.append("")
    lines.append("## 5. What can be split mechanically now")
    lines.append("")
    if scan_blocked:
        lines.append("- Fix parse blockers first; split recommendations would be premature before the baseline can see the full file shape.")
    else:
        lines.extend(mechanical_split_bullets(findings))
    lines.append("")
    lines.append("## 6. What still needs design decisions")
    lines.append("")
    if scan_blocked:
        lines.append("- Decide whether the blocked files should be repaired, excluded, or regenerated before relying on this skill as a merge gate.")
    else:
        lines.extend(design_decision_bullets(findings))
    lines.append("")
    lines.append("## 7. Ordered action plan")
    lines.append("")
    lines.append("### 现在就做")
    for item in summary.get("immediate_actions", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 下一步")
    for item in summary.get("next_actions", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 之后再做")
    for item in summary.get("later_actions", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 8. What this repo is teaching AI to do wrong")
    lines.append("")
    if scan_blocked:
        lines.append('- "Leave parse blockers around and still trust the structural verdict."')
    else:
        lines.extend(ai_teaching_bullets(findings))
    lines.append("")
    return "\n".join(lines)


def section_bullets(findings: list[dict], categories: set[str]) -> list[str]:
    hits = [f for f in findings if f["category"] in categories][:6]
    if not hits:
        return ["- No major issues in this section."]
    return [f"- `{f['path']}` → {f['category']} ({f['severity']}): {f['evidence_summary']}" for f in hits]


def mechanical_split_bullets(findings: list[dict]) -> list[str]:
    bullets = []
    for f in findings[:6]:
        if f["decision"] in {"split", "extract", "narrow", "deduplicate"}:
            bullets.append(f"- `{f['path']}` → {f['decision']}: {short_change_shape(f)}")
    return bullets or ["- No obviously mechanical split candidates identified."]


def design_decision_bullets(findings: list[dict]) -> list[str]:
    bullets = []
    if any(f["category"] == "mixed-responsibility" for f in findings):
        bullets.append("- Decide the intended seam: transport, schema, orchestration, persistence, or UI composition.")
    if any(f["category"] == "hub-module" for f in findings):
        bullets.append("- Decide which module should own the stable public entrypoint so imports stop converging on the current hub.")
    if not bullets:
        bullets.append("- No major design-decision blockers surfaced beyond normal module cleanup.")
    return bullets


def ai_teaching_bullets(findings: list[dict]) -> list[str]:
    bullets = []
    if any(f["category"] == "god-module" for f in findings):
        bullets.append('- "Keep adding one more behavior to the same hotspot file."')
    if any(f["category"] == "mixed-responsibility" for f in findings):
        bullets.append('- "Mix routes, schemas, DB calls, and orchestration because it is faster right now."')
    if any(f["category"] == "export-surface-sprawl" for f in findings):
        bullets.append('- "Export everything from one module so future edits naturally pile up there again."')
    if not bullets:
        bullets.append('- "File shape still matters; do not let convenience become the default architecture."')
    return bullets


def short_change_shape(finding: dict) -> str:
    if finding["category"] == "god-module":
        return "split by responsibility and stop using one file as the catch-all integration point."
    if finding["category"] == "long-function":
        return "extract coherent substeps and keep the parent function as orchestration only."
    if finding["category"] == "hub-module":
        return "narrow the file to one entrypoint role."
    if finding["category"] == "export-surface-sprawl":
        return "reduce the public surface and stop centralizing unrelated exports."
    if finding["category"] == "duplication-cluster":
        return "deduplicate only after identifying a stable shared shape."
    return "separate responsibilities into coherent modules."


def explain_why_it_matters(finding: dict) -> str:
    category = finding["category"]
    return {
        "god-module": "This file will keep attracting unrelated future edits, so AI coding becomes more likely to worsen the same hotspot.",
        "oversized-file": "A very large file stops being a healthy unit of review, testing, and ownership.",
        "long-function": "Overlong functions hide multiple decisions in one place and make future edits risky.",
        "hub-module": "When too many dependencies converge here, one change can have wide and unclear blast radius.",
        "mixed-responsibility": "One file is trying to serve several reasons to change at once, which makes it harder to keep boundaries stable.",
        "export-surface-sprawl": "A very wide public surface makes one file the default dependency bucket.",
        "duplication-cluster": "Copy-paste growth creates fake progress now and larger maintenance cost later.",
        "scan-blocker": "Without parseable evidence, later conclusions are weaker.",
    }.get(category, "This shape will get worse if future AI edits keep landing in the same module.")


def explain_plain_language(finding: dict) -> str:
    category = finding["category"]
    return {
        "god-module": "This is one room in the house that has turned into kitchen, office, warehouse, and control center at the same time.",
        "oversized-file": "One document got so big that nobody can safely understand all of it during a normal review.",
        "long-function": "One procedure is doing too many things in one breath.",
        "hub-module": "Too many parts of the system are wired through the same junction box.",
        "mixed-responsibility": "This file is wearing too many jobs at once.",
        "export-surface-sprawl": "Too many people depend on this one doorway.",
        "duplication-cluster": "The same logic is being copied instead of owned once.",
        "scan-blocker": "The scanner could not read this file cleanly enough to make a confident call.",
    }.get(category, "This file shape is teaching the system a bad habit.")


def render_agent_brief(summary: dict) -> str:
    lines = []
    lines.append("# Module Shape Hardgate Agent Brief")
    lines.append("")
    lines.append("Use short, decision-level language.")
    lines.append("")
    lines.append("## Context")
    lines.append(f"- overall_verdict: `{summary['overall_verdict']}`")
    lines.append(f"- repo_root: `{summary['repo_root']}`")
    lines.append("")
    lines.append("## Ordered actions")
    actions = summary.get("immediate_actions", []) + summary.get("next_actions", []) + summary.get("later_actions", [])
    if not actions:
        actions = ["No urgent structural action required."]
    for idx, action in enumerate(actions[:5], start=1):
        lines.append(f"{idx}. `{action}`")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    lines.append("```yaml")
    for finding in summary["findings"][:12]:
        validation = validation_checks_for(finding)
        lines.append(f"- id: {finding['id']}")
        lines.append(f"  category: {finding['category']}")
        lines.append(f"  severity: {finding['severity']}")
        lines.append(f"  confidence: {finding['confidence']}")
        lines.append(f"  title: {yaml_escape(finding['title'])}")
        lines.append(f"  path: {finding['path']}")
        lines.append(f"  line: {finding['line']}")
        lines.append(f"  evidence_summary: {yaml_escape(finding['evidence_summary'])}")
        lines.append(f"  decision: {finding['decision']}")
        lines.append(f"  change_shape: {yaml_escape(short_change_shape(finding))}")
        lines.append("  validation:")
        for item in validation:
            lines.append(f"    - {yaml_escape(item)}")
        lines.append(f"  merge_gate: {finding['merge_gate']}")
        lines.append("  autofix_allowed: false")
        notes = finding.get("notes") or ""
        lines.append(f"  notes: {yaml_escape(notes)}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def yaml_escape(value: str) -> str:
    value = value.replace("\n", " ").strip()
    if not value:
        return '""'
    if re.search(r"[:#\-\[\]\{\},]|^\s|\s$", value):
        return json.dumps(value, ensure_ascii=False)
    return value


def validation_checks_for(finding: dict) -> list[str]:
    out = ["rerun module-shape-hardgate"]
    if finding["category"] in {"oversized-file", "god-module"}:
        out.append("verify file NLOC drops below threshold")
    if finding["category"] == "long-function":
        out.append("verify function body no longer exceeds length / complexity threshold")
    if finding["category"] == "hub-module":
        out.append("verify fan-out decreases and unrelated imports leave the module")
    if finding["category"] == "export-surface-sprawl":
        out.append("verify public exports are narrowed")
    if finding["category"] == "duplication-cluster":
        out.append("verify duplicate block count decreases without inventing a worse abstraction")
    return out


def build_summary(repo_root: Path, out_dir: Path) -> dict:
    files = iter_source_files(repo_root)
    languages = sorted({SUPPORTED_SUFFIXES[p.suffix] for p in files})
    texts: dict[str, str] = {}
    metrics_by_path: dict[str, FileMetrics] = {}

    py_packages = candidate_python_packages([p for p in files if p.suffix == ".py"], repo_root)

    for path in files:
        rel_path = path.relative_to(repo_root).as_posix()
        texts[rel_path] = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".py":
            metrics_by_path[rel_path] = parse_python_file(path, rel_path, py_packages)
        else:
            metrics_by_path[rel_path] = parse_typescript_file(path, rel_path)

    build_duplicate_index(metrics_by_path, texts)
    findings = build_findings(metrics_by_path)

    coverage = {
        "files_scanned": len(metrics_by_path),
        "python_files": sum(1 for m in metrics_by_path.values() if m.language == "python"),
        "typescript_files": sum(1 for m in metrics_by_path.values() if m.language == "typescript"),
        "exempt_files": sum(1 for m in metrics_by_path.values() if m.generated_like or m.migration_like),
    }
    repo_profile = {
        "languages": languages,
        "python_files": coverage["python_files"],
        "typescript_files": coverage["typescript_files"],
        "exempt_files": coverage["exempt_files"],
        "notes": [],
    }
    verdict = overall_verdict(findings, metrics_by_path, languages)
    severity_counts = Counter(f["severity"] for f in findings if f["category"] != "scan-blocker")
    summary = {
        "schema_version": "1.0",
        "skill": "module-shape-hardgate",
        "generated_at": utc_now(),
        "repo_root": str(repo_root.resolve()),
        "repo_profile": repo_profile,
        "threshold_profile": {
            "file_warn_nloc": THRESHOLDS["file_warn_nloc"],
            "file_block_nloc": THRESHOLDS["file_block_nloc"],
            "function_warn_nloc": THRESHOLDS["function_warn_nloc"],
            "function_block_nloc": THRESHOLDS["function_block_nloc"],
            "complexity_warn": THRESHOLDS["complexity_warn"],
            "complexity_block": THRESHOLDS["complexity_block"],
            "fanout_warn": THRESHOLDS["fanout_warn"],
            "fanout_block": THRESHOLDS["fanout_block"],
            "export_warn": THRESHOLDS["export_warn"],
            "export_block": THRESHOLDS["export_block"],
        },
        "overall_verdict": verdict,
        "summary_line": summary_line(verdict, findings, metrics_by_path),
        "coverage": coverage,
        "severity_counts": {
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
        },
        "findings": findings,
        "immediate_actions": immediate_actions(findings),
        "next_actions": next_actions(findings),
        "later_actions": later_actions(findings),
        "assumptions": [
            "TypeScript parsing is heuristic in the standalone baseline; treat mixed-responsibility findings as structural signals, not parser-level proof."
        ],
        "dependency_status": "ready",
        "bootstrap_actions": [],
        "dependency_failures": [],
    }
    return summary


def write_outputs(
    summary: dict,
    out_dir: Path,
    summary_path: Path | None = None,
    report_path: Path | None = None,
    brief_path: Path | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_summary = summary_path or (out_dir / SUMMARY_FILENAME)
    resolved_report = report_path or (out_dir / REPORT_FILENAME)
    resolved_brief = brief_path or (out_dir / BRIEF_FILENAME)
    resolved_summary.parent.mkdir(parents=True, exist_ok=True)
    resolved_report.parent.mkdir(parents=True, exist_ok=True)
    resolved_brief.parent.mkdir(parents=True, exist_ok=True)
    resolved_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    resolved_report.write_text(render_human_report(summary), encoding="utf-8")
    resolved_brief.write_text(render_agent_brief(summary), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run module shape hardgate scan.")
    parser.add_argument("--repo", required=True, help="Repository root to scan.")
    parser.add_argument("--out-dir", required=True, help="Output directory.")
    parser.add_argument("--summary-out", default=None, help="Optional explicit summary output path.")
    parser.add_argument("--report-out", default=None, help="Optional explicit human report output path.")
    parser.add_argument("--agent-brief-out", default=None, help="Optional explicit agent brief output path.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    out_dir = Path(args.out_dir).resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        print(f"error: repo root does not exist: {repo_root}", file=sys.stderr)
        return 2

    summary = build_summary(repo_root, out_dir)
    summary_path = Path(args.summary_out).resolve() if args.summary_out else None
    report_path = Path(args.report_out).resolve() if args.report_out else None
    brief_path = Path(args.agent_brief_out).resolve() if args.agent_brief_out else None
    write_outputs(summary, out_dir, summary_path=summary_path, report_path=report_path, brief_path=brief_path)
    print(f"Wrote {(summary_path or (out_dir / SUMMARY_FILENAME)).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
