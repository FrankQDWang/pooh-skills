#!/usr/bin/env python3
"""Heuristic baseline security-posture audit for uv + pnpm repositories."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RUNTIME_BIN = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN))

from standard_audit_utils import any_match  # noqa: E402
from standard_audit_utils import build_summary  # noqa: E402
from standard_audit_utils import category_entry  # noqa: E402
from standard_audit_utils import collect_matches  # noqa: E402
from standard_audit_utils import finding_entry  # noqa: E402
from standard_audit_utils import first_match_location  # noqa: E402
from standard_audit_utils import iter_text_files  # noqa: E402
from standard_audit_utils import render_standard_brief  # noqa: E402
from standard_audit_utils import render_standard_report  # noqa: E402
from standard_audit_utils import write_json  # noqa: E402
from standard_audit_utils import write_text  # noqa: E402

PYTHON_FILE_RE = re.compile(r"\.py$", re.IGNORECASE)
TS_FILE_RE = re.compile(r"\.(ts|tsx|js|jsx)$", re.IGNORECASE)
PYTHON_AUDIT_RE = re.compile(r"(osv-scanner|uv export|dependency[- ]audit|python[- ]dependency[- ]audit)", re.IGNORECASE)
TS_AUDIT_RE = re.compile(r"(pnpm\s+audit|audit-ci|osv-scanner)", re.IGNORECASE)
BANDIT_RE = re.compile(r"\bbandit\b", re.IGNORECASE)
LOCK_DISCIPLINE_RE = re.compile(r"(uv\s+sync\s+--frozen|uv\s+lock|pnpm\s+install\s+--frozen-lockfile|pnpm\s+fetch\s+--frozen-lockfile)", re.IGNORECASE)
IGNORE_RE = re.compile(r"(ignore|allowlist|baseline|skip|audit-level|severity-level)", re.IGNORECASE)
PRIVATE_REGISTRY_RE = re.compile(r"(index-url|extra-index-url|registry=|npm\.pkg\.github\.com|artifactory|verdaccio|private\s+registry)", re.IGNORECASE)
WORKFLOW_SECURITY_RE = re.compile(r"(bandit|audit-ci|pnpm\s+audit|osv-scanner|safety|pip-audit|sarif|upload-artifact)", re.IGNORECASE)

CATEGORY_TITLES = {
    "python-known-vulns": "Python Known Vulnerabilities",
    "ts-known-vulns": "TS / Node Known Vulnerabilities",
    "python-static-security": "Python Static Security",
    "lockfile-install-discipline": "Lockfile and Install Discipline",
    "gate-and-ignore-governance": "Gate and Ignore Governance",
}


def state_for_audit_surface(
    *,
    applicable: bool,
    hits: list[str],
    in_ci: int,
    blocked: bool,
) -> tuple[str, str]:
    if not applicable:
        return "not-applicable", "This dependency surface does not exist in the current repository."
    if blocked:
        return "blocked", "Private registry or lockfile visibility blocks a trustworthy dependency audit."
    if in_ci:
        return "enforced", "A dependency audit signal is visible in CI or workflow definitions."
    if hits:
        return "partial", "A local audit command exists, but CI-visible enforcement is weak or absent."
    return "missing", "No reproducible dependency audit signal was detected."


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Python / TS security posture scan")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--agent-brief-out", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    text_files = list(iter_text_files(repo))
    python_files = [path for path in text_files if PYTHON_FILE_RE.search(path.name)]
    ts_files = [path for path in text_files if TS_FILE_RE.search(path.name)]
    uv_lock = (repo / "uv.lock").exists()
    pnpm_lock = (repo / "pnpm-lock.yaml").exists()
    private_registry = any_match(repo, PRIVATE_REGISTRY_RE, names={"pyproject.toml", "uv.toml", ".npmrc", "package.json"})

    python_audit_hits = collect_matches(repo, PYTHON_AUDIT_RE)
    python_audit_ci = sum(1 for hit in python_audit_hits if ".github/workflows/" in hit)
    ts_audit_hits = collect_matches(repo, TS_AUDIT_RE)
    ts_audit_ci = sum(1 for hit in ts_audit_hits if ".github/workflows/" in hit)
    bandit_hits = collect_matches(repo, BANDIT_RE)
    bandit_ci = sum(1 for hit in bandit_hits if ".github/workflows/" in hit)
    lock_hits = collect_matches(repo, LOCK_DISCIPLINE_RE)
    workflow_hits = collect_matches(repo, WORKFLOW_SECURITY_RE, suffixes={".yml", ".yaml"})
    ignore_hits = collect_matches(repo, IGNORE_RE, names={"pyproject.toml", "package.json", ".bandit", ".npmrc", "audit-ci.json", "audit-ci.jsonc", "uv.toml"})

    applicable = bool(python_files or ts_files or uv_lock or pnpm_lock)
    findings: list[dict[str, object]] = []
    if not applicable:
        categories = [
            category_entry(category_id, title, "not-applicable", "high", ["No Python or TypeScript dependency surface detected."])
            for category_id, title in CATEGORY_TITLES.items()
        ]
        summary = build_summary(
            skill="python-ts-security-posture-audit",
            repo=repo,
            repo_scope="no-python-or-ts-surface",
            coverage={
                "files_scanned": len(text_files),
                "python_surface_files": 0,
                "ts_surface_files": 0,
                "lockfiles_present": 0,
                "workflow_security_entries": 0,
                "ignore_entries": 0,
            },
            categories=categories,
            findings=[],
            top_actions=["Keep baseline security posture work out of the queue until the repo actually carries Python or TypeScript dependency risk."],
            summary_line="No Python or TypeScript dependency surface was detected, so baseline security-posture auditing is not applicable.",
        )
        write_json(Path(args.summary_out), summary)
        write_text(
            Path(args.report_out),
            render_standard_report("Python / TS Security Posture Audit", summary, focus_label="Security Surface"),
        )
        write_text(
            Path(args.agent_brief_out),
            render_standard_brief(
                "Python / TS Security Posture Audit",
                summary,
                target_shape=["Add baseline dependency and static-security gates only after this repo gains Python or TypeScript dependency risk."],
                validation_gates=["Re-run only after Python or TypeScript package management appears in the repo."],
            ),
        )
        return 0

    python_blocked = bool(python_files) and (not uv_lock or private_registry and not python_audit_hits)
    ts_blocked = bool(ts_files) and (not pnpm_lock or private_registry and not ts_audit_hits)

    python_state, python_note = state_for_audit_surface(
        applicable=bool(python_files),
        hits=python_audit_hits,
        in_ci=python_audit_ci,
        blocked=python_blocked,
    )
    ts_state, ts_note = state_for_audit_surface(
        applicable=bool(ts_files),
        hits=ts_audit_hits,
        in_ci=ts_audit_ci,
        blocked=ts_blocked,
    )
    static_state = "enforced" if bandit_ci else "partial" if bandit_hits else "missing"
    lock_state = (
        "blocked"
        if (python_files and not uv_lock) or (ts_files and not pnpm_lock)
        else "enforced"
        if lock_hits and ((not python_files or uv_lock) and (not ts_files or pnpm_lock))
        else "partial"
    )
    ignore_state = "enforced" if workflow_hits and ignore_hits else "partial" if ignore_hits or workflow_hits else "missing"

    if python_state != "enforced" and python_state != "not-applicable":
        loc = first_match_location(repo, PYTHON_AUDIT_RE) or ("pyproject.toml", 1, "No Python dependency-audit signal was detected.")
        findings.append(
            finding_entry(
                "python-known-vulns",
                "high" if python_state == "blocked" else "medium",
                "medium",
                "Python dependency vulnerability auditing is not trustworthy yet",
                loc[0],
                loc[1],
                evidence_summary="The repository does not show a stable Python dependency-audit chain tied to uv lock discipline and CI evidence.",
                recommended_change_shape="Add one reproducible Python dependency-audit gate tied to uv.lock and surface it in CI.",
            )
        )
    if ts_state != "enforced" and ts_state != "not-applicable":
        loc = first_match_location(repo, TS_AUDIT_RE) or ("package.json", 1, "No TS dependency-audit signal was detected.")
        findings.append(
            finding_entry(
                "ts-known-vulns",
                "high" if ts_state == "blocked" else "medium",
                "medium",
                "TS / Node dependency vulnerability auditing is not trustworthy yet",
                loc[0],
                loc[1],
                evidence_summary="The repository does not show a stable pnpm-backed dependency-audit gate that can be reviewed in CI.",
                recommended_change_shape="Add one reproducible TS / Node dependency-audit gate tied to pnpm-lock.yaml and wire it into CI.",
            )
        )
    if static_state != "enforced" and python_files:
        loc = first_match_location(repo, BANDIT_RE) or ("pyproject.toml", 1, "No Python static-security signal was detected.")
        findings.append(
            finding_entry(
                "python-static-security",
                "medium",
                "medium",
                "Python static security scanning is weak or missing",
                loc[0],
                loc[1],
                evidence_summary="The repo has Python code but does not clearly show a Bandit-backed or equivalent static-security gate in CI.",
                recommended_change_shape="Add one reproducible Python static-security scan and keep its scope and ignores reviewable.",
            )
        )
    if lock_state != "enforced":
        loc = first_match_location(repo, LOCK_DISCIPLINE_RE) or ("pyproject.toml", 1, "No frozen-install discipline was detected.")
        findings.append(
            finding_entry(
                "lockfile-install-discipline",
                "high" if lock_state == "blocked" else "medium",
                "high" if lock_state == "blocked" else "medium",
                "Lockfile or frozen-install discipline is not strong enough",
                loc[0],
                loc[1],
                evidence_summary="uv.lock or pnpm-lock.yaml discipline is weak, missing, or not clearly enforced through frozen install paths.",
                recommended_change_shape="Make lockfiles authoritative and keep CI installs frozen or immutable.",
            )
        )
    if ignore_state != "enforced":
        loc = first_match_location(repo, IGNORE_RE) or ("package.json", 1, "No ignore-governance evidence was detected.")
        findings.append(
            finding_entry(
                "gate-and-ignore-governance",
                "medium",
                "medium",
                "Ignore and governance evidence is incomplete",
                loc[0],
                loc[1],
                evidence_summary="Security gate definitions, ignore lists, or artifact retention do not yet look explicit and reviewable.",
                recommended_change_shape="Keep ignore rationale versioned, visible, and tied to the same CI gates that produce security evidence.",
            )
        )

    categories = [
        category_entry(
            "python-known-vulns",
            CATEGORY_TITLES["python-known-vulns"],
            python_state,
            "high" if python_state == "blocked" else "medium",
            [f"{len(python_audit_hits)} Python dependency-audit entries", f"uv.lock present: {uv_lock}"],
            notes=python_note,
        ),
        category_entry(
            "ts-known-vulns",
            CATEGORY_TITLES["ts-known-vulns"],
            ts_state,
            "high" if ts_state == "blocked" else "medium",
            [f"{len(ts_audit_hits)} TS / Node dependency-audit entries", f"pnpm-lock.yaml present: {pnpm_lock}"],
            notes=ts_note,
        ),
        category_entry(
            "python-static-security",
            CATEGORY_TITLES["python-static-security"],
            "not-applicable" if not python_files else static_state,
            "medium",
            [f"{len(bandit_hits)} Bandit or equivalent static-security entries"],
        ),
        category_entry(
            "lockfile-install-discipline",
            CATEGORY_TITLES["lockfile-install-discipline"],
            lock_state,
            "high" if lock_state == "blocked" else "medium",
            [f"uv.lock present: {uv_lock}", f"pnpm-lock.yaml present: {pnpm_lock}", f"{len(lock_hits)} frozen-install entries"],
        ),
        category_entry(
            "gate-and-ignore-governance",
            CATEGORY_TITLES["gate-and-ignore-governance"],
            ignore_state,
            "medium",
            [f"{len(workflow_hits)} workflow security entries", f"{len(ignore_hits)} ignore/baseline entries"],
            notes="This skill is baseline security posture only, not a substitute for full application or infrastructure security review.",
        ),
    ]

    summary = build_summary(
        skill="python-ts-security-posture-audit",
        repo=repo,
        repo_scope="python-ts-security-surface",
        coverage={
            "files_scanned": len(text_files),
            "python_surface_files": len(python_files),
            "ts_surface_files": len(ts_files),
            "lockfiles_present": int(uv_lock) + int(pnpm_lock),
            "workflow_security_entries": len(workflow_hits),
            "ignore_entries": len(ignore_hits),
        },
        categories=categories,
        findings=findings,
        top_actions=[
            "Tie Python and TS dependency auditing to uv.lock and pnpm-lock.yaml rather than ad-hoc local commands.",
            "Keep frozen installs and lockfile ownership explicit before trusting vulnerability counts.",
            "Version control ignore and baseline rationale so blocked or partial security runs stay explainable.",
        ],
        summary_line="Baseline security posture is only trustworthy when lockfiles, dependency audits, static scans, and ignore governance all point at one reviewable CI trail.",
    )

    write_json(Path(args.summary_out), summary)
    write_text(
        Path(args.report_out),
        render_standard_report("Python / TS Security Posture Audit", summary, focus_label="Security Surface"),
    )
    write_text(
        Path(args.agent_brief_out),
        render_standard_brief(
            "Python / TS Security Posture Audit",
            summary,
            target_shape=[
                "Keep Python and TS dependency audits tied to lockfile-backed installs.",
                "Expose one reproducible Python static-security scan when Python code is in scope.",
                "Keep ignore and artifact governance explicit so blocked runs stay interpretable.",
            ],
            validation_gates=[
                "uv.lock and pnpm-lock.yaml are present whenever their language surfaces are present.",
                "Dependency audit and static-security commands are visible in CI rather than local-only scripts.",
                "Ignore or baseline files are reviewable and tied to the same gates that produce findings.",
            ],
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
