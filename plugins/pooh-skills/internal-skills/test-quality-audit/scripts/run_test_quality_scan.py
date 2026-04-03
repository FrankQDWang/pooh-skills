#!/usr/bin/env python3
"""Deterministic test governance audit."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

RUNTIME_BIN = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN))

from standard_audit_utils import iter_text_files  # noqa: E402
from standard_audit_utils import describe_surface_source  # noqa: E402
from standard_audit_utils import first_party_text_files  # noqa: E402
from standard_audit_utils import foreign_runtime_text_files  # noqa: E402
from standard_audit_utils import format_surface_note  # noqa: E402
from standard_audit_utils import package_managers  # noqa: E402
from standard_audit_utils import read_text  # noqa: E402
from standard_audit_utils import rel  # noqa: E402
from standard_audit_utils import surface_source  # noqa: E402
from standard_audit_utils import write_json  # noqa: E402
from standard_audit_utils import write_text  # noqa: E402

SCHEMA_VERSION = "1.0"
CATEGORY_TITLES = {
    "ci-test-gate": "CI Test Gate",
    "placeholder-test-quality": "Placeholder Test Quality",
    "skip-retry-governance": "Skip and Retry Governance",
    "mock-discipline": "Mock Discipline",
    "failure-path-evidence": "Failure-Path Evidence",
}
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}
TEST_SIGNAL_RE = re.compile(r"(?im)\b(?:pytest|unittest|vitest|jest|playwright|pnpm\s+test|npm\s+test|uv\s+run\s+pytest|python\s+-m\s+pytest)\b")
PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*assert\s+True\s*$"),
    re.compile(r"^\s*assert\s+1\s*==\s*1\s*$"),
    re.compile(r"^\s*self\.assertTrue\(\s*True\s*\)\s*$"),
    re.compile(r"^\s*expect\(\s*true\s*\)\.toBe\(\s*true\s*\)\s*;?\s*$", re.IGNORECASE),
    re.compile(r"^\s*expect\(\s*1\s*\)\.toBe\(\s*1\s*\)\s*;?\s*$", re.IGNORECASE),
    re.compile(r"\b(?:it|test)\.todo\s*\(", re.IGNORECASE),
)
SKIP_RETRY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"pytest\.mark\.(?:skip|skipif|xfail)"),
    re.compile(r"@unittest\.skip"),
    re.compile(r"\b(?:it|test|describe)\.skip\s*\(", re.IGNORECASE),
    re.compile(r"\bretries\s*:\s*\d+", re.IGNORECASE),
    re.compile(r"\b(?:pytest\.mark\.flaky|@flaky|reruns\s*=)"),
)
INTERNAL_MOCK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bmocker\.patch\s*\("),
    re.compile(r"\bmonkeypatch\.setattr\s*\("),
    re.compile(r"\bpatch(?:\.object)?\s*\("),
    re.compile(r"\b(?:jest|vi)\.mock\s*\(", re.IGNORECASE),
    re.compile(r"\b(?:jest|vi)\.spyOn\s*\(", re.IGNORECASE),
)
BOUNDARY_HINT_RE = re.compile(r"\b(?:requests|httpx|axios|fetch|msw|respx|nock|redis|s3|smtp|stripe|twilio)\b", re.IGNORECASE)
FAILURE_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bpytest\.raises\s*\("),
    re.compile(r"\bassertRaises\s*\("),
    re.compile(r"\bexpect\([^)]*\)\.(?:toThrow|rejects)\b", re.IGNORECASE),
    re.compile(r"\btoThrow\s*\(", re.IGNORECASE),
    re.compile(r"\braises?\s*=", re.IGNORECASE),
)
CI_CANDIDATE_FILES = (
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
)


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
    parser = argparse.ArgumentParser(description="Run test quality audit")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--agent-brief-out", required=True)
    return parser.parse_args(argv)


def is_test_file(path: Path, repo: Path) -> bool:
    relative = rel(path, repo)
    name = path.name.lower()
    parts = [part.lower() for part in Path(relative).parts]
    if any(part in {"tests", "__tests__", "spec", "specs"} for part in parts):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return any(token in name for token in (".test.", ".spec."))


def category_entry(category_id: str, state: str, confidence: str, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": category_id,
        "title": CATEGORY_TITLES[category_id],
        "state": state,
        "confidence": confidence,
        "evidence": evidence[:8],
        "notes": notes,
    }


def ci_config_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in first_party_text_files(repo, suffixes={".yml", ".yaml"}):
        relative = rel(path, repo)
        if relative.startswith(".github/workflows/"):
            files.append(path)
        elif relative == ".circleci/config.yml":
            files.append(path)
        elif relative in CI_CANDIDATE_FILES:
            files.append(path)
    unique: dict[str, Path] = {str(path): path for path in files}
    return list(unique.values())


def collect_repo_surface(repo: Path) -> tuple[list[Path], list[Path]]:
    source_files: list[Path] = []
    test_files: list[Path] = []
    for path in iter_text_files(repo, suffixes=SOURCE_EXTS):
        if is_test_file(path, repo):
            test_files.append(path)
        else:
            source_files.append(path)
    return source_files, test_files


def collect_foreign_runtime_surface(repo: Path) -> tuple[list[Path], list[Path]]:
    source_files: list[Path] = []
    test_files: list[Path] = []
    for path in foreign_runtime_text_files(repo, suffixes=SOURCE_EXTS):
        if is_test_file(path, repo):
            test_files.append(path)
        else:
            source_files.append(path)
    return source_files, test_files


def first_hit(path: Path, repo: Path, pattern: re.Pattern[str]) -> tuple[str, int, str] | None:
    for line_no, line in enumerate(read_text(path).splitlines(), start=1):
        if pattern.search(line):
            return rel(path, repo), line_no, line.strip()
    return None


def collect_ci_gate(repo: Path, ci_files: list[Path]) -> tuple[list[str], int]:
    evidence: list[str] = []
    hits = 0
    for path in ci_files:
        text = read_text(path)
        for line_no, line in enumerate(text.splitlines(), start=1):
            if TEST_SIGNAL_RE.search(line):
                hits += 1
                evidence.append(f"{rel(path, repo)}:{line_no} {line.strip()[:160]}")
    if hits == 0:
        if ci_files:
            evidence.append("CI config files exist, but no explicit test gate signal was found in them.")
        else:
            evidence.append("No supported CI config file exposing a test gate was found.")
    return evidence[:8], hits


def scan_test_files(repo: Path, test_files: list[Path]) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]], list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    placeholder_hits: list[tuple[str, int, str]] = []
    skip_retry_hits: list[tuple[str, int, str]] = []
    internal_mock_hits: list[tuple[str, int, str]] = []
    failure_hits: list[tuple[str, int, str]] = []

    for path in test_files:
        for line_no, line in enumerate(read_text(path).splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if any(pattern.search(stripped) for pattern in PLACEHOLDER_PATTERNS):
                placeholder_hits.append((rel(path, repo), line_no, stripped[:160]))
            if any(pattern.search(stripped) for pattern in SKIP_RETRY_PATTERNS):
                skip_retry_hits.append((rel(path, repo), line_no, stripped[:160]))
            if any(pattern.search(stripped) for pattern in INTERNAL_MOCK_PATTERNS) and not BOUNDARY_HINT_RE.search(stripped):
                internal_mock_hits.append((rel(path, repo), line_no, stripped[:160]))
            if any(pattern.search(stripped) for pattern in FAILURE_PATH_PATTERNS):
                failure_hits.append((rel(path, repo), line_no, stripped[:160]))

    return placeholder_hits[:12], skip_retry_hits[:12], internal_mock_hits[:12], failure_hits[:12]


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {level: 0 for level in ("critical", "high", "medium", "low")}
    for finding in findings:
        counts[finding.severity] += 1
    return counts


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


def build_summary_line(verdict: str, categories: dict[str, str]) -> str:
    if verdict == "not-applicable":
        return "No Python or TypeScript code or test surface was found for test-quality auditing."
    if verdict == "scan-blocked":
        return "The audit could not complete a required local test-quality scan truthfully."
    if categories["ci-test-gate"] == "watch" and categories["failure-path-evidence"] == "watch":
        return "The repo lacks both a trustworthy CI test gate and visible failure-path evidence."
    if categories["placeholder-test-quality"] == "watch":
        return "Placeholder or tautological tests are inflating confidence without proving behavior."
    if categories["skip-retry-governance"] == "watch":
        return "Skip, xfail, or retry usage is becoming part of the normal test story."
    if categories["mock-discipline"] == "watch":
        return "The suite leans heavily on internal mocking, which weakens behavior-level confidence."
    if categories["failure-path-evidence"] == "watch":
        return "The suite exercises happy paths but gives little proof that failures are tested deliberately."
    return "The repo shows a real CI test gate without obvious placeholder tests, skip or retry drift, or missing failure-path evidence."


def top_actions(findings: list[Finding], category_states: dict[str, str]) -> list[str]:
    actions: list[str] = []
    if category_states["ci-test-gate"] == "watch":
        actions.append("Put a real automated test command in CI before treating local green runs as trustworthy governance.")
    if category_states["placeholder-test-quality"] == "watch":
        actions.append("Replace placeholder assertions with behavior checks that can actually fail for the right reason.")
    if category_states["skip-retry-governance"] == "watch":
        actions.append("Review skip, xfail, and retry usage and remove the ones that are masking unresolved instability.")
    if category_states["mock-discipline"] == "watch":
        actions.append("Trim internal-logic mocking and exercise real behavior or boundary adapters more directly.")
    if category_states["failure-path-evidence"] == "watch":
        actions.append("Add explicit failure-path tests so the suite proves how the system behaves when things go wrong.")
    if not actions and not findings:
        actions.append("Preserve the current test-governance posture and keep CI, failure-path evidence, and placeholder-test discipline intact.")
    return actions[:3]


def surface_note_from_summary(summary: dict[str, object]) -> str:
    coverage = summary.get("coverage") or {}
    first_party_total = (
        int(coverage.get("source_files_detected", 0) or 0)
        + int(coverage.get("test_files_scanned", 0) or 0)
        + int(coverage.get("ci_configs_scanned", 0) or 0)
    )
    foreign_runtime_total = (
        int(coverage.get("foreign_runtime_source_files_excluded", 0) or 0)
        + int(coverage.get("foreign_runtime_test_files_excluded", 0) or 0)
    )
    return format_surface_note(
        first_party_count=first_party_total,
        foreign_runtime_excluded=foreign_runtime_total,
        source=str(coverage.get("surface_source") or "git-index"),
    )


def render_report(summary: dict[str, object]) -> str:
    lines = [
        "# Test Quality Audit Report",
        "",
        "## 1. Executive summary",
        f"- overall_verdict: `{summary['overall_verdict']}`",
        f"- summary_line: `{summary['summary_line']}`",
        f"- repo_scope: `{summary['repo_scope']}`",
        f"- package_managers: `{', '.join(summary.get('package_managers') or ['none'])}`",
        "",
        "## 2. Scan surface",
        f"- note: `{surface_note_from_summary(summary)}`",
        f"- source: `{describe_surface_source(Path(str(summary['repo_root'])))}`",
        "",
        "## 3. Category states",
        "",
    ]
    for category in summary["categories"]:
        lines.extend([
            f"### {category['title']}",
            f"- state: `{category['state']}`",
            f"- confidence: `{category['confidence']}`",
        ])
        for item in category.get("evidence") or []:
            lines.append(f"- evidence: `{item}`")
        if category.get("notes"):
            lines.append(f"- notes: {category['notes']}")
        lines.append("")

    lines.extend(["## 4. Highest-risk findings", ""])
    if not summary["findings"]:
        lines.append("No material test-governance findings were detected from the current local evidence set.")
    else:
        for finding in summary["findings"][:6]:
            lines.extend([
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
            ])

    lines.extend(["## 5. Ordered action queue", ""])
    for action in summary["top_actions"]:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def render_brief(summary: dict[str, object]) -> str:
    lines = [
        "# Test Quality Audit Agent Brief",
        "",
        f"- overall_verdict: `{summary['overall_verdict']}`",
        f"- summary_line: `{summary['summary_line']}`",
        f"- scan_surface: `{surface_note_from_summary(summary)}`",
        "",
        "## Immediate actions",
        "",
    ]
    for action in summary["top_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## Findings", ""])
    if not summary["findings"]:
        lines.append("- No material test-governance findings were detected by the current local evidence set.")
    else:
        for finding in summary["findings"][:6]:
            lines.extend([
                f"### {finding['title']}",
                f"- category: {finding['category']}",
                f"- severity: {finding['severity']}",
                f"- confidence: {finding['confidence']}",
                f"- location: {finding['path']}:{finding['line']}",
                f"- change_shape: {finding['recommended_change_shape']}",
                "",
            ])
    lines.append("")
    return "\n".join(lines)


def build_summary(repo: Path) -> dict[str, object]:
    source_files, test_files = collect_repo_surface(repo)
    foreign_runtime_source_files, foreign_runtime_test_files = collect_foreign_runtime_surface(repo)
    ci_files = ci_config_files(repo)
    surface_mode, _ = surface_source(repo)
    if not source_files and not test_files and not ci_files:
        categories = [
            category_entry(category_id, "not-applicable", "high", ["No Python or TypeScript code or test surface was detected."])
            for category_id in CATEGORY_TITLES
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "skill": "test-quality-audit",
            "status": "not-applicable",
            "verdict": "not-applicable",
            "overall_verdict": "not-applicable",
            "repo_scope": "no-python-or-ts-test-surface",
            "summary": "No Python or TypeScript code or test surface was found for test-quality auditing.",
            "summary_line": "No Python or TypeScript code or test surface was found for test-quality auditing.",
            "package_managers": package_managers(repo),
            "coverage": {
                "source_files_detected": 0,
                "test_files_scanned": 0,
                "ci_configs_scanned": 0,
                "foreign_runtime_source_files_excluded": len(foreign_runtime_source_files),
                "foreign_runtime_test_files_excluded": len(foreign_runtime_test_files),
                "ci_gate_hits": 0,
                "placeholder_hits": 0,
                "skip_retry_hits": 0,
                "internal_mock_hits": 0,
                "failure_path_hits": 0,
                "surface_source": surface_mode,
            },
            "categories": categories,
            "findings": [],
            "top_actions": ["Re-run only after the repository grows Python or TypeScript code or tests that need governance review."],
            "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        }

    ci_evidence, ci_gate_hits = collect_ci_gate(repo, ci_files)
    placeholder_hits, skip_retry_hits, internal_mock_hits, failure_hits = scan_test_files(repo, test_files)

    findings: list[Finding] = []
    if ci_gate_hits == 0:
        path = rel(ci_files[0], repo) if ci_files else ".github/workflows"
        findings.append(
            Finding(
                id="missing-ci-gate-01",
                category="missing-ci-gate",
                severity="high",
                confidence="high" if ci_files else "medium",
                title="No trustworthy CI test gate is visible",
                path=path,
                line=1,
                evidence_summary=ci_evidence[0],
                recommended_change_shape="Add one explicit CI test lane that runs the real repository test command before treating local green runs as enough.",
            )
        )
    if placeholder_hits:
        path, line, evidence = placeholder_hits[0]
        findings.append(
            Finding(
                id="placeholder-test-01",
                category="placeholder-test",
                severity="high",
                confidence="high",
                title="Placeholder or tautological test assertion found",
                path=path,
                line=line,
                evidence_summary=f"`{path}:{line}` uses a placeholder-style assertion: `{evidence}`.",
                recommended_change_shape="Replace placeholder assertions with a behavior check that can fail for the real defect you care about.",
            )
        )
    if skip_retry_hits:
        path, line, evidence = skip_retry_hits[0]
        findings.append(
            Finding(
                id="skip-retry-sprawl-01",
                category="skip-retry-sprawl",
                severity="medium",
                confidence="high",
                title="Skip, xfail, or retry usage is visible in the suite",
                path=path,
                line=line,
                evidence_summary=f"`{path}:{line}` shows skip, xfail, or retry governance drift: `{evidence}`.",
                recommended_change_shape="Review each skip or retry and keep only the ones that are clearly temporary and justified.",
            )
        )
    if len(internal_mock_hits) >= 3:
        path, line, evidence = internal_mock_hits[0]
        findings.append(
            Finding(
                id="internal-mock-drift-01",
                category="internal-mock-drift",
                severity="medium",
                confidence="medium",
                title="Tests lean heavily on internal-logic mocking",
                path=path,
                line=line,
                evidence_summary=f"`{path}:{line}` is part of a broader pattern of repeated internal mocking instead of behavior-level proof: `{evidence}`.",
                recommended_change_shape="Use fewer internal patches and exercise real behavior or explicit boundary adapters where possible.",
            )
        )
    if test_files and not failure_hits:
        path = rel(test_files[0], repo)
        findings.append(
            Finding(
                id="missing-failure-path-evidence-01",
                category="missing-failure-path-evidence",
                severity="medium",
                confidence="medium",
                title="Failure-path evidence is missing from the visible suite",
                path=path,
                line=1,
                evidence_summary="The visible test files do not show common failure-path assertions such as `pytest.raises`, `assertRaises`, or `toThrow`.",
                recommended_change_shape="Add explicit tests for error, rejection, invalid-input, or unhappy-path behavior so the suite proves more than the happy path.",
            )
        )

    categories = [
        category_entry(
            "ci-test-gate",
            "clean" if ci_gate_hits else "watch",
            "high" if ci_files else "medium",
            ci_evidence,
        ),
        category_entry(
            "placeholder-test-quality",
            "not-applicable" if not test_files else ("watch" if placeholder_hits else "clean"),
            "high" if placeholder_hits else "medium",
            [f"{path}:{line} {evidence}" for path, line, evidence in placeholder_hits[:4]]
            or ["No placeholder or tautological test assertions were found in the visible test files."],
        ),
        category_entry(
            "skip-retry-governance",
            "not-applicable" if not test_files else ("watch" if skip_retry_hits else "clean"),
            "high" if skip_retry_hits else "medium",
            [f"{path}:{line} {evidence}" for path, line, evidence in skip_retry_hits[:4]]
            or ["No skip, xfail, or retry pattern was found in the visible test files."],
        ),
        category_entry(
            "mock-discipline",
            "not-applicable" if not test_files else ("watch" if len(internal_mock_hits) >= 3 else "clean"),
            "medium",
            [f"{path}:{line} {evidence}" for path, line, evidence in internal_mock_hits[:4]]
            or ["No repeated internal-logic mocking pattern was found in the visible test files."],
            notes="This skill does not grade browser-boundary mocking for frontend specialists; it only flags broad internal mock drift.",
        ),
        category_entry(
            "failure-path-evidence",
            "not-applicable" if not test_files else ("clean" if failure_hits else "watch"),
            "medium",
            [f"{path}:{line} {evidence}" for path, line, evidence in failure_hits[:4]]
            or ["No explicit failure-path assertion was found in the visible test files."],
            notes="Temporal replay and time-skipping verification remain owned by the durable-agent specialist, not by this category.",
        ),
    ]
    category_states = {str(item["id"]): str(item["state"]) for item in categories}
    verdict = overall_verdict(categories)
    summary_line = build_summary_line(verdict, category_states)
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "test-quality-audit",
        "status": status_for_verdict(verdict),
        "verdict": verdict,
        "overall_verdict": verdict,
        "repo_scope": "repo-test-governance",
        "summary": summary_line,
        "summary_line": summary_line,
        "package_managers": package_managers(repo),
        "coverage": {
            "source_files_detected": len(source_files),
            "test_files_scanned": len(test_files),
            "ci_configs_scanned": len(ci_files),
            "foreign_runtime_source_files_excluded": len(foreign_runtime_source_files),
            "foreign_runtime_test_files_excluded": len(foreign_runtime_test_files),
            "ci_gate_hits": ci_gate_hits,
            "placeholder_hits": len(placeholder_hits),
            "skip_retry_hits": len(skip_retry_hits),
            "internal_mock_hits": len(internal_mock_hits),
            "failure_path_hits": len(failure_hits),
            "surface_source": surface_mode,
        },
        "categories": categories,
        "findings": [item.to_dict() for item in findings[:12]],
        "top_actions": top_actions(findings, category_states),
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
