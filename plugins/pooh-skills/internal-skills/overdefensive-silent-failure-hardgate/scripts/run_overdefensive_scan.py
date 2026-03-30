#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SKILL = "overdefensive-silent-failure-hardgate"
SCHEMA_VERSION = "1.0.0"

EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".next",
    ".repo-harness",
    ".pooh-runtime",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "target",
    "vendor",
    ".venv",
    "venv",
    "site-packages",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

MAX_FILE_BYTES = 1_000_000
OPTIONALITY_SIGNAL_LIMIT = 4
CHAIN_SIGNAL_LIMIT = 4
DEFAULT_SIGNAL_LIMIT = 4

RE_OPTIONAL_PY = re.compile(r"\bOptional\s*\[|(?:\b[A-Za-z_][A-Za-z0-9_]*|\])\s*\|\s*None\b")
RE_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore\b|#\s*pyright:\s*ignore\b")
RE_NOQA = re.compile(r"#\s*noqa\b", re.IGNORECASE)

RE_TS_COMMENT = re.compile(r"@ts-(?:ignore|expect-error|nocheck)\b")
RE_ESLINT_DISABLE = re.compile(r"eslint-disable")
RE_AS_ANY = re.compile(r"\bas\s+any\b")
RE_DOUBLE_ASSERT = re.compile(r"\bas\s+unknown\s+as\b")
RE_EMPTY_CATCH = re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}", re.DOTALL)
RE_CATCH_EMPTY_BODY_ARROW = re.compile(
    r"\.catch\s*\(\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)?\s*=>\s*\{\s*\}\s*\)",
    re.DOTALL,
)
RE_CATCH_UNDEFINED = re.compile(
    r"\.catch\s*\(\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)?\s*=>\s*(?:undefined|null|void\s+0)\s*\)",
    re.DOTALL,
)
RE_FAKE_CATCH = re.compile(r"\.catch\s*;")
RE_UNSAFE_OPTIONAL_CHAIN = re.compile(r"\?\.[^\n;]*!")
RE_NON_NULL = re.compile(r"(?<![=!])\b[A-Za-z_$][\w$.\]\)]*!\s*(?:[.\[\);,:?]|$)")
RE_OPTIONAL_CHAIN_LINE = re.compile(r"\?\.")
RE_TRUTHY_DEFAULT = re.compile(r"(?:=|return)\s+[^;\n]*\|\|\s*(?:['\"`].*?['\"`]|[0-9]+|\[\]|\{\}|true|false|null|undefined)")
RE_NULLISH_DEFAULT = re.compile(r"(?:=|return)\s+[^;\n]*\?\?\s*(?:['\"`].*?['\"`]|[0-9]+|\[\]|\{\}|true|false|null|undefined)")
RE_USELESS_CATCH = re.compile(r"catch\s*\([^)]*\)\s*\{\s*throw\b", re.DOTALL)

RE_BOUNDARY_PATH = re.compile(
    r"(api|http|transport|serializer|schema|dto|parser|validation|validator|tests?|migrations?)",
    re.IGNORECASE,
)


@dataclass
class Finding:
    category: str
    severity: str
    confidence: str
    language: str
    title: str
    path: str
    line: int
    evidence: list[str]
    recommendation: str
    merge_gate: str
    notes: str = ""

    def to_json(self, idx: int) -> dict:
        return {
            "id": f"osf-{idx:03d}",
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "language": self.language,
            "title": self.title,
            "path": self.path,
            "line": self.line,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "merge_gate": self.merge_gate,
            "notes": self.notes,
        }


RECOMMENDATIONS = {
    "exception-swallow": "Catch only the expected error, emit explicit degrade state if truly intended, otherwise let the failure surface.",
    "skip-on-error": "Do not silently skip work. Collect failures explicitly or stop the batch when data loss is unacceptable.",
    "cause-chain-loss": "Preserve the original error with `from e` or `cause` so debugging keeps the causal chain.",
    "async-exception-leak": "Await, gather, or explicitly observe background work instead of letting it fail off-camera.",
    "optionality-leak": "Keep absence localized at the boundary. Restore required contracts in core paths.",
    "silent-default": "Replace hidden defaults with explicit validation or explicit degraded-state handling.",
    "truthiness-fallback": "Distinguish nullish from legitimate falsy values instead of using blanket truthiness fallback.",
    "unsafe-optional-chain": "Remove optional chaining from invariant paths or narrow the value before access.",
    "type-escape-hatch": "Replace assertions / casts with narrowing, runtime validation, or a documented compatibility adapter.",
    "lint-escape-hatch": "Stop silencing the checker. Fix the rule violation or quarantine the edge case behind an explicit adapter.",
    "useless-catch-theater": "Delete fake error-handling layers that add noise but do not change behavior or observability.",
    "scan-blocker": "Fix the parsing or scan blocker so the audit can make a real judgment.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan a repo for over-defensive and silent-failure patterns.")
    parser.add_argument("--repo", required=True, help="Repository root to scan")
    parser.add_argument("--out", required=True, help="Path to output summary JSON")
    return parser.parse_args()


