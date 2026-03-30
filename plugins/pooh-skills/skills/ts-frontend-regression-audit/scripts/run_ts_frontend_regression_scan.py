#!/usr/bin/env python3
"""Heuristic browser-regression audit for TypeScript frontend repositories."""

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

FRONTEND_FILE_RE = re.compile(r"\.(tsx?|jsx?|html|css|scss|vue|svelte)$", re.IGNORECASE)
REAL_BROWSER_RE = re.compile(r"(playwright|browser\s*:\s*{|browserMode|@playwright/test|@vitest/browser)", re.IGNORECASE)
JSDOM_ONLY_RE = re.compile(r"(jsdom|happy-dom)", re.IGNORECASE)
MSW_RE = re.compile(r"(msw|setupServer|setupWorker|rest\.(get|post|put|patch|delete)|http\.(get|post|put|patch|delete))", re.IGNORECASE)
INTERNAL_MOCK_RE = re.compile(r"(jest\.mock|vi\.mock|mockImplementation|mockResolvedValue)", re.IGNORECASE)
AXE_RE = re.compile(r"(@axe-core/playwright|axe\()", re.IGNORECASE)
VISUAL_RE = re.compile(r"(toHaveScreenshot|snapshotPathTemplate|percy|chromatic|compareSnapshot)", re.IGNORECASE)
WORKFLOW_RE = re.compile(r"(playwright|vitest|upload-artifact|trace|screenshot|retries:)", re.IGNORECASE)

