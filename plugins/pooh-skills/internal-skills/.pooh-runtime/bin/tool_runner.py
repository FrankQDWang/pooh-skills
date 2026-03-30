#!/usr/bin/env python3
"""Shared locked-tool execution helpers for pooh-skills scanners."""

from __future__ import annotations

import json
import os
import subprocess
import contextlib
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from runtime_contract import DOCS_BIN_DIR, NODE_BIN_DIR, PY_BIN_DIR, RUNTIME_ROOT, load_registry, resolve_tool_path

DEFAULT_TIMEOUT_SECONDS = 240
MAX_DETAIL_CHARS = 4000


@dataclass
class ToolRun:
    tool: str
    status: str
    command: str
    exit_code: int
    issue_count: int
    summary: str
    details: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def runtime_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([
        str(PY_BIN_DIR),
        str(NODE_BIN_DIR),
        str(DOCS_BIN_DIR),
        env.get("PATH", ""),
    ])
    if extra:
        env.update(extra)
    return env


def truncate_detail(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) <= MAX_DETAIL_CHARS:
        return cleaned
    return cleaned[: MAX_DETAIL_CHARS - 3].rstrip() + "..."


def parse_json_payload(output: str) -> Any | None:
    output = output.strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        pass

    start_positions = [index for index, char in enumerate(output) if char in "[{"]
    for start in start_positions:
        try:
            return json.loads(output[start:])
        except json.JSONDecodeError:
            continue
    return None


def count_payload_issues(payload: Any) -> int:
    if payload is None:
        return 0
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return len(payload["results"])
        if isinstance(payload.get("generalDiagnostics"), list):
            return len(payload["generalDiagnostics"])
        if isinstance(payload.get("issues"), list):
            total = 0
            for issue in payload["issues"]:
                if isinstance(issue, dict):
                    for key, value in issue.items():
                        if key == "file":
                            continue
                        if isinstance(value, list):
                            total += len(value)
                else:
                    total += 1
            return total
        if isinstance(payload.get("violations"), list):
            return len(payload["violations"])
    return 0


def payload_excerpt(payload: Any) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [truncate_detail(json.dumps(item, ensure_ascii=False)) for item in payload[:5]]
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            out: list[str] = []
            for item in payload["results"][:5]:
                path = item.get("path") or item.get("check_id") or "result"
                extra = item.get("extra") or {}
                message = extra.get("message") or item.get("start") or "match"
                out.append(truncate_detail(f"{path}: {message}"))
            return out
        if isinstance(payload.get("generalDiagnostics"), list):
            out = []
            for item in payload["generalDiagnostics"][:5]:
                out.append(truncate_detail(f"{item.get('file')}: {item.get('message')}"))
            return out
        if isinstance(payload.get("issues"), list):
            out = []
            for item in payload["issues"][:5]:
                if isinstance(item, dict):
                    file_name = item.get("file", "package.json")
                    local_issues: list[str] = []
                    for key, value in item.items():
                        if key == "file" or not isinstance(value, list) or not value:
                            continue
                        local_issues.append(f"{key}={len(value)}")
                    out.append(truncate_detail(f"{file_name}: {', '.join(local_issues) or 'issues detected'}"))
            return out
        if isinstance(payload.get("violations"), list):
            out = []
            for item in payload["violations"][:5]:
                out.append(truncate_detail(f"{item.get('from')}: {item.get('to')} [{item.get('rule', {}).get('name', 'violation')}]"))
            return out
    return [truncate_detail(str(payload))]


def run_locked_tool(
    tool: str,
    args: list[str],
    cwd: Path,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    allow_exit_codes: set[int] | None = None,
    env_extra: dict[str, str] | None = None,
) -> tuple[ToolRun, Any | None]:
    registry = load_registry()
    binary = resolve_tool_path(tool, registry)
    command = [str(binary), *args]
    env = runtime_env(env_extra)
    allow_codes = allow_exit_codes or {0}
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        detail = truncate_detail((exc.stdout or "") + "\n" + (exc.stderr or ""))
        return ToolRun(
            tool=tool,
            status="failed",
            command=" ".join(command),
            exit_code=124,
            issue_count=0,
            summary=f"{tool} timed out after {timeout_seconds}s.",
            details=[detail] if detail else [],
        ), None
    except FileNotFoundError as exc:
        return ToolRun(
            tool=tool,
            status="failed",
            command=" ".join(command),
            exit_code=127,
            issue_count=0,
            summary=str(exc),
            details=[],
        ), None

    output_parts = [part.strip() for part in (completed.stdout, completed.stderr) if part and part.strip()]
    raw_output = "\n".join(output_parts)
    payload = parse_json_payload(raw_output)
    issue_count = count_payload_issues(payload)

    if completed.returncode in allow_codes:
        if completed.returncode != 0:
            status = "issues"
        else:
            status = "issues" if issue_count else "passed"
    else:
        status = "failed"

    if status == "passed":
        summary = f"{tool} ran successfully with no machine-detected findings."
    elif status == "issues":
        if issue_count:
            summary = f"{tool} ran successfully and reported {issue_count} finding(s)."
        else:
            summary = f"{tool} returned a non-zero audit result that requires review."
    else:
        summary = f"{tool} execution failed with exit code {completed.returncode}."

    details = payload_excerpt(payload) or ([truncate_detail(raw_output)] if raw_output else [])
    return ToolRun(
        tool=tool,
        status=status,
        command=" ".join(command),
        exit_code=completed.returncode,
        issue_count=issue_count,
        summary=summary,
        details=details[:5],
    ), payload


def skipped_tool_run(tool: str, reason: str) -> ToolRun:
    return ToolRun(
        tool=tool,
        status="skipped",
        command="",
        exit_code=0,
        issue_count=0,
        summary=reason,
        details=[],
    )


def any_failed(tool_runs: list[ToolRun]) -> bool:
    return any(item.status == "failed" for item in tool_runs)


def tool_run_map(tool_runs: list[ToolRun]) -> dict[str, ToolRun]:
    return {item.tool: item for item in tool_runs}


def run_semgrep_rules(
    rule_text: str,
    cwd: Path,
    targets: list[str],
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[ToolRun, Any | None]:
    with NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as handle:
        handle.write(rule_text)
        rule_path = Path(handle.name)
    try:
        return run_locked_tool(
            "semgrep",
            ["scan", "--config", str(rule_path), "--json", "--quiet", *targets],
            cwd,
            allow_exit_codes={0, 1},
            timeout_seconds=timeout_seconds,
        )
    finally:
        with contextlib.suppress(FileNotFoundError):
            rule_path.unlink()


def run_astgrep_pattern(
    pattern: str,
    lang: str,
    cwd: Path,
    targets: list[str],
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[ToolRun, Any | None]:
    return run_locked_tool(
        "ast-grep",
        ["run", "--pattern", pattern, "--lang", lang, "--json=compact", *targets],
        cwd,
        allow_exit_codes={0, 1},
        timeout_seconds=timeout_seconds,
    )
