#!/usr/bin/env python3
"""Heuristic scanner for distributed side-effect hazards.

The goal is not perfect precision. The goal is to surface high-value, review-worthy
signals that commonly appear in AI-generated code:
- database commit + publish in one flow
- external side effect before commit
- consumer logic without idempotency clues
- retries around non-idempotent effects
- message handling with no visible DLQ or event versioning signals
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List

RUNTIME_BIN_DIR = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN_DIR))

from standard_audit_utils import describe_surface_source, first_party_text_files  # noqa: E402
from standard_audit_utils import foreign_runtime_excluded_count, format_surface_note, surface_source  # noqa: E402
from tool_runner import ToolRun, run_astgrep_pattern, run_semgrep_rules  # noqa: E402

TEXT_EXTS = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".toml", ".ini",
}

DB_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(session|db|uow|unit_of_work|transaction|txn)\.commit\s*\(",
        r"\bcommit\s*\(",
        r"\b(save_changes|flush)\s*\(",
    ]
]

SIDE_EFFECT_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(publish|emit|produce|send|enqueue|dispatch|append_to_stream|notify)\s*\(",
        r"\b(requests|httpx|axios)\.(post|put|patch|delete)\s*\(",
        r"\bfetch\s*\(",
        r"\b(webhook|sns|sqs|kafka|rabbit|pubsub|nats|celery)\b",
        r"\b(charge|capture|refund|ship|deliver|post_message)\s*\(",
    ]
]

OUTBOX_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\boutbox\b",
        r"\bevent_outbox\b",
        r"\bpending_events\b",
        r"\bcdc\b",
        r"\bdebezium\b",
        r"\brelay\b",
    ]
]

IDEMPOTENCY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bidempoten",
        r"\bdedup",
        r"\bde[-_ ]?dupe\b",
        r"\bprocessed_messages?\b",
        r"\bmessage_id\b",
        r"\bevent_id\b",
        r"\brequest_id\b",
        r"\bidempotency[_-]?key\b",
        r"\bON CONFLICT\b",
        r"\bUPSERT\b",
        r"\bunique\b",
    ]
]

RETRY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [r"@retry", r"\bretry\s*\(", r"\btenacity\b", r"\bbackoff\b"]
]

DLQ_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [r"\bdlq\b", r"dead[-_ ]?letter", r"poison[-_ ]?queue"]
]

EVENT_VERSION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bevent_version\b",
        r"\bversion\s*[:=]",
        r'"version"\s*:',
        r"\bv[0-9]+\b",
    ]
]

OBSERVABILITY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\btrace_id\b",
        r"\bcorrelation_id\b",
        r"\bspan\b",
        r"\bmetric\b",
        r"\blogger\b",
        r"\bopentelemetry\b",
    ]
]

CONSUMER_HINTS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bconsumer\b", r"\bsubscriber\b", r"\bhandler\b", r"\blistener\b",
        r"\bwebhook\b", r"\bon_message\b", r"\bon_event\b", r"\bprocess_",
    ]
]
TOOL_BATCH_SIZE = 200

STATE_MUTATION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [r"\b(commit|save|insert|update|delete|upsert|write)\b"]
]

SEMGRP_SIDE_EFFECT_RULES = """
rules:
  - id: distributed-network-side-effect
    languages: [python]
    severity: WARNING
    message: Remote side effect
    pattern-either:
      - pattern: requests.$METHOD(...)
      - pattern: httpx.$METHOD(...)
  - id: distributed-retry-signal
    languages: [python]
    severity: WARNING
    message: Retry wrapper
    pattern-either:
      - pattern: "@retry"
      - pattern: retry(...)
