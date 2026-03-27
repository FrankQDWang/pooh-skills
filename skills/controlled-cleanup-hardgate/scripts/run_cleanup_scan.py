#!/usr/bin/env python3
"""Heuristic cleanup scanner for large repositories.

The scanner is intentionally conservative: it finds likely cleanup signals, not proofs.
It uses only the Python standard library so it runs on macOS and Linux with Python 3.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

TEXT_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".kts", ".go", ".rb", ".php", ".cs", ".cpp",
    ".cc", ".cxx", ".c", ".h", ".hpp", ".scala", ".rs", ".swift",
    ".md", ".mdx", ".rst", ".txt", ".adoc", ".yaml", ".yml", ".json",
    ".toml", ".ini", ".cfg", ".properties", ".gradle", ".sh", ".bash",
    ".zsh", ".sql",
}

DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".txt", ".adoc"}

IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", "dist", "build",
    "target", "out", "coverage", ".next", ".turbo", ".cache", ".idea",
    ".vscode", "vendor", "__pycache__", "generated", ".repo-harness",
}

MANIFESTS = {
    "package.json": "node",
    "pnpm-workspace.yaml": "node",
    "yarn.lock": "node",
    "package-lock.json": "node",
    "tsconfig.json": "typescript",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "poetry.lock": "python",
    "Pipfile": "python",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "java",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "mkdocs.yml": "docs",
    "docusaurus.config.js": "docs",
    "docusaurus.config.ts": "docs",
    "sidebars.js": "docs",
    "sidebars.ts": "docs",
    ".github/workflows": "ci",
}

LANGUAGE_BY_EXT = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".go": "Go", ".rb": "Ruby",
    ".php": "PHP", ".cs": "C#", ".cpp": "C/C++", ".cc": "C/C++", ".cxx": "C/C++",
    ".c": "C/C++", ".h": "C/C++", ".hpp": "C/C++", ".scala": "Scala", ".rs": "Rust",
    ".swift": "Swift", ".md": "Markdown", ".mdx": "Markdown", ".rst": "RST", ".adoc": "AsciiDoc",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON", ".toml": "TOML",
    ".ini": "Config", ".cfg": "Config", ".properties": "Config", ".gradle": "Gradle",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".sql": "SQL",
}

NON_SOURCE_LANGUAGES = {
    "Markdown", "RST", "AsciiDoc", "YAML", "JSON", "TOML", "Config", "Shell", "SQL"
}

STRUCTURED_DEPRECATION_PATTERNS = [
    re.compile(r"@deprecated\b", re.IGNORECASE),
    re.compile(r"@Deprecated\b"),
    re.compile(r"DeprecationWarning\b"),
    re.compile(r"(?im)^\s*(?:#|//|/\*+|\*|>|-)?\s*deprecated\b[:.]"),
    re.compile(r"REMOVE[-_ ]?AFTER\b", re.IGNORECASE),
    re.compile(r"\bsunset\s*[:=]", re.IGNORECASE),
]

SHIM_PATH_PATTERN = re.compile(
    r"(^|/)(legacy|compat|compatibility|shim|deprecated|adapters?/legacy)(/|$)",
    re.IGNORECASE,
)
SHIM_TEXT_PATTERNS = [
    re.compile(r"\bcompat(?:ibility)?\s+(?:shim|layer|adapter|wrapper)\b", re.IGNORECASE),
    re.compile(r"\blegacy\s+alias\b", re.IGNORECASE),
    re.compile(r"\bbackward compatible\b", re.IGNORECASE),
]

FEATURE_FLAG_PATTERNS = [
    re.compile(r"feature[_ -]?flag", re.IGNORECASE),
    re.compile(r"LaunchDarkly"),
    re.compile(r"OpenFeature"),
    re.compile(r"Unleash"),
    re.compile(r"flag[_A-Z]"),
    re.compile(r"is_enabled\("),
]

DYNAMIC_RISK_PATTERNS = [
    re.compile(r"\bgetattr\("),
    re.compile(r"\bsetattr\("),
    re.compile(r"\bimportlib\b"),
    re.compile(r"\b__import__\("),
    re.compile(r"\beval\("),
    re.compile(r"\bexec\("),
    re.compile(r"\bClass\.forName\("),
    re.compile(r"\bServiceLoader\b"),
    re.compile(r"\bReflect\."),
    re.compile(r"\bimport\s*\("),
]

REPLACEMENT_PATTERNS = [
    re.compile(r"replace[-_ ]?with\s*[:=]\s*([^\n*]+)", re.IGNORECASE),
    re.compile(r"use\s+([^\n]+?)\s+instead", re.IGNORECASE),
    re.compile(r"replacement\s*[:=]\s*([^\n*]+)", re.IGNORECASE),
]

REMOVAL_TARGET_PATTERNS = [
    re.compile(r"remove[-_ ]?after\s*[:=]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.IGNORECASE),
    re.compile(r"sunset\s*[:=]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.IGNORECASE),
    re.compile(r"remove[-_ ]?(?:by|in|on|target)?\s*[:=]\s*(v?\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
]

TEST_HINTS = [
    "pytest.ini", "tox.ini", "noxfile.py", "jest.config.js", "vitest.config.ts", "go.mod",
    "pom.xml", "build.gradle", "build.gradle.kts", ".github/workflows",
]

CI_HINTS = [
    ".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml",
]


@dataclass
class Finding:
    category: str
    severity: str
    confidence: str
    path: str
    line: int | None
    language: str | None
    summary: str
    cue: str | None
    replacement: str | None
    removal_target: str | None
    evidence: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "path": self.path,
            "line": self.line,
            "language": self.language,
            "summary": self.summary,
            "cue": self.cue,
            "replacement": self.replacement,
            "removal_target": self.removal_target,
            "evidence": self.evidence,
        }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan a repository for cleanup signals.")
    parser.add_argument("--repo", default=".", help="Repository root to scan.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument("--max-file-bytes", type=int, default=1_000_000, help="Skip larger files.")
    return parser.parse_args(argv)


def iter_files(repo: Path, max_file_bytes: int) -> Iterator[Path]:
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        root_path = Path(root)
        for name in files:
            path = root_path / name
            if should_scan(path, max_file_bytes):
                yield path


def should_scan(path: Path, max_file_bytes: int) -> bool:
    try:
        if path.stat().st_size > max_file_bytes:
            return False
    except OSError:
        return False
    if path.name in MANIFESTS:
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def language_for(path: Path) -> str | None:
    return LANGUAGE_BY_EXT.get(path.suffix.lower())


def is_doc_file(path: Path) -> bool:
    return path.suffix.lower() in DOC_EXTENSIONS


def is_code_or_config_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS and not is_doc_file(path)


def infer_repo_profile(repo: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    manifests: set[str] = set()
    docs_roots: set[str] = set()
    language_hints: set[str] = set()
    tool_hints: set[str] = set()

    workflows_dir = repo / ".github" / "workflows"
    if workflows_dir.exists():
        manifests.add(".github/workflows")
        tool_hints.add("ci")

    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        root_path = Path(root)

        for dir_name in dirs:
            dir_path = root_path / dir_name
            rel_dir = dir_path.relative_to(repo).as_posix()
            if dir_name.lower() in {"docs", "documentation", "wiki"}:
                docs_roots.add(rel_dir)
            manifest_kind = MANIFESTS.get(rel_dir)
            if manifest_kind:
                manifests.add(rel_dir)
                tool_hints.add(manifest_kind)

        for name in files:
            path = root_path / name
            rel = path.relative_to(repo).as_posix()
            manifest_kind = MANIFESTS.get(name) or MANIFESTS.get(rel)
            if manifest_kind:
                manifests.add(rel)
                tool_hints.add(manifest_kind)

            language = LANGUAGE_BY_EXT.get(path.suffix.lower())
            if language and language not in NON_SOURCE_LANGUAGES:
                language_hints.add(language)

    recommended_tools = set()
    if any(m.endswith(("package.json", "tsconfig.json")) for m in manifests):
        recommended_tools.update(["tsc", "eslint", "knip", "jscodeshift/ast-grep"])
    if any(m.endswith(("pyproject.toml", "requirements.txt", "setup.py", "Pipfile")) for m in manifests):
        recommended_tools.update(["ruff", "mypy/pyright", "vulture", "LibCST"])
    if any(m.endswith(("pom.xml", "build.gradle", "build.gradle.kts")) for m in manifests):
        recommended_tools.update(["OpenRewrite", "Error Prone", "SpotBugs", "JaCoCo"])
    if any(m.endswith("go.mod") for m in manifests):
        recommended_tools.update(["golangci-lint", "Staticcheck", "go test -coverprofile"])
    if docs_roots or any("docusaurus" in m or m.endswith("mkdocs.yml") for m in manifests):
        recommended_tools.update(["markdownlint", "link-checker", "Vale"])

    tool_hints.update(recommended_tools)
    return (
        sorted(language_hints),
        sorted(manifests),
        sorted(docs_roots),
        sorted(tool_hints),
    )


def iso_today() -> str:
    return dt.date.today().isoformat()


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def extract_first(patterns: Iterable[re.Pattern[str]], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            if match.lastindex:
                return match.group(1).strip()
            return match.group(0).strip()
    return None


def find_line_number(text: str, needle: str) -> int | None:
    index = text.find(needle)
    if index < 0:
        return None
    return text.count("\n", 0, index) + 1


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, int | None, str]] = set()
    out: list[Finding] = []
    for finding in findings:
        key = (finding.category, finding.path, finding.line, finding.summary)
        if key in seen:
            continue
        seen.add(key)
        out.append(finding)
    return out


def scan_file(repo: Path, path: Path, text: str) -> list[Finding]:
    rel = path.relative_to(repo).as_posix()
    lang = language_for(path)
    findings: list[Finding] = []

    replacement = extract_first(REPLACEMENT_PATTERNS, text)
    removal_target = extract_first(REMOVAL_TARGET_PATTERNS, text)
    removal_date = parse_date(removal_target)
    deprecation_cue = extract_first(STRUCTURED_DEPRECATION_PATTERNS, text)
    has_explicit_deprecation = deprecation_cue is not None or removal_target is not None
    code_or_config = is_code_or_config_file(path)

    if has_explicit_deprecation:
        cue = deprecation_cue or removal_target
        findings.append(
            Finding(
                category="deprecated-surface",
                severity="medium",
                confidence="high" if deprecation_cue else "medium",
                path=rel,
                line=find_line_number(text, cue) if cue else None,
                language=lang,
                summary="Repository contains an explicitly marked deprecated surface that likely needs migration or deletion planning.",
                cue=cue,
                replacement=replacement,
                removal_target=removal_target,
                evidence=[f"matched cue: {cue}"] if cue else ["explicit removal-target metadata found"],
            )
        )

    path_suggests_shim = code_or_config and SHIM_PATH_PATTERN.search(rel) is not None
    shim_cue = extract_first(SHIM_TEXT_PATTERNS, text) if code_or_config else None
    if code_or_config and ((path_suggests_shim and shim_cue) or (shim_cue and has_explicit_deprecation)):
        evidence = []
        if path_suggests_shim:
            evidence.append(f"path suggests compatibility surface: {rel}")
        if shim_cue:
            evidence.append(f"matched cue: {shim_cue}")
        findings.append(
            Finding(
                category="compatibility-shim",
                severity="medium",
                confidence="medium" if path_suggests_shim else "low",
                path=rel,
                line=find_line_number(text, shim_cue) if shim_cue else None,
                language=lang,
                summary="File looks like a compatibility wrapper, alias, or shim rather than a real source of truth.",
                cue=shim_cue,
                replacement=replacement,
                removal_target=removal_target,
                evidence=evidence,
            )
        )
    elif path_suggests_shim and not has_explicit_deprecation:
        findings.append(
            Finding(
                category="cleanup-opportunity",
                severity="low",
                confidence="low",
                path=rel,
                line=None,
                language=lang,
                summary="Path suggests a legacy or compatibility surface; confirm replacement and live references before deleting.",
                cue=None,
                replacement=replacement,
                removal_target=removal_target,
                evidence=[f"path suggests compatibility surface: {rel}"],
            )
        )

    if removal_date and removal_date < dt.date.today():
        findings.append(
            Finding(
                category="expired-removal-target",
                severity="high",
                confidence="high",
                path=rel,
                line=find_line_number(text, removal_target) if removal_target else None,
                language=lang,
                summary="Deprecation marker indicates a removal target that is already in the past.",
                cue=None,
                replacement=replacement,
                removal_target=removal_target,
                evidence=[f"expired removal target: {removal_target}"],
            )
        )

    if has_explicit_deprecation and (not replacement or not removal_target):
        missing = []
        if not replacement:
            missing.append("replacement")
        if not removal_target:
            missing.append("removal target")
        findings.append(
            Finding(
                category="marker-gap",
                severity="medium",
                confidence="medium",
                path=rel,
                line=find_line_number(text, deprecation_cue) if deprecation_cue else None,
                language=lang,
                summary=f"Explicit deprecation marker exists but is missing: {', '.join(missing)}.",
                cue=deprecation_cue,
                replacement=replacement,
                removal_target=removal_target,
                evidence=["deprecation cue without complete machine-readable metadata"],
            )
        )

    if code_or_config:
        feature_flag_cue = extract_first(FEATURE_FLAG_PATTERNS, text)
        if feature_flag_cue:
            findings.append(
                Finding(
                    category="feature-flag-debt",
                    severity="medium",
                    confidence="medium",
                    path=rel,
                    line=find_line_number(text, feature_flag_cue),
                    language=lang,
                    summary="File contains feature-flag or fallback-path cues that may outlive the migration window.",
                    cue=feature_flag_cue,
                    replacement=None,
                    removal_target=removal_target,
                    evidence=[f"matched cue: {feature_flag_cue}"],
                )
            )

        dynamic_cue = extract_first(DYNAMIC_RISK_PATTERNS, text)
        if dynamic_cue:
            findings.append(
                Finding(
                    category="dynamic-entrypoint-risk",
                    severity="high",
                    confidence="medium",
                    path=rel,
                    line=find_line_number(text, dynamic_cue),
                    language=lang,
                    summary="Hidden references may exist because the file uses runtime indirection, reflection, or dynamic dispatch cues.",
                    cue=dynamic_cue,
                    replacement=None,
                    removal_target=None,
                    evidence=[f"matched cue: {dynamic_cue}"],
                )
            )

    return findings


def detect_evidence_gaps(repo: Path, manifests: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    has_test_dir = any((repo / name).exists() for name in ["tests", "test", "spec", "specs", "__tests__"])
    has_test_hint = any((repo / hint).exists() for hint in TEST_HINTS)
    has_ci = any((repo / hint).exists() for hint in CI_HINTS)

    if not has_test_dir and not has_test_hint:
        findings.append(
            Finding(
                category="evidence-gap",
                severity="high",
                confidence="high",
                path=".",
                line=None,
                language=None,
                summary="Repository does not show obvious test layout or test runner hints, which weakens deletion confidence.",
                cue=None,
                replacement=None,
                removal_target=None,
                evidence=["no tests/ or common test-runner manifest found"],
            )
        )
    if not has_ci:
        findings.append(
            Finding(
                category="evidence-gap",
                severity="medium",
                confidence="medium",
                path=".",
                line=None,
                language=None,
                summary="Repository does not show obvious CI configuration, so cleanup validation may rely on local discipline only.",
                cue=None,
                replacement=None,
                removal_target=None,
                evidence=["no common CI config found"],
            )
        )
    if not manifests:
        findings.append(
            Finding(
                category="scan-blocker",
                severity="medium",
                confidence="medium",
                path=".",
                line=None,
                language=None,
                summary="Repository exposes very few recognizable manifests; follow-up validation commands may need manual discovery.",
                cue=None,
                replacement=None,
                removal_target=None,
                evidence=["no known manifest files found"],
            )
        )
    return findings


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    out_path = Path(args.out).resolve()

    if not repo.exists() or not repo.is_dir():
        print(f"error: repo does not exist or is not a directory: {repo}")
        return 2

    languages, manifests, docs_roots, tool_hints = infer_repo_profile(repo)
    findings: list[Finding] = []

    for path in iter_files(repo, args.max_file_bytes):
        text = read_text(path)
        if text is None:
            continue
        findings.extend(scan_file(repo, path, text))

    findings.extend(detect_evidence_gaps(repo, manifests))
    findings = dedupe_findings(findings)

    counts = Counter(f.category for f in findings)
    summary = {
        "repo_root": repo.as_posix(),
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repo_profile": {
            "languages": languages,
            "manifests": manifests,
            "docs_roots": docs_roots,
            "tool_hints": tool_hints,
        },
        "counts": {
            "total": len(findings),
            "by_category": dict(sorted(counts.items())),
        },
        "findings": [f.to_dict() for f in findings],
        "notes": [
            "This scanner is heuristic. High-confidence deletion decisions still need validation and, for risky paths, rollout thinking.",
            f"today={iso_today()}",
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
