#!/usr/bin/env python3
"""Heuristic schema-governance audit for OpenAPI and JSON Schema repositories."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RUNTIME_BIN = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN))

from standard_audit_utils import build_summary  # noqa: E402
from standard_audit_utils import category_entry  # noqa: E402
from standard_audit_utils import collect_matches  # noqa: E402
from standard_audit_utils import finding_entry  # noqa: E402
from standard_audit_utils import first_match_location  # noqa: E402
from standard_audit_utils import iter_text_files  # noqa: E402
from standard_audit_utils import rel  # noqa: E402
from standard_audit_utils import render_standard_brief  # noqa: E402
from standard_audit_utils import render_standard_report  # noqa: E402
from standard_audit_utils import write_json  # noqa: E402
from standard_audit_utils import write_text  # noqa: E402

SCHEMA_FILE_RE = re.compile(r"(openapi|swagger|schema|oas)", re.IGNORECASE)
OPENAPI_HEADER_RE = re.compile(r"^\s*openapi:\s*3", re.IGNORECASE)
JSON_SCHEMA_RE = re.compile(r'"\$schema"|"definitions"|jsonschema', re.IGNORECASE)
REDOCLY_CONFIG_RE = re.compile(r"redocly", re.IGNORECASE)
SPECTRAL_CONFIG_RE = re.compile(r"spectral", re.IGNORECASE)
LINT_BUNDLE_RE = re.compile(r"(redocly\s+(lint|bundle)|spectral\s+lint|check-jsonschema|ajv\s+validate)", re.IGNORECASE)
BREAKING_DIFF_RE = re.compile(r"(openapi[- ]diff|oasdiff|swagger[- ]diff|breaking[- ]change|azure/oad|oad\s+diff)", re.IGNORECASE)
PUBLISH_RE = re.compile(r"(publish|upload-artifact|pages|artifact|schema registry|swaggerhub)", re.IGNORECASE)
GENERATED_RE = re.compile(r"(generated|gen[-_/]|client[-_/]|sdk[-_/]|dist/)", re.IGNORECASE)
SOURCE_DIR_RE = re.compile(r"(openapi|schemas?|specs?|api[-_/]?contracts?)", re.IGNORECASE)

CATEGORY_TITLES = {
    "artifact-health": "Artifact Health",
    "ruleset-governance": "Ruleset Governance",
    "source-of-truth-discipline": "Source-of-Truth Discipline",
    "breaking-change-detection": "Breaking-Change Detection",
    "ci-publication-surface": "CI Publication Surface",
}


def relevant_schema_file(path: Path) -> bool:
    if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
        return False
    if SCHEMA_FILE_RE.search(str(path)):
        return True
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(OPENAPI_HEADER_RE.search(text) or JSON_SCHEMA_RE.search(text))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run schema governance scan")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--agent-brief-out", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    text_files = list(iter_text_files(repo))
    schema_files = [path for path in text_files if relevant_schema_file(path)]
    ruleset_configs = [
        path for path in text_files if path.name in {"redocly.yaml", ".redocly.yaml", ".spectral.yaml", ".spectral.yml"}
    ]

    lint_hits = collect_matches(repo, LINT_BUNDLE_RE)
    diff_hits = collect_matches(repo, BREAKING_DIFF_RE)
    publish_hits = collect_matches(repo, PUBLISH_RE, suffixes={".yml", ".yaml"})
    workflow_hits = collect_matches(
        repo,
        re.compile(r"(redocly|spectral|check-jsonschema|ajv|openapi[- ]diff|oasdiff|upload-artifact|pages)", re.IGNORECASE),
        suffixes={".yml", ".yaml"},
    )

    source_files = [path for path in schema_files if SOURCE_DIR_RE.search(rel(path.parent, repo))]
    generated_files = [path for path in schema_files if GENERATED_RE.search(rel(path, repo))]
    has_surface = bool(schema_files or ruleset_configs or lint_hits)
    findings: list[dict[str, object]] = []

    if not has_surface:
        categories = [
            category_entry(category_id, title, "not-applicable", "high", ["No OpenAPI or JSON Schema surface detected."])
            for category_id, title in CATEGORY_TITLES.items()
        ]
        summary = build_summary(
            skill="openapi-jsonschema-governance-audit",
            repo=repo,
            repo_scope="no-openapi-or-jsonschema-surface",
            coverage={
                "files_scanned": len(text_files),
                "schema_surface_files": 0,
                "canonical_sources": 0,
                "ruleset_configs": 0,
                "diff_entries": 0,
                "ci_entries": 0,
            },
            categories=categories,
            findings=[],
            top_actions=["Keep schema governance out of the action queue until this repo actually carries OpenAPI or JSON Schema artifacts."],
            summary_line="No OpenAPI or JSON Schema surface was detected, so schema governance is not applicable.",
        )
        write_json(Path(args.summary_out), summary)
        write_text(
            Path(args.report_out),
            render_standard_report("OpenAPI / JSON Schema Governance Audit", summary, focus_label="Governance Surface"),
        )
        write_text(
            Path(args.agent_brief_out),
            render_standard_brief(
                "OpenAPI / JSON Schema Governance Audit",
                summary,
                target_shape=[
                    "Introduce schema governance only when the repo gains a real OpenAPI or JSON Schema source surface.",
                ],
                validation_gates=["Re-run only after a canonical schema source is added."],
            ),
        )
        return 0

    artifact_state = "hardened" if schema_files and lint_hits else "partial" if schema_files else "missing"
    artifact_evidence = [
        f"{len(schema_files)} schema artifacts detected",
        f"{len(lint_hits)} lint/bundle validation entries detected",
    ]
    if artifact_state == "partial":
        location = first_match_location(repo, LINT_BUNDLE_RE)
        loc = location or ("package.json", 1, "No lint / bundle entry was detected.")
        findings.append(
            finding_entry(
                "artifact-health",
                "medium",
                "medium",
                "Schema artifacts exist without a clear lint / bundle chain",
                loc[0],
                loc[1],
                evidence_summary="Canonical schema files exist, but the repo does not show a stable lint / bundle path that proves they stay parseable in CI.",
                recommended_change_shape="Add one reproducible lint / bundle entry and wire it into CI before relying on the schema surface.",
            )
        )

    ruleset_hits = collect_matches(repo, REDOCLY_CONFIG_RE, names={"package.json", "pyproject.toml", "justfile", "Makefile"})
    spectral_hits = collect_matches(repo, SPECTRAL_CONFIG_RE, names={"package.json", "pyproject.toml", "justfile", "Makefile"})
    has_ruleset = bool(ruleset_configs or ruleset_hits or spectral_hits)
    ruleset_state = "hardened" if len(ruleset_configs) >= 2 else "enforced" if has_ruleset else "missing"
    if ruleset_state == "missing":
        findings.append(
            finding_entry(
                "ruleset-governance",
                "high",
                "medium",
                "Schema governance lacks an explicit ruleset layer",
                "package.json",
                1,
                "The repo has schema artifacts but no Redocly, Spectral, or equivalent ruleset signal that makes policy executable.",
                "Introduce one explicit lint/ruleset configuration and keep it under version control.",
            )
        )

    if generated_files and not source_files:
        source_state = "missing"
        source_note = "Generated clients or dist artifacts appear to be the only visible schema surface."
    elif generated_files and source_files:
        source_state = "partial"
        source_note = "Canonical schema sources exist, but generated artifacts are also prominent and need ownership boundaries."
    else:
        source_state = "enforced" if source_files else "partial"
        source_note = "Source schema directories are visible and generated artifacts do not dominate the surface."
    if source_state in {"missing", "partial"}:
        location = generated_files[0] if generated_files else (schema_files[0] if schema_files else repo / "README.md")
        findings.append(
            finding_entry(
                "source-of-truth-discipline",
                "high" if source_state == "missing" else "medium",
                "high" if source_state == "missing" else "medium",
                "Canonical schema source is ambiguous",
                str(location.relative_to(repo)),
                1,
                "The repository makes generated clients or bundles too easy to confuse with the canonical source-of-truth artifacts.",
                "Separate source specs from generated outputs and document ownership directly in scripts and CI.",
            )
        )

    diff_in_ci = any(".github/workflows/" in hit for hit in diff_hits)
    diff_local_only = bool(diff_hits) and not diff_in_ci
    if diff_in_ci:
        diff_state = "enforced"
        diff_note = "At least one breaking-change detector is visible in CI or workflow files."
    elif diff_local_only:
        diff_state = "partial"
        diff_note = "Breaking-change detection exists, but only as a local or ad-hoc command."
    else:
        diff_state = "missing"
        diff_note = "No reproducible breaking-change gate was detected."
    if diff_state != "enforced":
        location = first_match_location(repo, BREAKING_DIFF_RE)
        loc = location or ("package.json", 1, "No breaking-change gate was detected.")
        findings.append(
            finding_entry(
                "breaking-change-detection",
                "high" if diff_state == "missing" else "medium",
                "medium",
                "Schema changes are not protected by a CI-visible diff gate",
                loc[0],
                loc[1],
                evidence_summary="The repository does not show a trustworthy PR or CI step that blocks breaking schema changes before publication.",
                recommended_change_shape="Add a reproducible breaking-change diff command to CI; do not rely on local-only diff checks.",
            )
        )

    ci_state = "hardened" if workflow_hits and publish_hits else "partial" if workflow_hits else "missing"
    ci_note = (
        "CI references lint, bundle, diff, or artifact publication."
        if workflow_hits
        else "No workflow evidence was found for schema linting, bundling, or publication."
    )
    if ci_state != "hardened":
        loc = first_match_location(repo, PUBLISH_RE) or ("package.json", 1, "No CI publication evidence was detected.")
        findings.append(
            finding_entry(
                "ci-publication-surface",
                "medium",
                "medium",
                "Schema governance is weakly represented in CI and publication steps",
                loc[0],
                loc[1],
                evidence_summary="Schema tooling may exist locally, but CI does not clearly preserve the resulting reports, bundles, or publication checks.",
                recommended_change_shape="Expose schema governance through CI steps that produce lint/bundle/diff evidence and artifact outputs.",
            )
        )

    categories = [
        category_entry("artifact-health", CATEGORY_TITLES["artifact-health"], artifact_state, "medium", artifact_evidence),
        category_entry(
            "ruleset-governance",
            CATEGORY_TITLES["ruleset-governance"],
            ruleset_state,
            "medium",
            [f"{len(ruleset_configs)} ruleset config files detected", f"{len(ruleset_hits) + len(spectral_hits)} script references detected"],
        ),
        category_entry(
            "source-of-truth-discipline",
            CATEGORY_TITLES["source-of-truth-discipline"],
            source_state,
            "high" if source_state == "missing" else "medium",
            [f"{len(source_files)} canonical-looking source files", f"{len(generated_files)} generated-looking schema artifacts"],
            notes=source_note,
        ),
        category_entry(
            "breaking-change-detection",
            CATEGORY_TITLES["breaking-change-detection"],
            diff_state,
            "medium",
            [f"{len(diff_hits)} breaking-change entries detected", f"{sum(1 for hit in diff_hits if '.github/workflows/' in hit)} CI workflow references"],
            notes=diff_note,
        ),
        category_entry(
            "ci-publication-surface",
            CATEGORY_TITLES["ci-publication-surface"],
            ci_state,
            "medium",
            [f"{len(workflow_hits)} workflow schema entries", f"{len(publish_hits)} publication or artifact hints"],
            notes=ci_note,
        ),
    ]

    summary = build_summary(
        skill="openapi-jsonschema-governance-audit",
        repo=repo,
        repo_scope="openapi-jsonschema-surface",
        coverage={
            "files_scanned": len(text_files),
            "schema_surface_files": len(schema_files),
            "canonical_sources": len(source_files),
            "ruleset_configs": len(ruleset_configs),
            "diff_entries": len(diff_hits),
            "ci_entries": len(workflow_hits),
        },
        categories=categories,
        findings=findings,
        top_actions=[
            "Make one canonical schema source explicit before treating bundles or generated clients as trustworthy.",
            "Wire lint, bundle, and breaking-change checks into CI rather than local-only scripts.",
            "Preserve schema governance evidence as workflow artifacts so failures are reviewable.",
        ],
        summary_line="Schema governance is only real when canonical sources, rulesets, diff gates, and CI publication evidence all point at the same artifact chain.",
    )

    write_json(Path(args.summary_out), summary)
    write_text(
        Path(args.report_out),
        render_standard_report("OpenAPI / JSON Schema Governance Audit", summary, focus_label="Governance Surface"),
    )
    write_text(
        Path(args.agent_brief_out),
        render_standard_brief(
            "OpenAPI / JSON Schema Governance Audit",
            summary,
            target_shape=[
                "Keep source specs separate from generated bundles and clients.",
                "Run one reproducible lint/bundle pipeline plus one CI-visible breaking-change gate.",
                "Expose schema publication evidence through CI rather than README-only guidance.",
            ],
            validation_gates=[
                "Canonical source directories are obvious and generated outputs are secondary.",
                "Lint, bundle, and diff all run from versioned scripts or workflow steps.",
                "CI stores enough schema artifacts to explain failures after the run.",
            ],
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
