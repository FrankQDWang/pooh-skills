#!/usr/bin/env python3
"""Deterministic secrets and hardcoded-credential audit."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

RUNTIME_BIN = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN))

from standard_audit_utils import iter_text_files  # noqa: E402
from standard_audit_utils import package_managers  # noqa: E402
from standard_audit_utils import read_text  # noqa: E402
from standard_audit_utils import rel  # noqa: E402
from standard_audit_utils import write_json  # noqa: E402
from standard_audit_utils import write_text  # noqa: E402

SCHEMA_VERSION = "1.0"
CATEGORY_TITLES = {
    "working-tree-secrets": "Working-Tree Secret Exposure",
    "git-history-secrets": "Git-History Secret Exposure",
    "hardcoded-credential-material": "Hardcoded Credential Material",
    "ignore-discipline": "Ignore Discipline",
}
SECRET_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("aws-access-key", "critical", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", "critical", re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", "critical", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe-live-key", "critical", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b")),
    ("private-key", "critical", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    (?:
      ["']?(?:password|passwd|pwd|secret|secret_key|api[_-]?key|auth[_-]?token|token|client_secret|access[_-]?key)["']?
      \s*[:=]\s*
      ["']([^"'\n]{8,})["']
    )
    """
)
CREDENTIAL_URL_RE = re.compile(r"(?i)\b(?:postgres|mysql|mongodb|redis|amqp|https?)://[^/\s:@]+:[^/\s@]{6,}@")
SENSITIVE_FILE_RE = re.compile(r"(?i)(^|/)(?:\.env(?:\.[^/]+)?|.*\.(?:pem|key|p12|pfx)|id_rsa|id_dsa)$")
PLACEHOLDER_RE = re.compile(r"(?i)(changeme|example|sample|dummy|placeholder|test[-_]?only|notasecret|fake|your[_-]|<[^>]+>|\$\{[^}]+\})")
IGNORE_PATTERNS = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa", "id_dsa")
HISTORY_REGEX = r"(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|gh[pous]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk_live_[A-Za-z0-9]{16,}|BEGIN [A-Z ]*PRIVATE KEY)"


@dataclass(frozen=True)
class Finding:
    id: str
    category: str
    severity: str
    confidence: str
    title: str
    path: str
    line: int
    evidence_summary: str
    recommended_change_shape: str
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "title": self.title,
            "path": self.path,
            "line": self.line,
            "evidence_summary": self.evidence_summary,
            "recommended_change_shape": self.recommended_change_shape,
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run secrets and hardcode audit")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--agent-brief-out", required=True)
    return parser.parse_args(argv)


def redact_preview(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= 8:
        return "[redacted]"
    return f"{stripped[:4]}…{stripped[-4:]}"


def is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.search(value))


def iter_secret_candidate_files(repo: Path) -> list[Path]:
    candidates = {path for path in iter_text_files(repo)}
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        relative_path = rel(path, repo)
        if relative_path.startswith(".git/") or "/.git/" in f"/{relative_path}":
            continue
        if SENSITIVE_FILE_RE.search(relative_path):
            candidates.add(path)
    return sorted(candidates)