def should_skip(path: Path) -> bool:
    if path.name.endswith(".min.js"):
        return True
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return True
    except OSError:
        return True
    return False


def iter_files(repo_root: Path) -> Iterable[Path]:
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        if path.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
            yield path


def rel(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def is_boundary_path(rel_path: str) -> bool:
    return bool(RE_BOUNDARY_PATH.search(rel_path))


def get_line(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def evidence_from_line(lines: list[str], line_no: int) -> str:
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()[:240]
    return ""


def is_default_literal(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (str, int, float, bool, type(None)))
    if isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
        return True
    return False


def call_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def broad_exception_name(node: ast.AST | None) -> str:
    if node is None:
        return "bare"
    try:
        if isinstance(node, ast.Tuple):
            names = [broad_exception_name(elt) for elt in node.elts]
            return ", ".join(filter(None, names))
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return call_name(node)
    except Exception:
        pass
    return ""


def is_broad_exception(node: ast.AST | None) -> bool:
    name = broad_exception_name(node)
    broad = {"bare", "Exception", "BaseException", "builtins.Exception", "builtins.BaseException"}
    if name in broad:
        return True
    if isinstance(node, ast.Tuple):
        return any(is_broad_exception(elt) for elt in node.elts)
    return False


def build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def add_finding(findings: list[Finding], seen: set[tuple], finding: Finding) -> None:
    key = (finding.category, finding.path, finding.line, finding.title)
    if key in seen:
        return
    seen.add(key)
    findings.append(finding)


def python_comment_tokens(text: str) -> list[tuple[int, str]]:
    comments: list[tuple[int, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                comments.append((token.start[0], token.string))
    except tokenize.TokenError:
        return comments
    return comments


def python_code_lines(text: str) -> dict[int, str]:
    buckets: defaultdict[int, list[str]] = defaultdict(list)
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type in {tokenize.STRING, tokenize.COMMENT, tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT}:
                continue
            if token.string.strip():
                buckets[token.start[0]].append(token.string)
    except tokenize.TokenError:
        return {}
    return {line: " ".join(parts) for line, parts in buckets.items()}


def sanitize_js_source(text: str) -> tuple[str, list[tuple[int, str]]]:
    chars = list(text)
    comments: list[tuple[int, str]] = []
    i = 0
    line = 1
    length = len(chars)
    state = "code"
    quote = ""

    while i < length:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < length else ""

        if state == "code":
            if ch == "/" and nxt == "/":
                start = i
                comment_line = line
                i += 2
                while i < length and chars[i] != "\n":
                    i += 1
                comment = text[start:i]
                comments.append((comment_line, comment))
                for idx in range(start, i):
                    chars[idx] = " "
                continue
            if ch == "/" and nxt == "*":
                start = i
                comment_line = line
                i += 2
                while i < length - 1 and not (chars[i] == "*" and chars[i + 1] == "/"):
                    if chars[i] == "\n":
                        line += 1
                    i += 1
                i = min(i + 2, length)
                comment = text[start:i]
                comments.append((comment_line, comment))
                for idx in range(start, i):
                    if chars[idx] != "\n":
                        chars[idx] = " "
                continue
            if ch in {"'", '"', "`"}:
                quote = ch
                state = "string"
                if ch != "\n":
                    chars[i] = " "
                i += 1
                continue
        elif state == "string":
            if ch == "\\":
                if ch != "\n":
                    chars[i] = " "
                i += 1
                if i < length and chars[i] != "\n":
                    chars[i] = " "
                i += 1
                continue
            if ch == quote:
                chars[i] = " "
                state = "code"
                i += 1
                continue
            if ch != "\n":
                chars[i] = " "

        if ch == "\n":
            line += 1
        i += 1

    return "".join(chars), comments


def scan_python(path: Path, repo_root: Path, findings: list[Finding], seen: set[tuple], scan_blockers: list[str]) -> None:
    rel_path = rel(path, repo_root)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    # Comment-level suppressions should only trigger from real comment tokens, not from strings.
    optional_signals = 0
    code_lines = python_code_lines(text)
    for idx, comment in python_comment_tokens(text):
        if RE_TYPE_IGNORE.search(comment):
            add_finding(
                findings,
                seen,
                Finding(
                    category="type-escape-hatch",
                    severity="high",
                    confidence="high",
                    language="python",
                    title="Type ignore suppresses checker feedback",
                    path=rel_path,
                    line=idx,
                    evidence=[evidence_from_line(lines, idx)],
                    recommendation=RECOMMENDATIONS["type-escape-hatch"],
                    merge_gate="block-changed-files",
                ),
            )
        elif RE_NOQA.search(comment):
            add_finding(
                findings,
                seen,
                Finding(
                    category="lint-escape-hatch",
                    severity="medium",
                    confidence="high",
                    language="python",
                    title="noqa suppresses linter feedback",
                    path=rel_path,
                    line=idx,
                    evidence=[evidence_from_line(lines, idx)],
                    recommendation=RECOMMENDATIONS["lint-escape-hatch"],
                    merge_gate="block-changed-files",
                ),
            )

    for idx, code_line in sorted(code_lines.items()):
        if not is_boundary_path(rel_path) and optional_signals < OPTIONALITY_SIGNAL_LIMIT and RE_OPTIONAL_PY.search(code_line):
            optional_signals += 1
            add_finding(
                findings,
                seen,
                Finding(
                    category="optionality-leak",
                    severity="low",
                    confidence="low",
                    language="python",
                    title="Nullable type appears in a non-boundary path",
                    path=rel_path,
                    line=idx,
                    evidence=[line.strip()],
                    recommendation=RECOMMENDATIONS["optionality-leak"],
                    merge_gate="unverified",
                    notes="A single Optional is not a failure by itself; inspect whether the absence should remain at the boundary.",
                ),
            )

    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError as exc:
        scan_blockers.append(f"{rel_path}:{exc.lineno or 1} could not be parsed by the bundled Python scanner ({exc.msg})")
        return

    parents = build_parent_map(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            broad = is_broad_exception(node.type)
            node_line = getattr(node, "lineno", 1)
            body_nodes = list(ast.walk(ast.Module(body=node.body, type_ignores=[])))
            has_pass = any(isinstance(n, ast.Pass) for n in body_nodes)
            has_continue = any(isinstance(n, ast.Continue) for n in body_nodes)
            has_return_default = any(isinstance(n, ast.Return) and is_default_literal(n.value) for n in body_nodes)
            raise_without_cause = any(
                isinstance(n, ast.Raise) and n.exc is not None and n.cause is None
                for n in body_nodes
            )

            if broad and has_pass:
                title = "Broad except with pass swallows the failure"
                sev = "critical" if node.type is None else "high"
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="exception-swallow",
                        severity=sev,
                        confidence="high",
                        language="python",
                        title=title,
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["exception-swallow"],
                        merge_gate="block-now",
                    ),
                )
            elif broad and has_continue:
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="skip-on-error",
                        severity="critical" if node.type is None else "high",
                        confidence="high",
                        language="python",
                        title="Broad except continues the loop after failure",
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["skip-on-error"],
                        merge_gate="block-now",
                    ),
                )
            elif broad and has_return_default:
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="silent-default",
                        severity="high" if node.type is None else "medium",
                        confidence="medium",
                        language="python",
                        title="Broad except returns a default instead of surfacing the error",
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["silent-default"],
                        merge_gate="block-changed-files" if node.type is None else "warn-only",
                    ),
                )
            elif broad:
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="exception-swallow",
                        severity="high" if node.type is None else "medium",
                        confidence="medium",
                        language="python",
                        title="Broad except widens the failure channel",
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["exception-swallow"],
                        merge_gate="block-changed-files" if node.type is None else "warn-only",
                        notes="Broad exception handling can be legitimate at process boundaries, but should not become default internal style.",
                    ),
                )

            if raise_without_cause:
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="cause-chain-loss",
                        severity="medium",
                        confidence="high",
                        language="python",
                        title="New exception is raised in except without `from e`",
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["cause-chain-loss"],
                        merge_gate="block-changed-files",
                    ),
                )

        elif isinstance(node, ast.Call):
            name = call_name(node.func)
            node_line = getattr(node, "lineno", 1)

            if name in {"contextlib.suppress", "suppress"}:
                confidence = "high" if any(is_broad_exception(arg) for arg in node.args) else "medium"
                severity = "high" if confidence == "high" else "medium"
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="exception-swallow",
                        severity=severity,
                        confidence=confidence,
                        language="python",
                        title="contextlib.suppress hides exceptions",
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["exception-swallow"],
                        merge_gate="block-changed-files" if confidence == "high" else "warn-only",
                    ),
                )

            if name in {"typing.cast", "cast"}:
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="type-escape-hatch",
                        severity="medium",
                        confidence="high",
                        language="python",
                        title="typing.cast bypasses checker scrutiny",
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["type-escape-hatch"],
                        merge_gate="block-changed-files",
                    ),
                )

            if name.endswith("create_task") or name.endswith("ensure_future"):
                parent = parents.get(id(node))
                if isinstance(parent, ast.Expr):
                    add_finding(
                        findings,
                        seen,
                        Finding(
                            category="async-exception-leak",
                            severity="high",
                            confidence="high",
                            language="python",
                            title="Fire-and-forget async task is launched without observation",
                            path=rel_path,
                            line=node_line,
                            evidence=[evidence_from_line(lines, node_line)],
                            recommendation=RECOMMENDATIONS["async-exception-leak"],
                            merge_gate="block-changed-files",
                        ),
                    )

            if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    if len(node.args) >= 2 or not is_boundary_path(rel_path):
                        add_finding(
                            findings,
                            seen,
                            Finding(
                                category="silent-default",
                                severity="medium" if len(node.args) >= 2 else "low",
                                confidence="low",
                                language="python",
                                title="dict.get style fallback may soften a required key",
                                path=rel_path,
                                line=node_line,
                                evidence=[evidence_from_line(lines, node_line)],
                                recommendation=RECOMMENDATIONS["silent-default"],
                                merge_gate="unverified" if len(node.args) == 1 else "warn-only",
                                notes="Treat as stronger evidence when the key is contractually required and this is not boundary parsing code.",
                            ),
                        )

            if name == "getattr" and len(node.args) >= 3:
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="optionality-leak",
                        severity="low",
                        confidence="low",
                        language="python",
                        title="getattr fallback may hide a model contract break",
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["optionality-leak"],
                        merge_gate="unverified",
                    ),
                )

            if name == "hasattr":
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="optionality-leak",
                        severity="low",
                        confidence="low",
                        language="python",
                        title="hasattr may be widening a contract into maybe-logic",
                        path=rel_path,
                        line=node_line,
                        evidence=[evidence_from_line(lines, node_line)],
                        recommendation=RECOMMENDATIONS["optionality-leak"],
                        merge_gate="unverified",
                    ),
                )

        elif isinstance(node, (ast.Assign, ast.Return)):
            value = node.value if isinstance(node, ast.Return) else node.value
            if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.Or) and len(value.values) == 2:
                line_no = getattr(node, "lineno", 1)
                add_finding(
                    findings,
                    seen,
                    Finding(
                        category="truthiness-fallback",
                        severity="medium",
                        confidence="low",
                        language="python",
                        title="Truthiness fallback may overwrite legitimate falsy values",
                        path=rel_path,
                        line=line_no,
                        evidence=[evidence_from_line(lines, line_no)],
                        recommendation=RECOMMENDATIONS["truthiness-fallback"],
                        merge_gate="warn-only",
                        notes="Escalate only when `0`, `''`, or `[]` are legitimate values in this contract.",
                    ),
                )


