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
import os
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

TEXT_EXTS = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".kt", ".kts",
    ".rb", ".php", ".cs", ".rs", ".json", ".yaml", ".yml", ".md", ".toml", ".ini",
}

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "dist", "build",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".turbo", ".next",
    ".idea", ".vscode", "coverage", ".repo-harness",
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

STATE_MUTATION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [r"\b(commit|save|insert|update|delete|upsert|write)\b"]
]


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
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d != "skills"]
        for name in files:
            path = Path(current_root) / name
            if path.suffix.lower() in TEXT_EXTS:
                yield path


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


def scan(repo: Path) -> dict:
    files = list(iter_files(repo))
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

    verdict, summary_line = infer_verdict(findings, repo_flags, relevant_signals)
    output = {
        "schema_version": "1.0",
        "skill": "distributed-side-effect-hardgate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo),
        "overall_verdict": verdict,
        "summary_line": summary_line,
        "language_profile": dict(language_counter),
        "coverage": {
            "files_scanned": len(files),
            "relevant_files": relevant_files,
            "relevant_signals": relevant_signals,
        },
        "severity_counts": severity_counts(findings),
        "scan_blockers": [],
        "repo_flags": repo_flags,
        "findings": [asdict(f) for f in findings],
    }
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Repository root to scan")
    parser.add_argument("--out", required=True, help="Path to write summary JSON")
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