def collect_worktree_findings(repo: Path) -> tuple[list[Finding], list[Finding], list[str], int]:
    secret_findings: list[Finding] = []
    credential_findings: list[Finding] = []
    sensitive_files: list[str] = []
    files_scanned = 0

    for path in iter_secret_candidate_files(repo):
        files_scanned += 1
        relative_path = rel(path, repo)
        if SENSITIVE_FILE_RE.search(relative_path):
            sensitive_files.append(relative_path)
        text = read_text(path)
        if not text:
            continue
        scan_credential_literals = path.suffix.lower() not in {".md", ".mdx", ".rst", ".txt", ".adoc"}
        for line_no, line in enumerate(text.splitlines(), start=1):
            for secret_name, severity, pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                value = match.group(0)
                if is_placeholder(value):
                    continue
                secret_findings.append(
                    Finding(
                        id=f"secret-material-{len(secret_findings) + 1:02d}",
                        category="secret-material",
                        severity=severity,
                        confidence="high",
                        title=f"High-signal secret material matched `{secret_name}`",
                        path=relative_path,
                        line=line_no,
                        evidence_summary=f"Matched high-signal secret material in `{relative_path}:{line_no}` with redacted preview `{redact_preview(value)}`.",
                        recommended_change_shape="Remove the secret from the working tree, rotate or revoke it, and replace the literal with environment or secret-manager indirection.",
                    )
                )
                break

            credential_match = CREDENTIAL_ASSIGNMENT_RE.search(line) if scan_credential_literals else None
            if credential_match:
                value = credential_match.group(1).strip()
                if value and not is_placeholder(value):
                    credential_findings.append(
                        Finding(
                            id=f"credential-literal-{len(credential_findings) + 1:02d}",
                            category="credential-literal",
                            severity="high",
                            confidence="medium",
                            title="Hardcoded credential literal is embedded in code or config",
                            path=relative_path,
                            line=line_no,
                            evidence_summary=f"`{relative_path}:{line_no}` stores a credential-like literal with redacted preview `{redact_preview(value)}`.",
                            recommended_change_shape="Move the credential behind environment or secret-manager boundaries and leave only a config key or indirection in source control.",
                        )
                    )
            elif scan_credential_literals and CREDENTIAL_URL_RE.search(line):
                credential_findings.append(
                    Finding(
                        id=f"credential-literal-{len(credential_findings) + 1:02d}",
                        category="credential-literal",
                        severity="high",
                        confidence="medium",
                        title="Connection string appears to embed credentials inline",
                        path=relative_path,
                        line=line_no,
                        evidence_summary=f"`{relative_path}:{line_no}` contains a credential-bearing URL shape.",
                        recommended_change_shape="Move connection credentials out of inline URLs and inject them through environment or secret-manager configuration.",
                    )
                )

    return secret_findings[:12], credential_findings[:12], sorted(set(sensitive_files))[:12], files_scanned


def sensitive_files_in_repo(repo: Path) -> list[str]:
    matches: list[str] = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(repo).as_posix()
        if "/.git/" in f"/{relative_path}" or relative_path.startswith(".git/"):
            continue
        if SENSITIVE_FILE_RE.search(relative_path):
            matches.append(relative_path)
    return sorted(set(matches))[:12]


def git_history_matches(repo: Path) -> tuple[bool, list[str], list[Finding]]:
    git_dir = repo / ".git"
    if not git_dir.exists():
        return False, ["This checkout does not expose `.git`, so history leakage could not be verified."], []
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False, ["Git history is unavailable in this checkout, so past secret leakage remains a trust gap."], []
    if inside.stdout.strip() != "true":
        return False, ["Git history is unavailable in this checkout, so past secret leakage remains a trust gap."], []

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--all",
                "-G",
                HISTORY_REGEX,
                "--format=%H",
                "--name-only",
                "--max-count",
                "6",
            ],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.CalledProcessError:
        return False, ["Git history scan failed before it could prove whether past secret leakage exists."], [
            Finding(
                id="scan-blocker-01",
                category="scan-blocker",
                severity="medium",
                confidence="low",
                title="Git history scan failed before it completed",
                path=".git",
                line=1,
                evidence_summary="The audit could not complete its git-history query cleanly, so history leakage remains unresolved.",
                recommended_change_shape="Repair git-history access or rerun this audit from a full clone before calling the repo clean.",
            )
        ]

    commits: list[str] = []
    files: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"[0-9a-f]{40}", line):
            commits.append(line)
        elif not line.startswith(".repo-harness/"):
            files.append(line)
    if not commits:
        return True, ["No high-signal secret material was matched in accessible git history."], []

    evidence = [f"commit {commit[:12]}" for commit in commits[:4]]
    if files:
        evidence.extend(f"file {path}" for path in files[:4])
    history_findings = [
        Finding(
            id=f"history-secret-trace-{idx + 1:02d}",
            category="history-secret-trace",
            severity="high",
            confidence="medium",
            title="Git history still shows high-signal secret material",
            path=files[idx] if idx < len(files) else ".git-history",
            line=1,
            evidence_summary=f"Accessible git history matched high-signal secret patterns in commit `{commit[:12]}`.",
            recommended_change_shape="Review whether the leaked material still needs rotation or revoke-first handling, then decide whether history rewrite is required.",
            notes="History-only evidence still matters even if the current working tree is clean.",
        )
        for idx, commit in enumerate(commits[:4])
    ]
    return True, evidence[:8], history_findings


