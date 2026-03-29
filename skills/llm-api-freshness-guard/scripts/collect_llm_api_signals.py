#!/usr/bin/env python3
"""Deterministic local signal collector for LLM API freshness work.

This script does not verify live docs. It identifies likely providers, wrappers, version
hints, model strings, base URLs, and suspicious surfaces that should be checked against
current docs with Context7.

It can also emit baseline artifacts so CI or higher-level orchestration can consume a
truthful "local-scan-only" result without pretending that live documentation was checked.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover - only for very old runtimes
    tomllib = None  # type: ignore[assignment]

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

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".go",
    ".java",
    ".kt",
    ".kts",
    ".rb",
    ".php",
    ".cs",
    ".swift",
    ".rs",
    ".scala",
    ".sh",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".txt",
    ".properties",
    ".lock",
    ".xml",
}

SPECIAL_FILENAMES = {
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
    ".env",
    ".env.example",
    ".env.local",
}

MAX_FILE_SIZE_BYTES = 1_000_000
MAX_SNIPPET_CHARS = 240


@dataclass(frozen=True)
class Pattern:
    label: str
    category: str
    weight: int
    regex: re.Pattern[str]
    provider: Optional[str] = None
    wrapper: Optional[str] = None


@dataclass(frozen=True)
class ProviderRegistry:
    providers: frozenset[str]
    wrappers: frozenset[str]
    package_hints: Dict[str, Dict[str, Optional[str]]]
    patterns: List[Pattern]
    model_patterns: Dict[str, re.Pattern[str]]
    url_patterns: Dict[str, re.Pattern[str]]


def compile_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


DEFAULT_PROVIDER_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "assets" / "provider-registry.json"


def load_provider_registry(path: Path) -> ProviderRegistry:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"provider registry file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"provider registry is not valid JSON: {path}: {exc}") from exc

    providers = frozenset(str(item) for item in raw.get("providers", []))
    wrappers = frozenset(str(item) for item in raw.get("wrappers", []))
    package_hints: Dict[str, Dict[str, Optional[str]]] = {}
    for name, hint in raw.get("package_hints", {}).items():
        if not isinstance(hint, dict):
            raise RuntimeError(f"package_hints[{name!r}] must be an object")
        package_hints[name.strip().lower()] = {
            "provider": hint.get("provider"),
            "wrapper": hint.get("wrapper"),
        }

    patterns: List[Pattern] = []
    for entry in raw.get("signal_patterns", []):
        if not isinstance(entry, dict):
            raise RuntimeError("signal_patterns entries must be objects")
        provider = entry.get("provider")
        wrapper = entry.get("wrapper")
        if provider is not None and provider not in providers:
            raise RuntimeError(f"unknown provider in signal_patterns: {provider!r}")
        if wrapper is not None and wrapper not in wrappers:
            raise RuntimeError(f"unknown wrapper in signal_patterns: {wrapper!r}")
        patterns.append(
            Pattern(
                label=str(entry["label"]),
                category=str(entry["category"]),
                weight=int(entry["weight"]),
                regex=compile_pattern(str(entry["regex"])),
                provider=provider,
                wrapper=wrapper,
            )
        )

    model_patterns = {
        str(provider): re.compile(str(pattern))
        for provider, pattern in raw.get("model_patterns", {}).items()
    }
    url_patterns = {
        str(provider): re.compile(str(pattern), re.IGNORECASE)
        for provider, pattern in raw.get("url_patterns", {}).items()
    }

    return ProviderRegistry(
        providers=providers,
        wrappers=wrappers,
        package_hints=package_hints,
        patterns=patterns,
        model_patterns=model_patterns,
        url_patterns=url_patterns,
    )


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def debug(msg: str) -> None:
    # Uncomment for debugging:
    # print(msg, file=sys.stderr)
    return


def is_text_candidate(path: Path) -> bool:
    if path.name in SPECIAL_FILENAMES:
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".ruff_cache")


def iter_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        for filename in filenames:
            path = Path(dirpath) / filename
            if not is_text_candidate(path):
                continue
            try:
                if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def trim_snippet(text: str) -> str:
    text = " ".join(text.strip().split())
    if len(text) <= MAX_SNIPPET_CHARS:
        return text
    return text[: MAX_SNIPPET_CHARS - 1] + "…"


def relative_to(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def detect_language(path: Path) -> Optional[str]:
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".go": "go",
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".swift": "swift",
        ".rs": "rust",
        ".scala": "scala",
        ".sh": "shell",
    }
    if path.name == "package.json":
        return "json"
    if path.name == "pyproject.toml":
        return "toml"
    return mapping.get(path.suffix.lower())


def add_unique(bucket: Dict[str, List[str]], key: str, value: str) -> None:
    if not value:
        return
    existing = bucket.setdefault(key, [])
    if value not in existing:
        existing.append(value)


def package_name_key(name: str) -> str:
    return name.strip().lower()


def extract_package_hints_from_package_json(path: Path, root: Path, provider_scores: Counter, wrapper_scores: Counter, version_hints: Dict[str, List[str]], evidence: List[dict], package_hints: Dict[str, Dict[str, Optional[str]]]) -> None:
    text = read_text(path)
    if not text:
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return

    sections = ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]
    for section in sections:
        deps = data.get(section, {})
        if not isinstance(deps, dict):
            continue
        for raw_name, raw_version in deps.items():
            name = package_name_key(raw_name)
            hint = package_hints.get(name)
            if not hint:
                continue
            version = str(raw_version)
            if hint["provider"]:
                provider_scores[hint["provider"]] += 4
                add_unique(version_hints, hint["provider"], f"{name}@{version}")
            if hint["wrapper"]:
                wrapper_scores[hint["wrapper"]] += 4
                add_unique(version_hints, hint["wrapper"], f"{name}@{version}")
            evidence.append(
                {
                    "path": relative_to(path, root),
                    "line": 1,
                    "snippet": trim_snippet(f"{section}: {name}: {version}"),
                    "kind": "manifest",
                    "label": f"package-json-{name}",
                    "provider": hint["provider"],
                    "wrapper": hint["wrapper"],
                    "category": "manifest",
                }
            )


def extract_package_hints_from_pyproject(path: Path, root: Path, provider_scores: Counter, wrapper_scores: Counter, version_hints: Dict[str, List[str]], evidence: List[dict], package_hints: Dict[str, Dict[str, Optional[str]]]) -> None:
    if tomllib is None:
        return
    text = read_text(path)
    if not text:
        return
    try:
        data = tomllib.loads(text)
    except Exception:
        return

    candidates: List[str] = []

    project = data.get("project", {})
    if isinstance(project, dict):
        deps = project.get("dependencies", [])
        if isinstance(deps, list):
            candidates.extend(str(dep) for dep in deps)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group_deps in optional.values():
                if isinstance(group_deps, list):
                    candidates.extend(str(dep) for dep in group_deps)

    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            poetry_deps = poetry.get("dependencies", {})
            if isinstance(poetry_deps, dict):
                for name, spec in poetry_deps.items():
                    if name == "python":
                        continue
                    candidates.append(f"{name}{spec if isinstance(spec, str) else ''}")
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_name, group_body in group.items():
                    if not isinstance(group_body, dict):
                        continue
                    deps = group_body.get("dependencies", {})
                    if isinstance(deps, dict):
                        for name, spec in deps.items():
                            candidates.append(f"{name}{spec if isinstance(spec, str) else ''}")

    for dep in candidates:
        dep = dep.strip()
        if not dep:
            continue
        m = re.match(r"([A-Za-z0-9_.\-@/]+)", dep)
        if not m:
            continue
        name = package_name_key(m.group(1))
        hint = package_hints.get(name)
        if not hint:
            continue
        version_text = dep[len(m.group(1)):].strip() or "unspecified"
        if hint["provider"]:
            provider_scores[hint["provider"]] += 4
            add_unique(version_hints, hint["provider"], f"{name}{version_text}")
        if hint["wrapper"]:
            wrapper_scores[hint["wrapper"]] += 4
            add_unique(version_hints, hint["wrapper"], f"{name}{version_text}")
        evidence.append(
            {
                "path": relative_to(path, root),
                "line": 1,
                "snippet": trim_snippet(dep),
                "kind": "manifest",
                "label": f"pyproject-{name}",
                "provider": hint["provider"],
                "wrapper": hint["wrapper"],
                "category": "manifest",
            }
        )


def extract_package_hints_from_requirements(path: Path, root: Path, provider_scores: Counter, wrapper_scores: Counter, version_hints: Dict[str, List[str]], evidence: List[dict], package_hints: Dict[str, Dict[str, Optional[str]]]) -> None:
    text = read_text(path)
    if not text:
        return
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        m = re.match(r"([A-Za-z0-9_.\-@/]+)", line)
        if not m:
            continue
        name = package_name_key(m.group(1))
        hint = package_hints.get(name)
        if not hint:
            continue
        version_text = line[len(m.group(1)):].strip() or "unspecified"
        if hint["provider"]:
            provider_scores[hint["provider"]] += 4
            add_unique(version_hints, hint["provider"], f"{name}{version_text}")
        if hint["wrapper"]:
            wrapper_scores[hint["wrapper"]] += 4
            add_unique(version_hints, hint["wrapper"], f"{name}{version_text}")
        evidence.append(
            {
                "path": relative_to(path, root),
                "line": lineno,
                "snippet": trim_snippet(line),
                "kind": "manifest",
                "label": f"requirements-{name}",
                "provider": hint["provider"],
                "wrapper": hint["wrapper"],
                "category": "manifest",
            }
        )


def extract_patterns_from_text(path: Path, root: Path, text: str, provider_scores: Counter, wrapper_scores: Counter, model_hints: Dict[str, List[str]], base_url_hints: Dict[str, List[str]], evidence: List[dict], suspicions: List[dict], language_counts: Counter, patterns: Sequence[Pattern], model_patterns: Dict[str, re.Pattern[str]], url_patterns: Dict[str, re.Pattern[str]]) -> None:
    rel = relative_to(path, root)
    language = detect_language(path)
    if language:
        language_counts[language] += 1

    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for pattern in patterns:
            if not pattern.regex.search(line):
                continue
            if pattern.provider:
                provider_scores[pattern.provider] += pattern.weight
            if pattern.wrapper:
                wrapper_scores[pattern.wrapper] += pattern.weight
            entry = {
                "path": rel,
                "line": lineno,
                "snippet": trim_snippet(line),
                "kind": "signal",
                "label": pattern.label,
                "provider": pattern.provider,
                "wrapper": pattern.wrapper,
                "category": pattern.category,
            }
            evidence.append(entry)
            if pattern.category in {"stale-pattern", "legacy-surface-suspect", "compatibility-layer"}:
                suspicions.append(entry)

        for provider, regex in model_patterns.items():
            for match in regex.finditer(line):
                model = match.group(0)
                add_unique(model_hints, provider, model)
                evidence.append(
                    {
                        "path": rel,
                        "line": lineno,
                        "snippet": trim_snippet(line),
                        "kind": "model",
                        "label": f"{provider}-model",
                        "provider": provider,
                        "wrapper": None,
                        "category": "model",
                    }
                )
                if provider in provider_scores:
                    provider_scores[provider] += 2

        for provider, regex in url_patterns.items():
            for match in regex.finditer(line):
                add_unique(base_url_hints, provider, match.group(0))
                if provider in provider_scores:
                    provider_scores[provider] += 4
                evidence.append(
                    {
                        "path": rel,
                        "line": lineno,
                        "snippet": trim_snippet(line),
                        "kind": "base_url",
                        "label": f"{provider}-base-url",
                        "provider": provider,
                        "wrapper": None,
                        "category": "base-url",
                    }
                )


def build_provider_file_map(evidence: Sequence[dict]) -> Dict[str, List[str]]:
    files: Dict[str, List[str]] = defaultdict(list)
    for item in evidence:
        provider = item.get("provider")
        path = item.get("path")
        if provider and path and path not in files[provider]:
            files[provider].append(path)
    return dict(files)


def group_suspicions(suspicions: Sequence[dict]) -> List[dict]:
    grouped: Dict[tuple, dict] = {}
    for item in suspicions:
        key = (item.get("provider") or "unknown", item.get("label") or "unknown")
        group = grouped.setdefault(
            key,
            {
                "provider": item.get("provider") or "unknown",
                "label": item.get("label") or "unknown",
                "category": item.get("category") or "unknown",
                "evidence": [],
                "files": [],
            },
        )
        if len(group["evidence"]) < 6:
            group["evidence"].append(
                {
                    "path": item["path"],
                    "line": item["line"],
                    "snippet": item["snippet"],
                }
            )
        if item["path"] not in group["files"]:
            group["files"].append(item["path"])
    return sorted(grouped.values(), key=lambda g: (g["provider"], g["label"]))


def select_detected(scores: Counter, minimum_score: int) -> List[str]:
    items = [name for name, score in scores.items() if score >= minimum_score]
    return sorted(items)


def make_docs_unverified_finding(provider: str, files: Sequence[str], suspicions: Sequence[dict], version_hints: Dict[str, List[str]], model_hints: Dict[str, List[str]]) -> dict:
    evidence = []
    seen = set()
    for suspicion in suspicions:
        if suspicion["provider"] != provider:
            continue
        for item in suspicion["evidence"]:
            key = (item["path"], item["line"], item["snippet"])
            if key in seen:
                continue
            seen.add(key)
            evidence.append(item)
            if len(evidence) >= 6:
                break
        if len(evidence) >= 6:
            break

    versions = ", ".join(version_hints.get(provider, [])[:3]) or "no version hint found"
    models = ", ".join(model_hints.get(provider, [])[:4]) or "no model hint found"
    return {
        "id": f"docs-unverified-{provider}",
        "provider": provider,
        "kind": "docs-unverified",
        "severity": "medium",
        "confidence": "low",
        "status": "present",
        "scope": list(files)[:10],
        "title": f"{provider} surface detected, but current docs were not verified",
        "stale_usage": f"Local signals indicate {provider} usage, but this run did not check current official docs. Version hints: {versions}. Model hints: {models}.",
        "current_expectation": f"Resolve the current {provider} docs with Context7 before labeling any surface stale, deprecated, or removed.",
        "evidence": evidence,
        "recommended_change_shape": f"Run a Context7-backed verification pass for {provider}: official SDK docs first, then platform or gateway docs as needed.",
        "docs_verified": False,
        "autofix_allowed": False,
        "notes": "This is a truthful placeholder finding for local-scan-only mode.",
    }


def suspicion_kind_from_label(label: str) -> str:
    label = label.lower()
    if "model" in label:
        return "model-stale"
    if "function" in label or "tools" in label:
        return "tool-calling-drift"
    if "stream" in label:
        return "streaming-drift"
    if "complete" in label or "chatcompletion" in label or "responses" in label:
        return "endpoint-stale"
    if "api-version" in label or "base-url" in label or "azure" in label or "openrouter" in label or "bedrock" in label:
        return "compat-layer-drift"
    return "local-suspicion"


def suspicion_severity_from_category(category: str) -> str:
    if category == "stale-pattern":
        return "high"
    if category == "compatibility-layer":
        return "medium"
    return "medium"


def make_local_suspicion_finding(group: dict) -> dict:
    provider = group["provider"]
    label = group["label"]
    title = f"Possible stale surface: {label}"
    if provider == "unknown":
        title = f"Possible stale surface with unclear provider: {label}"
    return {
        "id": f"local-suspicion-{provider}-{label}",
        "provider": provider,
        "kind": suspicion_kind_from_label(label),
        "severity": suspicion_severity_from_category(group["category"]),
        "confidence": "low",
        "status": "possible",
        "scope": group["files"][:10],
        "title": title,
        "stale_usage": f"Local scan found a suspicious pattern (`{label}`) that often deserves a current-doc check.",
        "current_expectation": "Verify the current official docs before deciding whether this is removed, deprecated, or still valid.",
        "evidence": group["evidence"],
        "recommended_change_shape": "Use Context7 to verify the exact current surface, then normalize only the affected call sites.",
        "docs_verified": False,
        "autofix_allowed": False,
        "notes": "This is intentionally low-confidence because the local collector does not verify live docs.",
    }


def make_provider_ambiguous_finding(wrapper_scores: Counter, evidence: Sequence[dict]) -> dict:
    sample_evidence = []
    for item in evidence:
        if item.get("wrapper"):
            sample_evidence.append(
                {
                    "path": item["path"],
                    "line": item["line"],
                    "snippet": item["snippet"],
                }
            )
        if len(sample_evidence) >= 6:
            break
    wrappers = ", ".join(sorted(name for name, score in wrapper_scores.items() if score > 0)) or "no clear wrapper"
    return {
        "id": "provider-ambiguous-001",
        "provider": "unknown",
        "kind": "provider-ambiguous",
        "severity": "medium",
        "confidence": "low",
        "status": "present",
        "scope": [],
        "title": "The underlying LLM provider could not be resolved with high confidence",
        "stale_usage": f"Local evidence points to wrappers or indirection ({wrappers}), but not to one clear active provider surface.",
        "current_expectation": "Identify the real runtime provider or gateway before calling anything stale. If the integration is outside the built-in registry, extend the registry first.",
        "evidence": sample_evidence,
        "recommended_change_shape": "Resolve runtime wiring from manifests, base URLs, env handling, or deployment config, extend the provider registry if needed, then run Context7 verification.",
        "docs_verified": False,
        "autofix_allowed": False,
        "notes": "Do not guess the provider from model vibes alone.",
    }


def build_priorities(providers: Sequence[str], wrappers: Sequence[str], ambiguity: bool) -> dict:
    now: List[str] = []
    nxt: List[str] = []
    later: List[str] = []

    if ambiguity:
        now.append("Resolve the actual runtime provider surface before making any freshness claims; extend the provider registry first if the integration is outside the built-in set.")
    if providers:
        now.extend(
            [
                f"Run Context7 verification for {provider} on the exact SDK / gateway surface detected in code."
                for provider in providers
            ]
        )
    if wrappers:
        nxt.append(
            "Check wrapper-owned semantics separately from provider-owned semantics; do not assume wrappers preserve provider parity."
        )
    nxt.append("Verify tool calling, structured output, streaming, and model lifecycle before patching call sites.")
    later.extend(
        [
            "Add a repeatable freshness audit to CI or review flows.",
            "Centralize provider adapters so future migrations are smaller and less error-prone.",
        ]
    )
    return {
        "now": now[:6],
        "next": nxt[:6],
        "later": later[:6],
    }


def render_report(summary: dict, grouped_suspicions: Sequence[dict]) -> str:
    providers = ", ".join(summary["repo_profile"]["providers_detected"]) or "none"
    wrappers = ", ".join(summary["repo_profile"]["wrappers_detected"]) or "none"
    version_lines = []
    for key, values in summary["repo_profile"]["version_hints"].items():
        if values:
            version_lines.append(f"- {key}: {', '.join(values[:5])}")
    if not version_lines:
        version_lines.append("- no strong version hints found")

    findings = summary["findings"]
    lines = [
        "# LLM API Freshness Audit",
        "",
        "## Verdict",
        "- Overall verdict: local signal scan completed; live freshness verdict not available yet.",
        "- Verification mode: `local-scan-only`",
        f"- Providers in scope: {providers}",
        f"- Wrappers / gateways in scope: {wrappers}",
        "- Highest-risk surface: anything listed below under suspicious patterns still needs current-doc verification.",
        "",
        "## Executive diagnosis",
        "This is not a real freshness verdict yet. It is a deterministic local scan that found likely provider surfaces, wrappers, and suspicious patterns, but it did not check current docs. Treat it as triage, not truth.",
        "",
        "## 现在最该做的事",
    ]
    for item in summary["priorities"]["now"] or ["Run a Context7-backed verification pass."]:
        lines.append(f"1. {item}")

    lines.extend(
        [
            "",
            "## Version hints",
            *version_lines,
            "",
            "## Suspicious surfaces to verify",
        ]
    )
    if grouped_suspicions:
        for group in grouped_suspicions[:20]:
            files = ", ".join(group["files"][:4]) or "no files listed"
            lines.append(f"- `{group['provider']}` / `{group['label']}` -> {files}")
    else:
        lines.append("- no obvious suspicious patterns were detected locally")

    lines.extend(
        [
            "",
            "## Main findings",
        ]
    )
    for finding in findings[:20]:
        lines.extend(
            [
                "",
                f"### {finding['id']} {finding['title']}",
                f"- Provider: {finding['provider']}",
                f"- Kind: {finding['kind']}",
                f"- Severity: {finding['severity']}",
                f"- Confidence: {finding['confidence']}",
                f"- Status: {finding['status']}",
                f"- Scope: {', '.join(finding['scope'][:8]) or 'n/a'}",
                f"- 是什么：{finding['stale_usage']}",
                f"- 为什么重要：{finding['current_expectation']}",
                f"- 建议做什么：{finding['recommended_change_shape']}",
            ]
        )
        if finding["evidence"]:
            lines.append("- 代码证据：")
            for ev in finding["evidence"][:4]:
                lines.append(f"  - `{ev['path']}:{ev['line']}` {ev['snippet']}")

    lines.extend(
        [
            "",
            "## Blockers and ambiguity",
            "- Live docs were not verified in this run.",
            "- Wrapper or gateway usage may hide the true provider semantics.",
            "- Local pattern matches can identify migration candidates, but they cannot prove current deprecation state.",
            "",
            "## Prioritized plan",
            "",
            "### 现在",
        ]
    )
    for item in summary["priorities"]["now"]:
        lines.append(f"- {item}")
    lines.extend(["", "### 下一步"])
    for item in summary["priorities"]["next"]:
        lines.append(f"- {item}")
    lines.extend(["", "### 之后"])
    for item in summary["priorities"]["later"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Skipped checks",
            "- Context7-backed current-doc verification was not executed by this local wrapper.",
            "- No provider-specific migration recommendation is final until the live docs are checked.",
            "",
        ]
    )
    return "\n".join(lines)


def render_agent_brief(summary: dict, grouped_suspicions: Sequence[dict]) -> str:
    providers = summary["repo_profile"]["providers_detected"]
    wrappers = summary["repo_profile"]["wrappers_detected"]
    lines = [
        "# LLM API Freshness Agent Brief",
        "",
        "## Execution mode",
        "- `report-only`",
        "",
        "## Scope summary",
        f"- Providers: {', '.join(providers) or 'none'}",
        f"- Wrappers / gateways: {', '.join(wrappers) or 'none'}",
        f"- Verification mode: {summary['mode']}",
        f"- Files scanned: {summary['repo_profile']['files_scanned']}",
        "- Current docs checked: none",
        "",
        "## Findings queue",
    ]
    for finding in summary["findings"][:20]:
        evidence_summary = "; ".join(
            f"{ev['path']}:{ev['line']}" for ev in finding["evidence"][:4]
        ) or "n/a"
        lines.extend(
            [
                "",
                f"### {finding['id']} {finding['title']}",
                f"- provider: {finding['provider']}",
                f"- kind: {finding['kind']}",
                f"- severity: {finding['severity']}",
                f"- confidence: {finding['confidence']}",
                f"- status: {finding['status']}",
                f"- scope: {', '.join(finding['scope'][:8]) or 'n/a'}",
                f"- stale_usage: {finding['stale_usage']}",
                f"- current_expectation: {finding['current_expectation']}",
                f"- evidence_summary: {evidence_summary}",
                f"- decision: {finding['recommended_change_shape']}",
                "- recommended_change_shape: verify current docs first; do not patch blindly",
                "- validation_checks: compare provider docs, wrapper docs, and runtime config before changing code",
                f"- docs_verified: {str(finding['docs_verified']).lower()}",
                f"- autofix_allowed: {str(finding['autofix_allowed']).lower()}",
                f"- notes: {finding['notes']}",
            ]
        )

    if grouped_suspicions:
        lines.extend(["", "## Query targets"])
        for group in grouped_suspicions[:20]:
            lines.append(
                f"- {group['provider']} / {group['label']}: verify exact current surface via Context7 before editing {', '.join(group['files'][:3])}"
            )

    lines.extend(
        [
            "",
            "## Output rules for the coding agent",
            "- Keep patches small and reversible first.",
            "- Do not rewrite unrelated provider code.",
            "- Treat this local scan as triage only.",
            "- Convert suspicious patterns into real findings only after live-doc verification.",
            "",
        ]
    )
    return "\n".join(lines)


def build_summary(root: Path, files_scanned: int, language_counts: Counter, provider_scores: Counter, wrapper_scores: Counter, version_hints: Dict[str, List[str]], model_hints: Dict[str, List[str]], base_url_hints: Dict[str, List[str]], evidence: List[dict], grouped_suspicions: Sequence[dict]) -> dict:
    detected_providers = select_detected(provider_scores, minimum_score=4)
    detected_wrappers = select_detected(wrapper_scores, minimum_score=4)
    provider_files = build_provider_file_map(evidence)

    findings: List[dict] = []
    if not detected_providers:
        findings.append(make_provider_ambiguous_finding(wrapper_scores, evidence))

    for provider in detected_providers:
        findings.append(
            make_docs_unverified_finding(
                provider=provider,
                files=provider_files.get(provider, []),
                suspicions=grouped_suspicions,
                version_hints=version_hints,
                model_hints=model_hints,
            )
        )

    for group in grouped_suspicions:
        findings.append(make_local_suspicion_finding(group))

    summary = {
        "skill": "llm-api-freshness-guard",
        "version": "1.0.0",
        "generated_at": utc_now(),
        "mode": "local-scan-only",
        "repo_profile": {
            "repo_root": str(root.resolve()),
            "files_scanned": files_scanned,
            "languages": [name for name, _count in language_counts.most_common()],
            "providers_detected": detected_providers,
            "provider_scores": dict(sorted(provider_scores.items())),
            "wrappers_detected": detected_wrappers,
            "version_hints": dict(sorted(version_hints.items())),
            "model_hints": dict(sorted(model_hints.items())),
            "base_url_hints": dict(sorted(base_url_hints.items())),
        },
        "doc_verification": [],
        "findings": findings,
        "priorities": build_priorities(
            providers=detected_providers,
            wrappers=detected_wrappers,
            ambiguity=not bool(detected_providers),
        ),
        "scan_limitations": [
            "This summary was generated by the deterministic local signal collector only.",
            "Current provider docs were not verified in this run.",
            "Local suspicious patterns are migration candidates, not final freshness verdicts.",
        ],
    }
    return summary


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def collect(root: Path, registry: ProviderRegistry) -> dict:
    provider_scores: Counter = Counter()
    wrapper_scores: Counter = Counter()
    version_hints: Dict[str, List[str]] = {}
    model_hints: Dict[str, List[str]] = {}
    base_url_hints: Dict[str, List[str]] = {}
    evidence: List[dict] = []
    suspicions: List[dict] = []
    language_counts: Counter = Counter()
    files_scanned = 0

    for path in iter_files(root):
        files_scanned += 1
        if path.name == "package.json":
            extract_package_hints_from_package_json(path, root, provider_scores, wrapper_scores, version_hints, evidence, registry.package_hints)
        elif path.name == "pyproject.toml":
            extract_package_hints_from_pyproject(path, root, provider_scores, wrapper_scores, version_hints, evidence, registry.package_hints)
        elif path.name.startswith("requirements") and path.suffix == ".txt":
            extract_package_hints_from_requirements(path, root, provider_scores, wrapper_scores, version_hints, evidence, registry.package_hints)

        text = read_text(path)
        if text is None:
            continue
        extract_patterns_from_text(
            path=path,
            root=root,
            text=text,
            provider_scores=provider_scores,
            wrapper_scores=wrapper_scores,
            model_hints=model_hints,
            base_url_hints=base_url_hints,
            evidence=evidence,
            suspicions=suspicions,
            language_counts=language_counts,
            patterns=registry.patterns,
            model_patterns=registry.model_patterns,
            url_patterns=registry.url_patterns,
        )

    grouped_suspicions = group_suspicions(suspicions)
    summary = build_summary(
        root=root,
        files_scanned=files_scanned,
        language_counts=language_counts,
        provider_scores=provider_scores,
        wrapper_scores=wrapper_scores,
        version_hints=version_hints,
        model_hints=model_hints,
        base_url_hints=base_url_hints,
        evidence=evidence,
        grouped_suspicions=grouped_suspicions,
    )
    signals = {
        "generated_at": utc_now(),
        "repo_root": str(root.resolve()),
        "files_scanned": files_scanned,
        "languages": [name for name, _count in language_counts.most_common()],
        "provider_scores": dict(sorted(provider_scores.items())),
        "wrapper_scores": dict(sorted(wrapper_scores.items())),
        "version_hints": dict(sorted(version_hints.items())),
        "model_hints": dict(sorted(model_hints.items())),
        "base_url_hints": dict(sorted(base_url_hints.items())),
        "signals": evidence[:1500],
        "suspicious_groups": grouped_suspicions,
    }
    return {
        "signals": signals,
        "summary": summary,
        "report": render_report(summary, grouped_suspicions),
        "agent_brief": render_agent_brief(summary, grouped_suspicions),
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect local LLM API signals for freshness audits.")
    parser.add_argument("repo", help="Path to the repository or directory to scan.")
    parser.add_argument("--provider-registry", help="Optional path to a provider registry JSON override.")
    parser.add_argument("--json-out", help="Write the raw signals JSON to this path.")
    parser.add_argument("--summary-out", help="Write the local-scan-only summary JSON to this path.")
    parser.add_argument("--report-out", help="Write a baseline human report to this path.")
    parser.add_argument("--agent-brief-out", help="Write a baseline agent brief to this path.")
    parser.add_argument("--stdout", choices=["signals", "summary"], default="signals", help="What to print to stdout when no output path is given.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = Path(args.repo).expanduser().resolve()
    if not root.exists():
        print(f"error: path does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"error: path is not a directory: {root}", file=sys.stderr)
        return 2

    registry_path = Path(args.provider_registry).expanduser().resolve() if args.provider_registry else DEFAULT_PROVIDER_REGISTRY_PATH
    try:
        registry = load_provider_registry(registry_path)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = collect(root, registry)

    if args.json_out:
        write_json(Path(args.json_out), result["signals"])
    if args.summary_out:
        write_json(Path(args.summary_out), result["summary"])
    if args.report_out:
        write_text(Path(args.report_out), result["report"])
    if args.agent_brief_out:
        write_text(Path(args.agent_brief_out), result["agent_brief"])

    if not any([args.json_out, args.summary_out, args.report_out, args.agent_brief_out]):
        payload = result["signals"] if args.stdout == "signals" else result["summary"]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
