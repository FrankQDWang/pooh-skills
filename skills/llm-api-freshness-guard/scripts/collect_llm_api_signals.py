#!/usr/bin/env python3
"""Collect local LLM API surface evidence for llm-api-freshness-guard.

This script is the deterministic triage layer only. It extracts Python / TypeScript
surface evidence, builds surface candidates, and writes triage artifacts. It does not
claim a verified freshness verdict, because current-doc verification belongs to the
agent-first Context7 flow.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional, Sequence

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from llm_api_freshness_artifacts import render_agent_brief
from llm_api_freshness_artifacts import render_report

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
    ".pooh-runtime",
}
TEXT_EXTENSIONS = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
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
    ".md",
    ".mdx",
    ".rst",
}
CODE_EXTENSIONS = {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".txt"}
MAX_FILE_SIZE_BYTES = 1_000_000
MAX_SIGNAL_OUTPUT = 1500
MAX_SURFACE_EVIDENCE = 8
VERSION = "2.0.0"
ALLOWED_FAMILIES = {
    "openai-compatible",
    "anthropic-messages",
    "google-genai",
    "bedrock-hosted",
    "generic-wrapper",
    "custom-http-llm",
    "unknown",
}
ALLOWED_RESOLUTION_LEVELS = {
    "provider-resolved",
    "family-resolved",
    "wrapper-resolved",
    "ambiguous",
}
PROVIDER_TO_FAMILY = {
    "openai": "openai-compatible",
    "azure-openai": "openai-compatible",
    "openrouter": "openai-compatible",
    "anthropic": "anthropic-messages",
    "gemini": "google-genai",
    "google-genai": "google-genai",
    "bedrock": "bedrock-hosted",
}
PACKAGE_MANAGER_FILES = {
    "package.json": "node",
    "pnpm-lock.yaml": "pnpm",
    "package-lock.json": "npm",
    "yarn.lock": "yarn",
    "pyproject.toml": "python",
    "uv.lock": "uv",
    "requirements.txt": "python",
    "requirements-dev.txt": "python",
    "requirements-test.txt": "python",
}
PROVIDER_PATTERNS = [
    {
        "label": "openai-sdk-import",
        "regex": re.compile(r"\bfrom\s+openai\s+import\b|\bimport\s+openai\b|\bOpenAI\s*\(", re.IGNORECASE),
        "provider": "openai",
        "family": "openai-compatible",
        "strength": "strong",
        "kind": "provider-sdk",
        "sdk": "openai",
    },
    {
        "label": "anthropic-sdk-import",
        "regex": re.compile(r"@anthropic-ai/sdk|\bfrom\s+anthropic\s+import\b|\bimport\s+anthropic\b|\bAnthropic\s*\(", re.IGNORECASE),
        "provider": "anthropic",
        "family": "anthropic-messages",
        "strength": "strong",
        "kind": "provider-sdk",
        "sdk": "@anthropic-ai/sdk",
    },
    {
        "label": "google-genai-import",
        "regex": re.compile(r"@google/genai|google-generativeai|google\.genai|genai\.Client|GoogleGenAI", re.IGNORECASE),
        "provider": "gemini",
        "family": "google-genai",
        "strength": "strong",
        "kind": "provider-sdk",
        "sdk": "@google/genai",
    },
    {
        "label": "bedrock-runtime",
        "regex": re.compile(r"bedrock-runtime|boto3\.client\(\s*['\"]bedrock-runtime['\"]|invoke_model|converse\(", re.IGNORECASE),
        "provider": "bedrock",
        "family": "bedrock-hosted",
        "strength": "strong",
        "kind": "provider-sdk",
        "sdk": "bedrock-runtime",
    },
    {
        "label": "openrouter-host",
        "regex": re.compile(r"openrouter\.ai", re.IGNORECASE),
        "provider": "openrouter",
        "family": "openai-compatible",
        "strength": "strong",
        "kind": "gateway-host",
        "sdk": "openrouter",
    },
    {
        "label": "azure-openai-host",
        "regex": re.compile(r"openai\.azure\.com|AZURE_OPENAI_(?:ENDPOINT|API_KEY)", re.IGNORECASE),
        "provider": "azure-openai",
        "family": "openai-compatible",
        "strength": "strong",
        "kind": "gateway-host",
        "sdk": "azure-openai",
    },
]
WRAPPER_PATTERNS = [
    {
        "label": "litellm-import",
        "regex": re.compile(r"\blitellm\b", re.IGNORECASE),
        "wrapper": "litellm",
        "family": "generic-wrapper",
        "strength": "medium",
        "kind": "wrapper-sdk",
        "sdk": "litellm",
    },
    {
        "label": "langchain-openai",
        "regex": re.compile(r"langchain[-_/]openai|ChatOpenAI|OpenAIEmbeddings", re.IGNORECASE),
        "wrapper": "langchain",
        "provider": "openai",
        "family": "openai-compatible",
        "strength": "strong",
        "kind": "wrapper-sdk",
        "sdk": "langchain-openai",
    },
    {
        "label": "langchain-anthropic",
        "regex": re.compile(r"langchain[-_/]anthropic|ChatAnthropic", re.IGNORECASE),
        "wrapper": "langchain",
        "provider": "anthropic",
        "family": "anthropic-messages",
        "strength": "strong",
        "kind": "wrapper-sdk",
        "sdk": "langchain-anthropic",
    },
    {
        "label": "langchain-google",
        "regex": re.compile(r"langchain[-_/]google-genai|ChatGoogleGenerativeAI", re.IGNORECASE),
        "wrapper": "langchain",
        "provider": "gemini",
        "family": "google-genai",
        "strength": "strong",
        "kind": "wrapper-sdk",
        "sdk": "langchain-google-genai",
    },
    {
        "label": "vercel-ai-openai",
        "regex": re.compile(r"@ai-sdk/openai|createOpenAI", re.IGNORECASE),
        "wrapper": "vercel-ai-sdk",
        "provider": "openai",
        "family": "openai-compatible",
        "strength": "strong",
        "kind": "wrapper-sdk",
        "sdk": "@ai-sdk/openai",
    },
    {
        "label": "vercel-ai-anthropic",
        "regex": re.compile(r"@ai-sdk/anthropic|createAnthropic", re.IGNORECASE),
        "wrapper": "vercel-ai-sdk",
        "provider": "anthropic",
        "family": "anthropic-messages",
        "strength": "strong",
        "kind": "wrapper-sdk",
        "sdk": "@ai-sdk/anthropic",
    },
    {
        "label": "vercel-ai-google",
        "regex": re.compile(r"@ai-sdk/google|createGoogleGenerativeAI", re.IGNORECASE),
        "wrapper": "vercel-ai-sdk",
        "provider": "gemini",
        "family": "google-genai",
        "strength": "strong",
        "kind": "wrapper-sdk",
        "sdk": "@ai-sdk/google",
    },
    {
        "label": "pydantic-ai",
        "regex": re.compile(r"\bpydantic_ai\b|\bpydantic-ai\b|Agent\(", re.IGNORECASE),
        "wrapper": "pydantic-ai",
        "family": "generic-wrapper",
        "strength": "medium",
        "kind": "wrapper-sdk",
        "sdk": "pydantic-ai",
    },
    {
        "label": "instructor",
        "regex": re.compile(r"\binstructor\b|from_openai|from_anthropic", re.IGNORECASE),
        "wrapper": "instructor",
        "family": "generic-wrapper",
        "strength": "medium",
        "kind": "wrapper-sdk",
        "sdk": "instructor",
    },
]
FAMILY_PATTERNS = [
    {
        "label": "openai-compatible-path",
        "regex": re.compile(r"/v1/(chat/completions|responses)\b|chat\.completions\.create|responses\.create", re.IGNORECASE),
        "family": "openai-compatible",
        "strength": "medium",
        "kind": "family-surface",
        "sdk": "openai-compatible-http",
    },
    {
        "label": "anthropic-messages-path",
        "regex": re.compile(r"/v1/messages\b|messages\.create|anthropic-version", re.IGNORECASE),
        "family": "anthropic-messages",
        "strength": "medium",
        "kind": "family-surface",
        "sdk": "anthropic-messages-http",
    },
    {
        "label": "google-genai-surface",
        "regex": re.compile(r"generateContent|models\.generate_content|models\.generateContent|contents\s*=", re.IGNORECASE),
        "family": "google-genai",
        "strength": "medium",
        "kind": "family-surface",
        "sdk": "google-genai-http",
    },
    {
        "label": "custom-http-llm",
        "regex": re.compile(r"base_url|api_base|llm[_-]?gateway|model_router|gateway_url", re.IGNORECASE),
        "family": "custom-http-llm",
        "strength": "weak",
        "kind": "custom-surface",
        "sdk": "custom-http-llm",
    },
]
LEGACY_PATTERNS = [
    {
        "label": "openai-chatcompletion-legacy",
        "regex": re.compile(r"\bopenai\.ChatCompletion\.create\s*\(|\bChatCompletion\.create\s*\(", re.IGNORECASE),
        "family": "openai-compatible",
        "provider": "openai",
        "kind": "legacy-suspicion",
        "suggestion": "Verify migration pressure from legacy ChatCompletion calls to the current OpenAI SDK surface.",
    },
    {
        "label": "openai-completion-legacy",
        "regex": re.compile(r"\bopenai\.Completion\.create\s*\(|\bCompletion\.create\s*\(", re.IGNORECASE),
        "family": "openai-compatible",
        "provider": "openai",
        "kind": "legacy-suspicion",
        "suggestion": "Verify whether completion-style calls still match the current OpenAI surface in this codebase.",
    },
    {
        "label": "anthropic-completions-legacy",
        "regex": re.compile(r"\bcompletions\.create\s*\(|/v1/complete\b", re.IGNORECASE),
        "family": "anthropic-messages",
        "provider": "anthropic",
        "kind": "legacy-suspicion",
        "suggestion": "Verify whether this Anthropicsurface still depends on completions-era APIs instead of Messages.",
    },
    {
        "label": "google-generativeai-legacy",
        "regex": re.compile(r"google\.generativeai|GenerativeModel\s*\(", re.IGNORECASE),
        "family": "google-genai",
        "provider": "gemini",
        "kind": "legacy-suspicion",
        "suggestion": "Verify whether the repo still depends on the older google-generativeai package or migration shims.",
    },
]
MODEL_HINTS = [
    ("openai-compatible", re.compile(r"\bgpt-[a-z0-9\-]+\b", re.IGNORECASE)),
    ("anthropic-messages", re.compile(r"\bclaude-[a-z0-9\-]+\b", re.IGNORECASE)),
    ("google-genai", re.compile(r"\bgemini-[a-z0-9\-.]+\b", re.IGNORECASE)),
]
HOST_HINTS = [
    ("openai-compatible", "openai", re.compile(r"api\.openai\.com", re.IGNORECASE)),
    ("anthropic-messages", "anthropic", re.compile(r"api\.anthropic\.com", re.IGNORECASE)),
    ("google-genai", "gemini", re.compile(r"generativelanguage\.googleapis\.com|googleapis\.com/.+generateContent", re.IGNORECASE)),
    ("openai-compatible", "openrouter", re.compile(r"openrouter\.ai", re.IGNORECASE)),
    ("openai-compatible", "azure-openai", re.compile(r"openai\.azure\.com", re.IGNORECASE)),
]
PY_COMMENT_RE = re.compile(r"^\s*#")
TS_COMMENT_RE = re.compile(r"^\s*(//|/\*|\*)")
ENV_VALUE_RE = re.compile(r"(OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY|AZURE_OPENAI_(?:ENDPOINT|API_KEY)|OPENROUTER_API_KEY)")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect local LLM API surface evidence for freshness triage.")
    parser.add_argument("repo", help="Path to the repository or directory to scan.")
    parser.add_argument("--provider-hints", help="Optional path to a provider hints JSON override.")
    parser.add_argument("--json-out", help="Write the evidence bundle to this path.")
    parser.add_argument("--summary-out", help="Write the triage summary JSON to this path.")
    parser.add_argument("--report-out", help="Write the triage report to this path.")
    parser.add_argument("--agent-brief-out", help="Write the triage agent brief to this path.")
    parser.add_argument("--stdout", choices=["signals", "summary"], default="signals")
    return parser.parse_args(argv)


def load_provider_hints(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"provider hints must be a JSON object: {path}")
    raw.setdefault("package_aliases", {})
    raw.setdefault("query_seeds", {})
    raw.setdefault("host_hints", {})
    return raw


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS


def is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in PACKAGE_MANAGER_FILES


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [item for item in dirnames if not should_skip_dir(item)]
        for filename in filenames:
            path = Path(dirpath) / filename
            if not is_text_candidate(path):
                continue
            try:
                if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue
            files.append(path)
    return files


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def relative_to(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def detect_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".py", ".pyi"}:
        return "python"
    if suffix in {".ts", ".tsx"}:
        return "typescript"
    if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
        return "javascript"
    return "unknown"


def package_name_key(name: str) -> str:
    return name.strip().lower()


def trim_snippet(text: str) -> str:
    return " ".join(text.strip().split())[:240]


def is_doc_or_comment(path: Path, line: str) -> bool:
    suffix = path.suffix.lower()
    if suffix in DOC_EXTENSIONS:
        return True
    stripped = line.strip()
    if suffix in {".py", ".pyi"}:
        return bool(PY_COMMENT_RE.match(stripped))
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        return bool(TS_COMMENT_RE.match(stripped))
    return False


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def evidence_item(
    *,
    root: Path,
    path: Path,
    line_no: int,
    snippet: str,
    label: str,
    kind: str,
    strength: str,
    source: str,
    provider: Optional[str] = None,
    wrapper: Optional[str] = None,
    surface_family: Optional[str] = None,
    sdk: Optional[str] = None,
    version_hint: Optional[str] = None,
    model_hint: Optional[str] = None,
    base_url_hint: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "path": relative_to(path, root),
        "line": line_no,
        "snippet": trim_snippet(snippet),
        "label": label,
        "kind": kind,
        "strength": strength,
        "source": source,
        "language": detect_language(path),
        "provider": provider,
        "wrapper": wrapper,
        "surface_family": surface_family or provider_to_family(provider) or "unknown",
        "sdk": sdk,
        "version_hint": version_hint,
        "model_hint": model_hint,
        "base_url_hint": base_url_hint,
    }


def provider_to_family(provider: Optional[str]) -> Optional[str]:
    if not provider:
        return None
    return PROVIDER_TO_FAMILY.get(provider)


def load_manifest_aliases(hints: dict[str, Any]) -> dict[str, dict[str, Any]]:
    aliases = hints.get("package_aliases") or {}
    normalized: dict[str, dict[str, Any]] = {}
    for name, payload in aliases.items():
        if not isinstance(payload, dict):
            continue
        normalized[package_name_key(str(name))] = {
            "provider": payload.get("provider"),
            "wrapper": payload.get("wrapper"),
            "surface_family": payload.get("surface_family") or provider_to_family(payload.get("provider")) or "generic-wrapper",
            "sdk": payload.get("sdk") or str(name),
        }
    return normalized


def extract_package_hints_from_package_json(
    path: Path,
    root: Path,
    aliases: dict[str, dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> None:
    text = read_text(path)
    if not text:
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return

    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps = data.get(section, {})
        if not isinstance(deps, dict):
            continue
        for raw_name, raw_version in deps.items():
            payload = aliases.get(package_name_key(raw_name))
            if not payload:
                continue
            evidence.append(
                evidence_item(
                    root=root,
                    path=path,
                    line_no=1,
                    snippet=f"{section}: {raw_name}: {raw_version}",
                    label=f"manifest-{raw_name}",
                    kind="manifest-package",
                    strength="strong" if payload.get("provider") else "medium",
                    source="manifest",
                    provider=payload.get("provider"),
                    wrapper=payload.get("wrapper"),
                    surface_family=payload.get("surface_family"),
                    sdk=payload.get("sdk"),
                    version_hint=f"{raw_name}@{raw_version}",
                )
            )


def extract_package_hints_from_pyproject(
    path: Path,
    root: Path,
    aliases: dict[str, dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> None:
    if tomllib is None:
        return
    text = read_text(path)
    if not text:
        return
    try:
        data = tomllib.loads(text)
    except Exception:
        return

    candidates: list[str] = []
    project = data.get("project", {})
    if isinstance(project, dict):
        deps = project.get("dependencies", [])
        if isinstance(deps, list):
            candidates.extend(str(item) for item in deps)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for items in optional.values():
                if isinstance(items, list):
                    candidates.extend(str(item) for item in items)
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            deps = poetry.get("dependencies", {})
            if isinstance(deps, dict):
                for name, spec in deps.items():
                    if name == "python":
                        continue
                    candidates.append(f"{name}{spec if isinstance(spec, str) else ''}")
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for body in group.values():
                    if not isinstance(body, dict):
                        continue
                    deps = body.get("dependencies", {})
                    if isinstance(deps, dict):
                        for name, spec in deps.items():
                            candidates.append(f"{name}{spec if isinstance(spec, str) else ''}")

    for entry in candidates:
        match = re.match(r"([A-Za-z0-9_.\-@/]+)", entry.strip())
        if not match:
            continue
        name = package_name_key(match.group(1))
        payload = aliases.get(name)
        if not payload:
            continue
        evidence.append(
            evidence_item(
                root=root,
                path=path,
                line_no=1,
                snippet=entry,
                label=f"pyproject-{name}",
                kind="manifest-package",
                strength="strong" if payload.get("provider") else "medium",
                source="manifest",
                provider=payload.get("provider"),
                wrapper=payload.get("wrapper"),
                surface_family=payload.get("surface_family"),
                sdk=payload.get("sdk"),
                version_hint=entry.strip(),
            )
        )


def extract_package_hints_from_requirements(
    path: Path,
    root: Path,
    aliases: dict[str, dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> None:
    text = read_text(path)
    if not text:
        return
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        match = re.match(r"([A-Za-z0-9_.\-@/]+)", line)
        if not match:
            continue
        name = package_name_key(match.group(1))
        payload = aliases.get(name)
        if not payload:
            continue
        evidence.append(
            evidence_item(
                root=root,
                path=path,
                line_no=line_no,
                snippet=line,
                label=f"requirements-{name}",
                kind="manifest-package",
                strength="strong" if payload.get("provider") else "medium",
                source="manifest",
                provider=payload.get("provider"),
                wrapper=payload.get("wrapper"),
                surface_family=payload.get("surface_family"),
                sdk=payload.get("sdk"),
                version_hint=line,
            )
        )


def add_pattern_evidence(path: Path, root: Path, lines: list[str], evidence: list[dict[str, Any]]) -> None:
    for line_no, line in enumerate(lines, start=1):
        doc_or_comment = is_doc_or_comment(path, line)
        source = "docs" if doc_or_comment else ("code" if path.suffix.lower() in CODE_EXTENSIONS else "config")
        for pattern in PROVIDER_PATTERNS:
            if not pattern["regex"].search(line):
                continue
            evidence.append(
                evidence_item(
                    root=root,
                    path=path,
                    line_no=line_no,
                    snippet=line,
                    label=pattern["label"],
                    kind=pattern["kind"],
                    strength="weak" if doc_or_comment else pattern["strength"],
                    source=source,
                    provider=pattern.get("provider"),
                    surface_family=pattern.get("family"),
                    sdk=pattern.get("sdk"),
                    base_url_hint=trim_snippet(line) if pattern["kind"] == "gateway-host" else None,
                )
            )
        for pattern in WRAPPER_PATTERNS:
            if not pattern["regex"].search(line):
                continue
            evidence.append(
                evidence_item(
                    root=root,
                    path=path,
                    line_no=line_no,
                    snippet=line,
                    label=pattern["label"],
                    kind=pattern["kind"],
                    strength="weak" if doc_or_comment else pattern["strength"],
                    source=source,
                    provider=pattern.get("provider"),
                    wrapper=pattern.get("wrapper"),
                    surface_family=pattern.get("family"),
                    sdk=pattern.get("sdk"),
                )
            )
        for pattern in FAMILY_PATTERNS:
            if not pattern["regex"].search(line):
                continue
            evidence.append(
                evidence_item(
                    root=root,
                    path=path,
                    line_no=line_no,
                    snippet=line,
                    label=pattern["label"],
                    kind=pattern["kind"],
                    strength="weak" if doc_or_comment else pattern["strength"],
                    source=source,
                    surface_family=pattern.get("family"),
                    sdk=pattern.get("sdk"),
                )
            )
        for family, provider, regex in HOST_HINTS:
            for match in regex.finditer(line):
                evidence.append(
                    evidence_item(
                        root=root,
                        path=path,
                        line_no=line_no,
                        snippet=line,
                        label=f"host-{provider or family}",
                        kind="base-url",
                        strength="weak" if doc_or_comment else "strong",
                        source=source,
                        provider=provider,
                        surface_family=family,
                        sdk=provider or family,
                        base_url_hint=match.group(0),
                    )
                )
        for family, regex in MODEL_HINTS:
            for match in regex.finditer(line):
                evidence.append(
                    evidence_item(
                        root=root,
                        path=path,
                        line_no=line_no,
                        snippet=line,
                        label=f"model-{family}",
                        kind="model-hint",
                        strength="weak" if doc_or_comment else "medium",
                        source=source,
                        surface_family=family,
                        sdk=family,
                        model_hint=match.group(0),
                    )
                )
        for pattern in LEGACY_PATTERNS:
            if not pattern["regex"].search(line):
                continue
            evidence.append(
                evidence_item(
                    root=root,
                    path=path,
                    line_no=line_no,
                    snippet=line,
                    label=pattern["label"],
                    kind=pattern["kind"],
                    strength="weak" if doc_or_comment else "medium",
                    source=source,
                    provider=pattern.get("provider"),
                    surface_family=pattern.get("family"),
                    sdk=pattern.get("provider") or pattern.get("family"),
                )
            )
        for match in ENV_VALUE_RE.finditer(line):
            provider = {
                "OPENAI_API_KEY": "openai",
                "ANTHROPIC_API_KEY": "anthropic",
                "GEMINI_API_KEY": "gemini",
                "GOOGLE_API_KEY": "gemini",
                "AZURE_OPENAI_ENDPOINT": "azure-openai",
                "AZURE_OPENAI_API_KEY": "azure-openai",
                "OPENROUTER_API_KEY": "openrouter",
            }.get(match.group(1))
            evidence.append(
                evidence_item(
                    root=root,
                    path=path,
                    line_no=line_no,
                    snippet=line,
                    label=f"env-{match.group(1)}",
                    kind="env",
                    strength="weak" if doc_or_comment else "strong",
                    source=source,
                    provider=provider,
                    surface_family=provider_to_family(provider) or "unknown",
                    sdk=provider or "env",
                )
            )


def select_candidate_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item for item in evidence
        if item.get("source") in {"manifest", "code", "config"}
    ]


def build_surface_candidates(evidence: list[dict[str, Any]], query_seeds: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in select_candidate_evidence(evidence):
        provider = item.get("provider") or ""
        wrapper = item.get("wrapper") or ""
        family = item.get("surface_family") or "unknown"
        key = f"{provider}|{wrapper}|{family}"
        grouped[key].append(item)

    candidates: list[dict[str, Any]] = []
    for group in grouped.values():
        strong_provider = [item for item in group if item.get("provider") and item.get("strength") == "strong"]
        providers = Counter(str(item.get("provider")) for item in group if item.get("provider"))
        wrappers = Counter(str(item.get("wrapper")) for item in group if item.get("wrapper"))
        families = Counter(str(item.get("surface_family") or "unknown") for item in group)
        languages = Counter(str(item.get("language") or "unknown") for item in group if item.get("language"))
        sdks = Counter(str(item.get("sdk")) for item in group if item.get("sdk"))
        provider = strong_provider[0].get("provider") if strong_provider else (providers.most_common(1)[0][0] if providers else None)
        wrapper = wrappers.most_common(1)[0][0] if wrappers else None
        family = families.most_common(1)[0][0] if families else "unknown"
        if family not in ALLOWED_FAMILIES:
            family = provider_to_family(provider) or ("generic-wrapper" if wrapper else "unknown")

        if provider and strong_provider:
            resolution_level = "provider-resolved"
        elif wrapper:
            resolution_level = "wrapper-resolved"
        elif family != "unknown":
            resolution_level = "family-resolved"
        else:
            resolution_level = "ambiguous"

        confidence_score = 0
        confidence_score += min(len([item for item in group if item.get("strength") == "strong"]), 2)
        confidence_score += min(len([item for item in group if item.get("kind") == "manifest-package"]), 1)
        confidence_score += min(len([item for item in group if item.get("kind") == "base-url"]), 1)
        confidence = "high" if confidence_score >= 3 else ("medium" if confidence_score >= 2 else "low")

        version_hints = unique_values(item.get("version_hint") for item in group if item.get("version_hint"))
        model_hints = unique_values(item.get("model_hint") for item in group if item.get("model_hint"))
        base_url_hints = unique_values(item.get("base_url_hint") for item in group if item.get("base_url_hint"))
        surface_id = f"surface-{len(candidates) + 1:03d}"
        candidate = {
            "surface_id": surface_id,
            "surface_family": family,
            "provider": provider if resolution_level == "provider-resolved" else None,
            "wrapper": wrapper,
            "resolution_level": resolution_level,
            "confidence": confidence,
            "language": languages.most_common(1)[0][0] if languages else "unknown",
            "primary_sdk": sdks.most_common(1)[0][0] if sdks else "unknown",
            "version_hints": version_hints,
            "model_hints": model_hints,
            "base_url_hints": base_url_hints,
            "query_seeds": list(query_seeds.get(provider or family) or query_seeds.get(wrapper or "") or []),
            "evidence": group[:MAX_SURFACE_EVIDENCE],
        }
        if resolution_level == "ambiguous":
            candidate["surface_family"] = "unknown"
        if resolution_level == "wrapper-resolved" and family == "unknown":
            candidate["surface_family"] = "generic-wrapper"
        candidates.append(candidate)

    candidates = collapse_candidates(candidates)
    candidates.sort(key=lambda item: (resolution_rank(item["resolution_level"]), item["surface_family"], item["primary_sdk"]))
    for idx, candidate in enumerate(candidates, start=1):
        candidate["surface_id"] = f"surface-{idx:03d}"
    return candidates


def unique_values(values: Sequence[Optional[str]]) -> list[str]:
    result: list[str] = []
    for value in values:
        if not value:
            continue
        text = str(value)
        if text not in result:
            result.append(text)
    return result


def resolution_rank(level: str) -> int:
    order = {
        "provider-resolved": 0,
        "family-resolved": 1,
        "wrapper-resolved": 2,
        "ambiguous": 3,
    }
    return order.get(level, 9)


def confidence_rank(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 9)


def merge_candidate(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["evidence"] = sorted(
        list(target.get("evidence") or []) + list(source.get("evidence") or []),
        key=lambda item: (str(item.get("path") or ""), int(item.get("line") or 0), str(item.get("label") or "")),
    )[:MAX_SURFACE_EVIDENCE]
    target["version_hints"] = unique_values(list(target.get("version_hints") or []) + list(source.get("version_hints") or []))
    target["model_hints"] = unique_values(list(target.get("model_hints") or []) + list(source.get("model_hints") or []))
    target["base_url_hints"] = unique_values(list(target.get("base_url_hints") or []) + list(source.get("base_url_hints") or []))
    target["query_seeds"] = unique_values(list(target.get("query_seeds") or []) + list(source.get("query_seeds") or []))
    if target.get("surface_family") in {"unknown", "generic-wrapper", "custom-http-llm"} and source.get("surface_family") not in {"unknown", "generic-wrapper", "custom-http-llm"}:
        target["surface_family"] = source["surface_family"]
    if target.get("provider") is None and source.get("provider") is not None:
        target["provider"] = source["provider"]
    if target.get("wrapper") is None and source.get("wrapper") is not None:
        target["wrapper"] = source["wrapper"]
    if target.get("primary_sdk") in {"unknown", "generic-wrapper"} and source.get("primary_sdk") not in {"unknown", "generic-wrapper"}:
        target["primary_sdk"] = source["primary_sdk"]
    if target.get("language") == "unknown" and source.get("language") != "unknown":
        target["language"] = source["language"]
    if confidence_rank(str(source.get("confidence") or "low")) < confidence_rank(str(target.get("confidence") or "low")):
        target["confidence"] = source["confidence"]


def collapse_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    for candidate in candidates:
        duplicate = next(
            (
                item for item in deduped
                if item.get("provider") == candidate.get("provider")
                and item.get("wrapper") == candidate.get("wrapper")
                and item.get("surface_family") == candidate.get("surface_family")
                and item.get("resolution_level") == candidate.get("resolution_level")
            ),
            None,
        )
        if duplicate is None:
            deduped.append(candidate)
            continue
        merge_candidate(duplicate, candidate)

    candidates = deduped
    changed = True
    while changed:
        changed = False
        for source in list(candidates):
            if source["resolution_level"] not in {"family-resolved", "ambiguous"}:
                continue
            source_paths = {str(item.get("path") or "") for item in source.get("evidence") or []}
            target = next(
                (
                    item for item in candidates
                    if item is not source
                    and item["resolution_level"] in {"provider-resolved", "wrapper-resolved"}
                    and (
                        item.get("surface_family") == source.get("surface_family")
                        or item.get("surface_family") == "generic-wrapper"
                        or (
                            source.get("surface_family") in {"custom-http-llm", "unknown"}
                            and source_paths & {str(e.get("path") or "") for e in item.get("evidence") or []}
                        )
                    )
                ),
                None,
            )
            if target is None:
                continue
            merge_candidate(target, source)
            candidates.remove(source)
            changed = True
            break

    family_candidates = [item for item in candidates if item["resolution_level"] == "family-resolved"]
    for source in list(family_candidates):
        source_paths = {str(item.get("path") or "") for item in source.get("evidence") or []}
        target = next(
            (
                item for item in candidates
                if item is not source
                and item["resolution_level"] == "family-resolved"
                and source_paths & {str(e.get("path") or "") for e in item.get("evidence") or []}
                and source.get("surface_family") in {"custom-http-llm", "unknown"}
                and item.get("surface_family") not in {"custom-http-llm", "unknown"}
            ),
            None,
        )
        if target is None:
            continue
        merge_candidate(target, source)
        candidates.remove(source)
    return candidates


def attach_surface_ids(evidence: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[tuple[str, int, str], str]:
    mapping: dict[tuple[str, int, str], str] = {}
    for candidate in candidates:
        for item in candidate.get("evidence") or []:
            mapping[(str(item.get("path")), int(item.get("line") or 0), str(item.get("label") or ""))] = str(candidate["surface_id"])
    return mapping


def build_findings(evidence: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_index = {candidate["surface_id"]: candidate for candidate in candidates}
    evidence_to_surface = attach_surface_ids(evidence, candidates)
    findings: list[dict[str, Any]] = []

    for candidate in candidates:
        if candidate["resolution_level"] == "ambiguous":
            findings.append(
                {
                    "id": f"{candidate['surface_id']}-provider-ambiguous",
                    "surface_id": candidate["surface_id"],
                    "severity": "low",
                    "kind": "provider-ambiguous",
                    "resolution_level": candidate["resolution_level"],
                    "surface_family": candidate["surface_family"],
                    "provider": candidate.get("provider"),
                    "wrapper": candidate.get("wrapper"),
                    "title": "The underlying provider still cannot be resolved confidently",
                    "current_behavior": "Local evidence points to an LLM-like integration surface, but it does not identify one concrete provider or wrapper with confidence.",
                    "current_expectation": "Keep the surface ambiguous until stronger runtime evidence or Context7-backed docs narrow it safely.",
                    "verification_status": "not-run",
                    "recommended_change_shape": "Resolve the real runtime surface from imports, hosts, env wiring, or deployment config before making provider-specific freshness claims.",
                    "evidence": candidate["evidence"][:4],
                }
            )
        elif candidate["resolution_level"] == "wrapper-resolved" and not candidate.get("provider"):
            findings.append(
                {
                    "id": f"{candidate['surface_id']}-gateway-gap",
                    "surface_id": candidate["surface_id"],
                    "severity": "low",
                    "kind": "gateway-resolution-gap",
                    "resolution_level": candidate["resolution_level"],
                    "surface_family": candidate["surface_family"],
                    "provider": candidate.get("provider"),
                    "wrapper": candidate.get("wrapper"),
                    "title": "A wrapper or gateway is clear, but the provider underneath it is still hidden",
                    "current_behavior": "The repo exposes wrapper-level evidence without enough provider-specific evidence to claim one concrete upstream API surface.",
                    "current_expectation": "Verify wrapper-owned docs first, then only escalate to provider-specific docs if pass-through behavior is visible.",
                    "verification_status": "not-run",
                    "recommended_change_shape": "Use Context7 on the wrapper first and record any provider pass-through parameters before making freshness judgments.",
                    "evidence": candidate["evidence"][:4],
                }
            )

    for item in evidence:
        if item.get("kind") != "legacy-suspicion":
            continue
        key = (str(item.get("path")), int(item.get("line") or 0), str(item.get("label") or ""))
        surface_id = evidence_to_surface.get(key)
        if not surface_id:
            continue
        candidate = candidate_index[surface_id]
        findings.append(
            {
                "id": f"{surface_id}-{item['label']}",
                "surface_id": surface_id,
                "severity": "low",
                "kind": "legacy-suspicion",
                "resolution_level": candidate["resolution_level"],
                "surface_family": candidate["surface_family"],
                "provider": candidate.get("provider"),
                "wrapper": candidate.get("wrapper"),
                "title": "A legacy-looking LLM API surface was found in executable code",
                "current_behavior": item["snippet"],
                "current_expectation": "Treat this as a migration clue until Context7 verifies whether the current official docs still support this exact surface.",
                "verification_status": "triage-only",
                "recommended_change_shape": "Run a verified Context7 pass for this surface before changing code or reporting it as stale.",
                "evidence": [item],
            }
        )
    return dedupe_findings(findings)


def dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for finding in findings:
        key = (str(finding.get("surface_id")), str(finding.get("kind")))
        if key in seen and finding.get("kind") != "legacy-suspicion":
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def build_priorities(candidates: list[dict[str, Any]], findings: list[dict[str, Any]]) -> dict[str, list[str]]:
    now: list[str] = []
    next_actions: list[str] = []
    later: list[str] = []

    if any(item.get("kind") == "legacy-suspicion" for item in findings):
        now.append("Use Context7 to verify the exact current SDK surface for each legacy-looking code path before calling anything stale or migrating syntax.")
    if any(item.get("resolution_level") == "ambiguous" for item in candidates):
        now.append("Resolve ambiguous LLM surfaces from imports, base URLs, env wiring, or runtime config before provider-specific freshness claims.")
    if any(item.get("resolution_level") == "wrapper-resolved" and not item.get("provider") for item in candidates):
        next_actions.append("Verify wrapper-owned semantics first, then only add provider-specific docs when pass-through behavior is explicit in code.")
    if any(item.get("resolution_level") == "family-resolved" for item in candidates):
        next_actions.append("Use family-level Context7 queries for openai-compatible / anthropic-messages / google-genai surfaces that do not expose one concrete vendor.")
    if candidates:
        later.append("Centralize LLM adapter ownership so future freshness audits resolve surfaces with fewer ambiguous clues.")
    if not now:
        now.append("No urgent freshness drift was verified locally. Treat this artifact as triage and escalate only after Context7 checks.")
    if not next_actions:
        next_actions.append("Run a verified agent-first pass only on the detected surfaces instead of querying every possible provider.")
    if not later:
        later.append("Add lightweight review guidance so new LLM integrations declare provider, wrapper, and base URL more explicitly.")
    return {"now": now[:3], "next": next_actions[:3], "later": later[:3]}


def build_repo_profile(root: Path, files: list[Path], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    languages = Counter()
    package_managers: list[str] = []
    manifests_seen: set[str] = set()
    for path in files:
        language = detect_language(path)
        if language != "unknown":
            languages[language] += 1
        if path.name in PACKAGE_MANAGER_FILES:
            manifests_seen.add(path.name)
    for name, manager in PACKAGE_MANAGER_FILES.items():
        if name in manifests_seen and manager not in package_managers:
            package_managers.append(manager)
    return {
        "repo_root": str(root.resolve()),
        "files_scanned": len(files),
        "languages": [name for name, _count in languages.most_common()],
        "package_managers": package_managers,
        "surface_count": len(candidates),
        "wrapper_count": len([item for item in candidates if item.get("wrapper")]),
        "provider_count": len([item for item in candidates if item.get("provider")]),
    }


def build_summary(root: Path, files: list[Path], evidence: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    findings = build_findings(evidence, candidates)
    if not candidates:
        audit_mode = "not-applicable"
        limitations = ["No Python / TypeScript LLM SDK, wrapper, host, or family-level runtime surface was detected in executable files or manifests."]
    else:
        audit_mode = "triage"
        limitations = [
            "This is a triage artifact only. Current docs were not checked in this run.",
            "High-severity provider-specific freshness claims are reserved for the agent-first Context7 verification flow.",
        ]
    summary = {
        "skill": "llm-api-freshness-guard",
        "version": VERSION,
        "generated_at": utc_now(),
        "audit_mode": audit_mode,
        "target_scope": "repo",
        "repo_profile": build_repo_profile(root, files, candidates),
        "surface_resolution": candidates,
        "doc_verification": [],
        "findings": findings,
        "priorities": build_priorities(candidates, findings) if candidates else {"now": [], "next": [], "later": []},
        "scan_limitations": limitations,
        "dependency_status": "ready",
        "bootstrap_actions": [],
        "dependency_failures": [],
    }
    return summary


def build_evidence_bundle(root: Path, files: list[Path], hints: dict[str, Any], evidence: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "skill": "llm-api-freshness-guard",
        "version": VERSION,
        "generated_at": utc_now(),
        "target_scope": "repo",
        "repo_profile": build_repo_profile(root, files, candidates),
        "query_seeds": hints.get("query_seeds") or {},
        "surface_candidates": candidates,
        "signals": evidence[:MAX_SIGNAL_OUTPUT],
    }


def collect(root: Path, hints: dict[str, Any]) -> dict[str, Any]:
    files = iter_files(root)
    evidence: list[dict[str, Any]] = []
    aliases = load_manifest_aliases(hints)
    for path in files:
        if path.name == "package.json":
            extract_package_hints_from_package_json(path, root, aliases, evidence)
        elif path.name == "pyproject.toml":
            extract_package_hints_from_pyproject(path, root, aliases, evidence)
        elif path.name.startswith("requirements") and path.suffix == ".txt":
            extract_package_hints_from_requirements(path, root, aliases, evidence)

        text = read_text(path)
        if not text:
            continue
        add_pattern_evidence(path, root, text.splitlines(), evidence)

    candidates = build_surface_candidates(evidence, hints.get("query_seeds") or {})
    summary = build_summary(root, files, evidence, candidates)
    evidence_bundle = build_evidence_bundle(root, files, hints, evidence, candidates)
    return {
        "signals": evidence_bundle,
        "summary": summary,
        "report": render_report(summary),
        "agent_brief": render_agent_brief(summary),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = Path(args.repo).expanduser().resolve()
    if not root.exists():
        print(f"error: path does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"error: path is not a directory: {root}", file=sys.stderr)
        return 2

    hints_path = (
        Path(args.provider_hints).expanduser().resolve()
        if args.provider_hints
        else Path(__file__).resolve().parent.parent / "assets" / "provider-hints.json"
    )
    try:
        hints = load_provider_hints(hints_path)
    except Exception as exc:
        print(f"error: could not load provider hints: {exc}", file=sys.stderr)
        return 2

    result = collect(root, hints)
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