def parse_gitignore(repo: Path) -> set[str]:
    path = repo / ".gitignore"
    if not path.exists():
        return set()
    patterns: set[str] = set()
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.add(line)
    return patterns


def collect_ignore_findings(repo: Path, sensitive_files: list[str]) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    evidence: list[str] = []
    patterns = parse_gitignore(repo)
    missing_patterns = [pattern for pattern in IGNORE_PATTERNS if pattern not in patterns]
    if missing_patterns:
        evidence.append(f"missing core ignore patterns: {', '.join(missing_patterns)}")
    if sensitive_files:
        evidence.append(f"sensitive-looking files present: {', '.join(sensitive_files[:4])}")
    if missing_patterns and sensitive_files:
        findings.append(
            Finding(
                id="ignore-discipline-gap-01",
                category="ignore-discipline-gap",
                severity="high",
                confidence="high",
                title="Sensitive-looking files exist without matching core `.gitignore` coverage",
                path=sensitive_files[0],
                line=1,
                evidence_summary=f"The repo contains sensitive-looking files and `.gitignore` is missing core coverage for {', '.join(missing_patterns[:4])}.",
                recommended_change_shape="Add explicit ignore coverage for secret-bearing files and stop relying on local convention or luck.",
            )
        )
    elif missing_patterns:
        findings.append(
            Finding(
                id="ignore-discipline-gap-01",
                category="ignore-discipline-gap",
                severity="medium",
                confidence="medium",
                title="Core `.gitignore` coverage for secret-bearing files is incomplete",
                path=".gitignore",
                line=1,
                evidence_summary=f"`.gitignore` does not yet cover some common secret-bearing patterns: {', '.join(missing_patterns[:4])}.",
                recommended_change_shape="Add a small explicit ignore baseline for env files and key material before the next secret leak turns into tracked debt.",
            )
        )
    elif patterns:
        evidence.append("`.gitignore` covers the common env and key-material patterns checked by this audit.")
    else:
        evidence.append("No `.gitignore` file was found.")
    return findings, evidence[:8]


def category_entry(category_id: str, state: str, confidence: str, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": category_id,
        "title": CATEGORY_TITLES[category_id],
        "state": state,
        "confidence": confidence,
        "evidence": evidence[:8],
        "notes": notes,
    }


def overall_verdict(categories: list[dict[str, object]]) -> str:
    states = [str(item["state"]) for item in categories]
    if states and all(state == "not-applicable" for state in states):
        return "not-applicable"
    if any(state == "blocked" for state in states):
        return "scan-blocked"
    if any(state == "watch" for state in states):
        return "watch"
    return "clean"


def status_for_verdict(verdict: str) -> str:
    if verdict == "scan-blocked":
        return "blocked"
    if verdict == "not-applicable":
        return "not-applicable"
    return "complete"


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {level: 0 for level in ("critical", "high", "medium", "low")}
    for finding in findings:
        counts[finding.severity] += 1
    return counts