def scan_text_patterns(path: Path, repo_root: Path, findings: list[Finding], seen: set[tuple]) -> None:
    rel_path = rel(path, repo_root)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    sanitized_text, comment_tokens = sanitize_js_source(text)
    sanitized_lines = sanitized_text.splitlines()
    chain_signals = 0
    default_signals = 0

    def emit(category: str, severity: str, confidence: str, language: str, title: str, pos: int, merge_gate: str, notes: str = "") -> None:
        line_no = get_line(sanitized_text, pos)
        add_finding(
            findings,
            seen,
            Finding(
                category=category,
                severity=severity,
                confidence=confidence,
                language=language,
                title=title,
                path=rel_path,
                line=line_no,
                evidence=[evidence_from_line(lines, line_no)],
                recommendation=RECOMMENDATIONS[category],
                merge_gate=merge_gate,
                notes=notes,
            ),
        )

    language = "typescript" if path.suffix.lower() in {".ts", ".tsx"} else "javascript"

    for pattern, category, severity, confidence, title, gate in [
        (RE_EMPTY_CATCH, "exception-swallow", "high", "high", "Empty catch block swallows the error", "block-now"),
        (RE_CATCH_EMPTY_BODY_ARROW, "exception-swallow", "high", "high", "Promise catch handler is empty", "block-now"),
        (RE_CATCH_UNDEFINED, "exception-swallow", "high", "high", "Promise catch converts rejection into silent default", "block-now"),
        (RE_FAKE_CATCH, "exception-swallow", "high", "high", "`.catch;` pretends to handle rejection without doing it", "block-now"),
        (RE_AS_ANY, "type-escape-hatch", "high", "high", "`as any` erases type feedback", "block-changed-files"),
        (RE_DOUBLE_ASSERT, "type-escape-hatch", "high", "high", "Double assertion (`as unknown as`) bypasses real narrowing", "block-changed-files"),
        (RE_UNSAFE_OPTIONAL_CHAIN, "unsafe-optional-chain", "high", "high", "Optional chain is followed by a non-null assertion", "block-changed-files"),
        (RE_USELESS_CATCH, "useless-catch-theater", "low", "medium", "Catch block looks like theater rather than handling", "warn-only"),
    ]:
        for match in pattern.finditer(sanitized_text):
            emit(category, severity, confidence, language, title, match.start(), gate)

    for line_no, comment in comment_tokens:
        if RE_TS_COMMENT.search(comment):
            add_finding(
                findings,
                seen,
                Finding(
                    category="type-escape-hatch",
                    severity="high",
                    confidence="high",
                    language=language,
                    title="ts-comment suppression hides a type problem",
                    path=rel_path,
                    line=line_no,
                    evidence=[evidence_from_line(lines, line_no)],
                    recommendation=RECOMMENDATIONS["type-escape-hatch"],
                    merge_gate="block-changed-files",
                ),
            )
        if RE_ESLINT_DISABLE.search(comment):
            add_finding(
                findings,
                seen,
                Finding(
                    category="lint-escape-hatch",
                    severity="medium",
                    confidence="high",
                    language=language,
                    title="eslint-disable suppresses rule feedback",
                    path=rel_path,
                    line=line_no,
                    evidence=[evidence_from_line(lines, line_no)],
                    recommendation=RECOMMENDATIONS["lint-escape-hatch"],
                    merge_gate="block-changed-files",
                ),
            )

    # Non-null assertions can be noisy, so keep them as a weaker signal.
    non_null_count = 0
    for match in RE_NON_NULL.finditer(sanitized_text):
        if "?. " in match.group(0):
            continue
        line_no = get_line(sanitized_text, match.start())
        line = evidence_from_line(lines, line_no)
        if "!=" in line or "!==" in line:
            continue
        non_null_count += 1
        if non_null_count > 4:
            break
        add_finding(
            findings,
            seen,
            Finding(
                category="type-escape-hatch",
                severity="medium",
                confidence="medium",
                language=language,
                title="Non-null assertion removes a nullish safety check at compile time",
                path=rel_path,
                line=line_no,
                evidence=[line],
                recommendation=RECOMMENDATIONS["type-escape-hatch"],
                merge_gate="warn-only",
                notes="Escalate when this sits on a path that should be narrowed earlier or is paired with optional chaining.",
            ),
        )

    for idx, line in enumerate(sanitized_lines, start=1):
        raw_line = evidence_from_line(lines, idx)
        if chain_signals < CHAIN_SIGNAL_LIMIT and line.count("?.") >= 2:
            chain_signals += 1
            add_finding(
                findings,
                seen,
                Finding(
                    category="optionality-leak",
                    severity="low",
                    confidence="low",
                    language=language,
                    title="Optional chaining is stacked on a core access path",
                    path=rel_path,
                    line=idx,
                    evidence=[raw_line],
                    recommendation=RECOMMENDATIONS["optionality-leak"],
                    merge_gate="unverified",
                    notes="This becomes stronger evidence when the path is supposed to be invariant after validation.",
                ),
            )

        if default_signals < DEFAULT_SIGNAL_LIMIT and "||" in line and RE_TRUTHY_DEFAULT.search(line):
            default_signals += 1
            add_finding(
                findings,
                seen,
                Finding(
                    category="truthiness-fallback",
                    severity="medium",
                    confidence="low",
                    language=language,
                    title="`||` fallback may overwrite legitimate falsy values",
                    path=rel_path,
                    line=idx,
                    evidence=[raw_line],
                    recommendation=RECOMMENDATIONS["truthiness-fallback"],
                    merge_gate="warn-only",
                ),
            )
        if default_signals < DEFAULT_SIGNAL_LIMIT and "??" in line and RE_NULLISH_DEFAULT.search(line):
            default_signals += 1
            add_finding(
                findings,
                seen,
                Finding(
                    category="silent-default",
                    severity="low",
                    confidence="low",
                    language=language,
                    title="Nullish fallback may be softening a required contract",
                    path=rel_path,
                    line=idx,
                    evidence=[raw_line],
                    recommendation=RECOMMENDATIONS["silent-default"],
                    merge_gate="unverified",
                ),
            )