CATEGORY_TITLES = {
    "browser-fidelity": "Browser Fidelity",
    "request-boundary-mocking": "Request-Boundary Mocking",
    "accessibility-automation": "Accessibility Automation",
    "visual-regression": "Visual Regression",
    "ci-artifacts-and-stability": "CI Artifacts and Stability",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TS frontend regression scan")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--agent-brief-out", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    text_files = list(iter_text_files(repo))
    frontend_files = [path for path in text_files if FRONTEND_FILE_RE.search(path.name)]
    browser_hits = collect_matches(repo, REAL_BROWSER_RE)
    jsdom_hits = collect_matches(repo, JSDOM_ONLY_RE)
    mock_hits = collect_matches(repo, MSW_RE)
    internal_mock_hits = collect_matches(repo, INTERNAL_MOCK_RE)
    a11y_hits = collect_matches(repo, AXE_RE)
    visual_hits = collect_matches(repo, VISUAL_RE)
    workflow_hits = collect_matches(repo, WORKFLOW_RE, suffixes={".yml", ".yaml"})

    has_frontend = bool(frontend_files or any_match(repo, re.compile(r"(vite|next|storybook|react|vue|svelte)", re.IGNORECASE), names={"package.json"}))
    findings: list[dict[str, object]] = []

    if not has_frontend:
        categories = [
            category_entry(category_id, title, "not-applicable", "high", ["No browser-facing frontend surface detected."])
            for category_id, title in CATEGORY_TITLES.items()
        ]
        summary = build_summary(
            skill="ts-frontend-regression-audit",
            repo=repo,
            repo_scope="no-frontend-surface",
            coverage={
                "files_scanned": len(text_files),
                "frontend_files": 0,
                "browser_test_entries": 0,
                "mock_entries": 0,
                "visual_entries": 0,
                "workflow_entries": 0,
            },
            categories=categories,
            findings=[],
            top_actions=["Do not force browser-regression controls into repos that currently have no frontend surface."],
            summary_line="No frontend browser surface was detected, so regression-chain auditing is not applicable.",
        )
        write_json(Path(args.summary_out), summary)
        write_text(
            Path(args.report_out),
            render_standard_report("TypeScript Frontend Regression Audit", summary, focus_label="Regression Surface"),
        )
        write_text(
            Path(args.agent_brief_out),
            render_standard_brief(
                "TypeScript Frontend Regression Audit",
                summary,
                target_shape=["Introduce browser-regression controls only when this repository gains a real frontend surface."],
                validation_gates=["Re-run this audit after the repo adds browser-facing UI code."],
            ),
        )
        return 0

    browser_state = "hardened" if browser_hits and not jsdom_hits else "enforced" if browser_hits else "partial" if jsdom_hits else "missing"
    if browser_state != "hardened":
        location = first_match_location(repo, JSDOM_ONLY_RE if jsdom_hits else REAL_BROWSER_RE)
        loc = location or ("package.json", 1, "No real-browser regression entry was detected.")
        findings.append(
            finding_entry(
                "browser-fidelity",
                "high" if browser_state in {"missing", "partial"} else "medium",
                "medium",
                "Browser regression surface is weaker than the UI surface requires",
                loc[0],
                loc[1],
                evidence_summary="The repo shows frontend code, but its regression evidence is still dominated by jsdom-only or otherwise non-browser execution.",
                recommended_change_shape="Add a real-browser lane before trusting the regression chain to guard browser behavior.",
            )
        )

    mock_state = "enforced" if mock_hits else "partial" if internal_mock_hits else "missing"
    if mock_state != "enforced":
        location = first_match_location(repo, INTERNAL_MOCK_RE)
        loc = location or ("package.json", 1, "No request-boundary mock layer was detected.")
        findings.append(
            finding_entry(
                "request-boundary-mocking",
                "medium",
                "medium",
                "Regression tests lack a clear request-boundary mock layer",
                loc[0],
                loc[1],
                evidence_summary="The tests do not clearly show MSW or equivalent network-boundary interception, so mocking may still be patching implementation internals.",
                recommended_change_shape="Move network test doubles to the request boundary instead of component- or function-level patching.",
            )
        )

    a11y_state = "enforced" if a11y_hits else "missing"
    if a11y_state == "missing":
        findings.append(
            finding_entry(
                "accessibility-automation",
                "medium",
                "medium",
                "Accessibility automation is absent from the visible browser test chain",
                "package.json",
                1,
                "The repository exposes browser UI code but does not show an automated a11y check in the main regression lane.",
                "Add one reproducible accessibility automation step in the same browser lane as the regression tests.",
            )
        )

    visual_state = "hardened" if visual_hits else "missing"
    if visual_state == "missing":
        findings.append(
            finding_entry(
                "visual-regression",
                "medium",
                "medium",
                "Visual regression evidence is missing",
                "package.json",
                1,
                "The repo does not surface screenshot-based regression evidence or baseline management for the browser UI.",
                "Add one stable screenshot or visual-baseline lane to guard critical UI states.",
            )
        )

    ci_state = "hardened" if workflow_hits and visual_hits else "enforced" if workflow_hits else "missing"
    if ci_state != "hardened":
        loc = first_match_location(repo, WORKFLOW_RE) or (".github/workflows/ci.yml", 1, "No browser-regression workflow evidence was detected.")
        findings.append(
            finding_entry(
                "ci-artifacts-and-stability",
                "medium",
                "medium",
                "CI does not clearly preserve browser-regression evidence",
                loc[0],
                loc[1],
                evidence_summary="Workflow evidence is weak or missing for traces, screenshots, retries, and artifact retention.",
                recommended_change_shape="Upload browser test reports, traces, and screenshots so regression failures remain reviewable.",
            )
        )

    categories = [
        category_entry(
            "browser-fidelity",
            CATEGORY_TITLES["browser-fidelity"],
            browser_state,
            "high" if browser_state == "missing" else "medium",
            [f"{len(browser_hits)} real-browser test entries", f"{len(jsdom_hits)} jsdom-only entries"],
        ),
        category_entry(
            "request-boundary-mocking",
            CATEGORY_TITLES["request-boundary-mocking"],
            mock_state,
            "medium",
            [f"{len(mock_hits)} boundary-mock entries", f"{len(internal_mock_hits)} internal mock entries"],
        ),
        category_entry(
            "accessibility-automation",
            CATEGORY_TITLES["accessibility-automation"],
            a11y_state,
            "medium",
            [f"{len(a11y_hits)} accessibility test entries"],
        ),
        category_entry(
            "visual-regression",
            CATEGORY_TITLES["visual-regression"],
            visual_state,
            "medium",
            [f"{len(visual_hits)} visual regression entries"],
        ),
        category_entry(
            "ci-artifacts-and-stability",
            CATEGORY_TITLES["ci-artifacts-and-stability"],
            ci_state,
            "medium",
            [f"{len(workflow_hits)} workflow regression entries"],
            notes="CI should preserve enough trace, screenshot, or report evidence to make failures actionable.",
        ),
    ]

    summary = build_summary(
        skill="ts-frontend-regression-audit",
        repo=repo,
        repo_scope="ts-frontend-surface",
        coverage={
            "files_scanned": len(text_files),
            "frontend_files": len(frontend_files),
            "browser_test_entries": len(browser_hits),
            "mock_entries": len(mock_hits),
            "visual_entries": len(visual_hits),
            "workflow_entries": len(workflow_hits),
        },
        categories=categories,
        findings=findings,
        top_actions=[
            "Prove browser behavior in a real browser lane before trusting jsdom-only coverage.",
            "Move test doubles to the request boundary and preserve trace/screenshot artifacts in CI.",
            "Add accessibility and visual checks to the main browser regression chain rather than optional side lanes.",
        ],
        summary_line="Frontend regression is only real when browser execution, boundary mocks, accessibility, visual evidence, and CI traceability all reinforce the same lane.",
    )

    write_json(Path(args.summary_out), summary)
    write_text(
        Path(args.report_out),
        render_standard_report("TypeScript Frontend Regression Audit", summary, focus_label="Regression Surface"),
    )
    write_text(
        Path(args.agent_brief_out),
        render_standard_brief(
            "TypeScript Frontend Regression Audit",
            summary,
            target_shape=[
                "Keep one real-browser lane for critical UI behavior.",
                "Mock at the network boundary, not inside UI implementation details.",
                "Preserve a11y, visual, and CI artifact evidence together with the browser run.",
            ],
            validation_gates=[
                "At least one real-browser regression path is visible in versioned config or scripts.",
                "Boundary mocks, not internal monkey-patching, drive network control in browser tests.",
                "CI uploads enough reports, traces, or screenshots to explain regression failures after the run.",
            ],
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