def build_summary_line(verdict: str, findings: list[Finding], history_available: bool) -> str:
    if verdict == "not-applicable":
        return "No meaningful text or config surface was found for secrets-and-hardcode auditing."
    if verdict == "scan-blocked":
        return "The audit could not complete a required secrets or history check truthfully."
    if verdict == "clean":
        return "No high-signal secret exposure or ignore-discipline gap was detected in the current local evidence set."
    if any(item.category == "secret-material" for item in findings):
        return "Active working-tree secret exposure needs immediate removal and rotation review."
    if any(item.category == "history-secret-trace" for item in findings):
        return "The working tree may be cleaner than git history; leaked material still needs rotation or rewrite review."
    if not history_available:
        return "The repo does not expose git history here, so secret-hygiene confidence stays incomplete."
    return "Credential literals or ignore-discipline gaps still need cleanup before this repo can be called clean."


def top_actions(findings: list[Finding], history_available: bool) -> list[str]:
    actions: list[str] = []
    if any(item.category == "secret-material" for item in findings):
        actions.append("Remove active secret material from the working tree and rotate or revoke it before debating cleanup cosmetics.")
    if any(item.category == "history-secret-trace" for item in findings):
        actions.append("Review whether leaked material in git history still needs rotation, revoke-first handling, or explicit history-rewrite review.")
    elif not history_available:
        actions.append("Run this audit from a full git clone before calling the repository clean on secret history.")
    if any(item.category == "credential-literal" for item in findings):
        actions.append("Move hardcoded credential literals behind environment or secret-manager boundaries and leave only indirection in source control.")
    if any(item.category == "ignore-discipline-gap" for item in findings):
        actions.append("Tighten `.gitignore` coverage for env files and key material so future leaks do not become tracked debt.")
    if not actions:
        actions.append("Preserve the current secret-hygiene posture and keep redaction discipline in future code review.")
    return actions[:3]