"""


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


def iter_files(root: Path) -> Iterable[Path]:
    yield from first_party_text_files(root, suffixes=TEXT_EXTS)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    except Exception:
        return ""


def first_match_line(lines: List[str], patterns: List[re.Pattern]) -> int | None:
    for idx, line in enumerate(lines, start=1):
        if any(p.search(line) for p in patterns):
            return idx
    return None


def has_any(text: str, patterns: List[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    counter = Counter(f.severity for f in findings)
    return {k: int(counter.get(k, 0)) for k in ("critical", "high", "medium", "low")}


def relative_targets(repo: Path, files: list[Path], suffixes: set[str]) -> list[str]:
    return [str(path.relative_to(repo)) for path in files if path.suffix.lower() in suffixes]


def chunk_targets(targets: list[str], batch_size: int = TOOL_BATCH_SIZE) -> list[list[str]]:
    return [targets[index : index + batch_size] for index in range(0, len(targets), batch_size)]


def merge_tool_runs(tool: str, runs: list[ToolRun]) -> ToolRun:
    if not runs:
        return ToolRun(
            tool=tool,
            status="skipped",
            command="",
            exit_code=0,
            issue_count=0,
            summary=f"{tool} was skipped because no first-party targets were detected.",
            details=[],
        )
    status = "passed"
    exit_code = 0
    issue_count = 0
    details: list[str] = []
    for run in runs:
        issue_count += run.issue_count
        details.extend(run.details[:3])
        if run.status == "failed":
            status = "failed"
            exit_code = run.exit_code
        elif run.status == "issues" and status != "failed":
            status = "issues"
            exit_code = run.exit_code
    if status == "failed":
        summary = f"{tool} execution failed in at least one first-party target batch."
    elif status == "issues":
        if issue_count:
            summary = f"{tool} reported {issue_count} finding(s) across first-party targets."
        else:
            summary = f"{tool} returned a non-zero audit result across first-party targets."
    else:
        summary = f"{tool} ran successfully with no machine-detected findings across first-party targets."
    return ToolRun(
        tool=tool,
        status=status,
        command=f"{tool} batched first-party targets ({len(runs)} chunk(s))",
        exit_code=exit_code,
        issue_count=issue_count,
        summary=summary,
        details=details[:5],
    )


def build_tool_runs(repo: Path, files: list[Path]) -> list[ToolRun]:
    tool_runs: list[ToolRun] = []
    py_targets = relative_targets(repo, files, {".py", ".pyi"})
    js_targets = relative_targets(repo, files, {".ts", ".tsx", ".js", ".jsx"})

    if py_targets:
        semgrep_runs: list[ToolRun] = []
        for batch in chunk_targets(py_targets):
            semgrep_run, _ = run_semgrep_rules(SEMGRP_SIDE_EFFECT_RULES, repo, batch)
            semgrep_runs.append(semgrep_run)
        tool_runs.append(merge_tool_runs("semgrep", semgrep_runs))
    if js_targets:
        ast_lang = "typescript" if any(target.endswith((".ts", ".tsx")) for target in js_targets) else "javascript"
        ast_runs: list[ToolRun] = []
        for batch in chunk_targets(js_targets):
            ast_run, _ = run_astgrep_pattern("fetch($$$ARGS)", ast_lang, repo, batch)
            ast_runs.append(ast_run)
        tool_runs.append(merge_tool_runs("ast-grep", ast_runs))
    return tool_runs


def add_tool_findings(findings: list[Finding], tool_runs: list[ToolRun]) -> None:
    seen = {(item.category, item.path, item.line, item.title) for item in findings}
    for run in tool_runs:
        if run.status == "failed":
            candidate = Finding(
                id=f"dsh-{len(findings)+1:03d}",
                category="scan-blocker",
                severity="medium",
                confidence="high",
                title=f"{run.tool} did not complete cleanly",
                path=".",
                line=1,
                evidence=[run.summary, *run.details[:2]],
                recommendation="Fix the locked structural tool execution before trusting the distributed-side-effect report.",
                merge_gate="warn-only",
            )
        elif run.status == "issues":
            candidate = Finding(
                id=f"dsh-{len(findings)+1:03d}",
                category="dynamic-dispatch-signal" if run.tool == "ast-grep" else "side-effect-pattern-signal",
                severity="medium",
                confidence="medium",
                title=f"{run.tool} reported additional distributed side-effect evidence",
                path=".",
                line=1,
                evidence=[run.summary, *run.details[:3]],
                recommendation="Review the structural matches together with the heuristic findings before calling the flow safe.",
                merge_gate="warn-only",
            )
        else:
            continue
        key = (candidate.category, candidate.path, candidate.line, candidate.title)
        if key not in seen:
            findings.append(candidate)
            seen.add(key)


def infer_verdict(findings: list[Finding], repo_flags: dict[str, bool], relevant_signals: int) -> tuple[str, str]:
    if relevant_signals == 0:
        return "not-applicable", "No meaningful broker / webhook / worker / distributed side-effect surface was detected."
    sev = severity_counts(findings)
    if sev["critical"] > 0 or sev["high"] >= 2:
        return "unsafe", "The repo contains strong evidence that distributed side effects can duplicate, disappear, or diverge."
    if sev["high"] == 1 or sev["medium"] >= 2:
        return "fragile", "The repo shows distributed side-effect weaknesses that are likely survivable in demos and dangerous in production."
    if findings:
        return "watch", "The repo shows limited or moderate reliability debt, but not enough evidence for a top-level unsafe verdict."
    positive = sum(int(v) for v in repo_flags.values())
    if positive >= 4:
        return "hardened", "The repo shows multiple visible reliability controls and no scanner-detected high-signal hazards."
    return "sound", "No high-signal distributed side-effect hazards were found by the heuristic scan."


def render_human_report(summary: dict[str, Any]) -> str:
    findings = summary["findings"]
    tool_runs = summary.get("tool_runs", [])
    lines = [
        "# Distributed Side-Effect Hardgate Report",
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
        lines.append("- No locked tool runs were recorded for this repository surface.")
    else:
        for item in tool_runs:
            lines.extend([
                f"### {item['tool']}",
                f"- status: `{item['status']}`",
                f"- summary: {item['summary']}",
                *(f"- detail: {detail}" for detail in item.get("details", [])[:3]),
                "",
            ])

    lines.extend(["## 3. Highest-risk findings", ""])
    if not findings:
        lines.append("- No distributed side-effect findings were detected.")
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
        "- Treat this audit as production-correctness evidence, not as permission for automatic edits.",
        "- Resolve dual-write, retry, and idempotency risks before shipping more side effects.",
        "- Re-run the locked audit stack after manual hardening work.",
        "",
    ])
    return "\n".join(lines)


def render_agent_brief(summary: dict[str, Any]) -> str:
    findings = summary["findings"]
    lines = [
        "# Distributed Side-Effect Handoff Brief",
        "",
        "## Context",
        f"- overall_verdict: `{summary.get('overall_verdict')}`",
        f"- dependency_status: `{summary.get('dependency_status')}`",
        f"- summary_line: {summary.get('summary_line')}",
        f"- surface_source: `{summary.get('surface_source_note', '')}`",
        f"- scan_surface: `{summary.get('surface_note', '')}`",
        "",
        "## Ordered actions",
        "1. Remove blocker-level dual-write, retry, or idempotency risks before tuning anything cosmetic.",
        "2. Treat missing DLQ, event versioning, and observability signals as production-readiness debt.",
        "3. Re-run the locked audit stack after manual hardening changes.",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("- No distributed side-effect findings were detected by the locked stack.")
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


def scan(repo: Path) -> dict:
    files = list(iter_files(repo))
    surface_kind, _ = surface_source(repo)
    surface_note = format_surface_note(
        first_party_count=len(files),
        foreign_runtime_excluded=foreign_runtime_excluded_count(repo, suffixes=TEXT_EXTS),
        source=surface_kind,
    )
    surface_source_note = describe_surface_source(repo)
    tool_runs = build_tool_runs(repo, files)
    repo_text = []
    for path in files:
        text = read_text(path)
        if text:
            repo_text.append(text[:20000])
    joined = "\n".join(repo_text)

    repo_flags = {
        "outbox": has_any(joined, OUTBOX_PATTERNS),
        "idempotency": has_any(joined, IDEMPOTENCY_PATTERNS),
        "dead_letter": has_any(joined, DLQ_PATTERNS),
        "event_versioning": has_any(joined, EVENT_VERSION_PATTERNS),
        "observability": has_any(joined, OBSERVABILITY_PATTERNS),
    }

    findings: list[Finding] = []
    seen_keys: set[tuple] = set()
    relevant_files = 0
    relevant_signals = 0
    language_counter = Counter()

    def add_finding(f: Finding) -> None:
        key = (f.category, f.path, f.line, f.title)
        if key not in seen_keys:
            findings.append(f)
            seen_keys.add(key)

    for path in files:
        language_counter[path.suffix.lower()] += 1
        rel = str(path.relative_to(repo))
        text = read_text(path)
        if not text:
            continue
        lines = text.splitlines()
        lower = text.lower()

        local_relevant = (
            has_any(text, SIDE_EFFECT_PATTERNS)
            or has_any(text, DB_PATTERNS)
            or has_any(text, CONSUMER_HINTS)
            or "webhook" in lower
            or "queue" in lower
            or "event" in lower
        )
        if local_relevant:
            relevant_files += 1
            relevant_signals += 1

        # Sliding windows to catch commit/send ordering
        window_size = 40
        for start in range(0, len(lines), 10):
            window = lines[start:start + window_size]
            if not window:
                continue
            chunk = "\n".join(window)
            commit_line_local = first_match_line(window, DB_PATTERNS)
            effect_line_local = first_match_line(window, SIDE_EFFECT_PATTERNS)
            if commit_line_local and effect_line_local:
                global_commit = start + commit_line_local
                global_effect = start + effect_line_local
                if global_effect < global_commit:
                    add_finding(Finding(
                        id=f"dsh-{len(findings)+1:03d}",
                        category="pre-commit-side-effect",
                        severity="critical",
                        confidence="high",
                        title="External side effect appears before durable local commit",
                        path=rel,
                        line=global_effect,
                        evidence=[
                            window[effect_line_local - 1].strip(),
                            window[commit_line_local - 1].strip(),
                        ],
                        recommendation="Move the side effect behind a durable handoff or commit boundary; do not let remote systems observe uncommitted state.",
                        merge_gate="block-now",
                    ))
                else:
                    add_finding(Finding(
                        id=f"dsh-{len(findings)+1:03d}",
                        category="dual-write-hazard",
                        severity="high",
                        confidence="high",
                        title="Database write and external side effect happen in the same flow",
                        path=rel,
                        line=global_commit,
                        evidence=[
                            window[commit_line_local - 1].strip(),
                            window[effect_line_local - 1].strip(),
                        ],
                        recommendation="Introduce an outbox / relay / equivalent durable handoff instead of relying on inline commit + publish.",
                        merge_gate="block-now",
                    ))
                    if not (repo_flags["outbox"] or has_any(chunk, OUTBOX_PATTERNS)):
                        add_finding(Finding(
                            id=f"dsh-{len(findings)+1:03d}",
                            category="outbox-gap",
                            severity="high",
                            confidence="medium",
                            title="No visible outbox / relay signal near a dual-write path",
                            path=rel,
                            line=global_commit,
                            evidence=[
                                "commit + side effect detected",
                                "no local outbox / relay keyword detected in the surrounding flow",
                            ],
                            recommendation="Add a transactional outbox or an equivalently durable handoff between persistence and external publication.",
                            merge_gate="block-changed-files",
                        ))

            if has_any(chunk, RETRY_PATTERNS) and has_any(chunk, SIDE_EFFECT_PATTERNS) and not has_any(chunk, IDEMPOTENCY_PATTERNS):
                retry_line_local = first_match_line(window, RETRY_PATTERNS) or 1
                add_finding(Finding(
                    id=f"dsh-{len(findings)+1:03d}",
                    category="unsafe-retry",
                    severity="high",
                    confidence="medium",
                    title="Retry logic wraps a likely side-effect path without visible idempotency clues",
                    path=rel,
                    line=start + retry_line_local,
                    evidence=[window[retry_line_local - 1].strip()],
                    recommendation="Require an idempotency key / dedupe barrier before retrying this effect path.",
                    merge_gate="block-changed-files",
                ))

        # Consumer / webhook without idempotency hints
        path_hint = rel.lower()
        if (has_any(text, CONSUMER_HINTS) or any(h in path_hint for h in ["consumer", "handler", "listener", "subscriber", "webhook"])) and has_any(text, STATE_MUTATION_PATTERNS):
            if not (has_any(text, IDEMPOTENCY_PATTERNS) or repo_flags["idempotency"]):
                line = first_match_line(lines, CONSUMER_HINTS) or first_match_line(lines, STATE_MUTATION_PATTERNS) or 1
                add_finding(Finding(
                    id=f"dsh-{len(findings)+1:03d}",
                    category="idempotency-gap",
                    severity="high",
                    confidence="medium",
                    title="Consumer / handler mutates state without visible idempotency guard",
                    path=rel,
                    line=line,
                    evidence=[lines[line - 1].strip()],
                    recommendation="Persist message identity or an equivalent dedupe barrier before making the effect path irreversible.",
                    merge_gate="block-changed-files",
                ))

    # Repo-level gaps
    if relevant_signals > 0 and not repo_flags["dead_letter"] and has_any(joined, SIDE_EFFECT_PATTERNS):
        add_finding(Finding(
            id=f"dsh-{len(findings)+1:03d}",
            category="dead-letter-gap",
            severity="medium",
            confidence="medium",
            title="No visible dead-letter / poison handling signal in a repo with async side effects",
            path=".",
            line=1,
            evidence=["message / handler signals detected", "no DLQ / dead-letter keyword found repo-wide"],
            recommendation="Add an explicit failed-message holding path or document where poison messages go.",
            merge_gate="warn-only",
        ))

    if relevant_signals > 0 and has_any(joined, SIDE_EFFECT_PATTERNS) and not repo_flags["event_versioning"]:
        add_finding(Finding(
            id=f"dsh-{len(findings)+1:03d}",
            category="event-contract-gap",
            severity="medium",
            confidence="low",
            title="No clear event versioning signal was detected",
            path=".",
            line=1,
            evidence=["event / publish signals detected", "no obvious version field or version marker found repo-wide"],
            recommendation="Version integration events explicitly instead of relying on drift-prone payload memory.",
            merge_gate="warn-only",
        ))

    if relevant_signals > 0 and has_any(joined, SIDE_EFFECT_PATTERNS) and not repo_flags["observability"]:
        add_finding(Finding(
            id=f"dsh-{len(findings)+1:03d}",
            category="observability-gap",
            severity="low",
            confidence="low",
            title="No clear correlation / trace signal was detected around distributed side effects",
            path=".",
            line=1,
            evidence=["side-effect signals detected", "no obvious trace_id / correlation_id / telemetry signal found repo-wide"],
            recommendation="Add correlation identifiers and effect-path telemetry before debugging production duplication or loss becomes guesswork.",
            merge_gate="warn-only",
        ))

    add_tool_findings(findings, tool_runs)
    verdict, summary_line = infer_verdict(findings, repo_flags, relevant_signals)
    scan_blockers = [run.summary for run in tool_runs if run.status == "failed"]
    output = {
        "schema_version": "1.0",
        "skill": "distributed-side-effect-hardgate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo),
        "overall_verdict": verdict,
        "summary_line": summary_line,
        "surface_source_note": surface_source_note,
        "surface_note": surface_note,
        "language_profile": dict(language_counter),
        "coverage": {
            "files_scanned": len(files),
            "relevant_files": relevant_files,
            "relevant_signals": relevant_signals,
        },
        "severity_counts": severity_counts(findings),
        "scan_blockers": scan_blockers,
        "repo_flags": repo_flags,
        "tool_runs": [asdict(item) for item in tool_runs],
        "findings": [asdict(f) for f in findings],
    }
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Repository root to scan")
    parser.add_argument("--out", required=True, help="Path to write summary JSON")
    parser.add_argument("--report-out", default=None, help="Optional explicit human report output path")
    parser.add_argument("--agent-brief-out", default=None, help="Optional explicit agent brief output path")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if not repo.exists():
        print(f"Repository does not exist: {repo}", file=sys.stderr)
        return 2

    data = scan(repo)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_path = Path(args.report_out).resolve() if args.report_out else out.with_name("distributed-side-effect-report.md")
    brief_path = Path(args.agent_brief_out).resolve() if args.agent_brief_out else out.with_name("distributed-side-effect-agent-brief.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_human_report(data) + "\n", encoding="utf-8")
    brief_path.write_text(render_agent_brief(data), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