def summarize(findings: list[Finding], coverage: dict, scan_blockers: list[str], repo_root: Path) -> dict:
    severity_counts = Counter({"critical": 0, "high": 0, "medium": 0, "low": 0})
    category_counts: Counter[str] = Counter()
    for finding in findings:
        severity_counts[finding.severity] += 1
        category_counts[finding.category] += 1

    if coverage["files_scanned"] == 0:
        verdict = "not-applicable"
        summary_line = "No Python / TypeScript source files were found for this audit."
    elif severity_counts["critical"] or category_counts["exception-swallow"] or category_counts["skip-on-error"] or category_counts["async-exception-leak"]:
        verdict = "silent-failure-risk"
        summary_line = (
            f"Found {severity_counts['critical'] + severity_counts['high']} strong silent-failure indicators "
            f"and {severity_counts['medium'] + severity_counts['low']} softer contract-softening signals."
        )
    elif category_counts["type-escape-hatch"] or category_counts["lint-escape-hatch"] or category_counts["silent-default"] or category_counts["truthiness-fallback"] or category_counts["optionality-leak"] or category_counts["unsafe-optional-chain"]:
        verdict = "contract-softened"
        summary_line = (
            f"Strong silent-failure evidence is limited, but the repo shows {sum(category_counts.values())} "
            "contract-softening or escape-hatch signals."
        )
    else:
        verdict = "fail-loud"
        summary_line = "No strong bundled-scan evidence of silent failure or contract softening was found."

    return {
        "schema_version": SCHEMA_VERSION,
        "skill": SKILL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "overall_verdict": verdict,
        "summary_line": summary_line,
        "coverage": coverage,
        "severity_counts": {
            "critical": severity_counts["critical"],
            "high": severity_counts["high"],
            "medium": severity_counts["medium"],
            "low": severity_counts["low"],
        },
        "category_counts": dict(category_counts),
        "scan_blockers": scan_blockers,
        "findings": [finding.to_json(idx + 1) for idx, finding in enumerate(findings)],
        "dependency_status": "ready",
        "bootstrap_actions": [],
        "dependency_failures": [],
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo).resolve()
    out_path = Path(args.out).resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        print(f"Repository root does not exist or is not a directory: {repo_root}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    seen: set[tuple] = set()
    scan_blockers: list[str] = []

    coverage = {"files_scanned": 0, "python_files": 0, "ts_files": 0, "js_files": 0}

    for path in iter_files(repo_root):
        coverage["files_scanned"] += 1
        suffix = path.suffix.lower()
        if suffix == ".py":
            coverage["python_files"] += 1
            scan_python(path, repo_root, findings, seen, scan_blockers)
        elif suffix in {".ts", ".tsx"}:
            coverage["ts_files"] += 1
            scan_text_patterns(path, repo_root, findings, seen)
        else:
            coverage["js_files"] += 1
            scan_text_patterns(path, repo_root, findings, seen)

    summary = summarize(findings, coverage, scan_blockers, repo_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