def render_report(summary: dict[str, object]) -> str:
    lines = [
        "# Secrets and Hardcode Audit Report",
        "",
        "## 1. Executive summary",
        f"- overall_verdict: `{summary['overall_verdict']}`",
        f"- summary_line: `{summary['summary_line']}`",
        f"- repo_scope: `{summary['repo_scope']}`",
        f"- package_managers: `{', '.join(summary.get('package_managers') or ['none'])}`",
        "",
        "## 2. Category states",
        "",
    ]
    for category in summary["categories"]:
        lines.extend(
            [
                f"### {category['title']}",
                f"- state: `{category['state']}`",
                f"- confidence: `{category['confidence']}`",
            ]
        )
        for item in category.get("evidence") or []:
            lines.append(f"- evidence: `{item}`")
        if category.get("notes"):
            lines.append(f"- notes: {category['notes']}")
        lines.append("")

    lines.extend(["## 3. Highest-risk findings", ""])
    if not summary["findings"]:
        lines.append("No material secret-hygiene findings were detected from the current local evidence set.")
    else:
        for finding in summary["findings"][:6]:
            lines.extend(
                [
                    f"### {finding['title']}",
                    f"- category: `{finding['category']}`",
                    f"- severity: `{finding['severity']}`",
                    f"- confidence: `{finding['confidence']}`",
                    f"- location: `{finding['path']}:{finding['line']}`",
                    "",
                    str(finding["evidence_summary"]),
                    "",
                    f"Recommended shape: {finding['recommended_change_shape']}",
                    "",
                ]
            )

    lines.extend(["## 4. Ordered action queue", ""])
    for action in summary["top_actions"]:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def render_brief(summary: dict[str, object]) -> str:
    lines = [
        "# Secrets and Hardcode Audit Agent Brief",
        "",
        f"- overall_verdict: `{summary['overall_verdict']}`",
        f"- summary_line: `{summary['summary_line']}`",
        "",
        "## Immediate actions",
        "",
    ]
    for action in summary["top_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## Findings", ""])
    if not summary["findings"]:
        lines.append("- No material secret-hygiene findings were detected by the current local evidence set.")
    else:
        for finding in summary["findings"][:6]:
            lines.extend(
                [
                    f"### {finding['title']}",
                    f"- category: {finding['category']}",
                    f"- severity: {finding['severity']}",
                    f"- confidence: {finding['confidence']}",
                    f"- location: {finding['path']}:{finding['line']}",
                    f"- change_shape: {finding['recommended_change_shape']}",
                    "",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def build_summary(repo: Path) -> dict[str, object]:
    candidate_files = iter_secret_candidate_files(repo)
    if not candidate_files:
        categories = [
            category_entry(category_id, "not-applicable", "high", ["No text or config files were detected."])
            for category_id in CATEGORY_TITLES
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "skill": "secrets-and-hardcode-audit",
            "status": "not-applicable",
            "verdict": "not-applicable",
            "overall_verdict": "not-applicable",
            "repo_scope": "no-text-or-config-surface",
            "summary": "No meaningful text or config surface was found for secrets-and-hardcode auditing.",
            "summary_line": "No meaningful text or config surface was found for secrets-and-hardcode auditing.",
            "package_managers": package_managers(repo),
            "coverage": {
                "files_scanned": 0,
                "worktree_secret_hits": 0,
                "hardcoded_credential_hits": 0,
                "history_secret_hits": 0,
                "sensitive_file_hits": 0,
                "git_history_available": False,
            },
            "categories": categories,
            "findings": [],
            "top_actions": ["Re-run only after the repository gains a text or config surface that can leak secrets or hardcoded credentials."],
            "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        }

    secret_findings, credential_findings, _, files_scanned = collect_worktree_findings(repo)
    sensitive_files = sensitive_files_in_repo(repo)
    git_available, history_evidence, history_findings = git_history_matches(repo)
    ignore_findings, ignore_evidence = collect_ignore_findings(repo, sensitive_files)

    findings = secret_findings + credential_findings + history_findings + ignore_findings
    worktree_state = "watch" if secret_findings else "clean"
    credential_state = "watch" if credential_findings else "clean"
    history_state = "watch" if history_findings or not git_available else "clean"
    ignore_state = "watch" if ignore_findings else "clean"

    categories = [
        category_entry(
            "working-tree-secrets",
            worktree_state,
            "high" if secret_findings else "medium",
            [item.evidence_summary for item in secret_findings[:4]] or ["No high-signal secret material was found in the current working tree."],
        ),
        category_entry(
            "git-history-secrets",
            history_state,
            "medium" if git_available else "low",
            history_evidence,
            notes="History-only evidence still matters operationally even when the current working tree looks cleaner." if history_findings else "",
        ),
        category_entry(
            "hardcoded-credential-material",
            credential_state,
            "medium",
            [item.evidence_summary for item in credential_findings[:4]] or ["No credential-like literals were found beyond placeholder patterns."],
        ),
        category_entry(
            "ignore-discipline",
            ignore_state,
            "high" if ignore_findings else "medium",
            ignore_evidence or ["No ignore-discipline gap was detected from the current evidence set."],
        ),
    ]

    verdict = overall_verdict(categories)
    summary_line = build_summary_line(verdict, findings, git_available)
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "secrets-and-hardcode-audit",
        "status": status_for_verdict(verdict),
        "verdict": verdict,
        "overall_verdict": verdict,
        "repo_scope": "repo-secret-hygiene",
        "summary": summary_line,
        "summary_line": summary_line,
        "package_managers": package_managers(repo),
        "coverage": {
            "files_scanned": files_scanned,
            "worktree_secret_hits": len(secret_findings),
            "hardcoded_credential_hits": len(credential_findings),
            "history_secret_hits": len(history_findings),
            "sensitive_file_hits": len(sensitive_files),
            "git_history_available": git_available,
        },
        "categories": categories,
        "findings": [item.to_dict() for item in findings[:12]],
        "top_actions": top_actions(findings, git_available),
        "severity_counts": severity_counts(findings[:12]),
    }


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    summary = build_summary(repo)
    summary["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summary["repo_root"] = str(repo)
    write_json(Path(args.summary_out), summary)
    write_text(Path(args.report_out), render_report(summary))
    write_text(Path(args.agent_brief_out), render_brief(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
