#!/usr/bin/env python3
"""Deterministic filesystem-based scanner for python-lint-format-audit."""

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
from standard_audit_utils import read_text  # noqa: E402
from standard_audit_utils import rel  # noqa: E402
from standard_audit_utils import render_standard_brief  # noqa: E402
from standard_audit_utils import render_standard_report  # noqa: E402
from standard_audit_utils import write_json  # noqa: E402
from standard_audit_utils import write_text  # noqa: E402

SKILL = "python-lint-format-audit"
PY_SUFFIXES = {".py", ".pyi"}
TOOLCHAIN_TITLE = "Python lint / format control surface"
CATEGORY_TITLES = {
    "toolchain-normalization": "Toolchain normalization",
    "config-coherence": "Config coherence",
    "enforcement-gates": "Enforcement gates",
    "suppression-governance": "Suppression governance",
    "scope-hygiene": "Scope hygiene",
}
RUFF_CONFIG_RE = re.compile(r"(\[tool\.ruff\]|^\s*extend\s*=|^\s*line-length\s*=)", re.MULTILINE)
LEGACY_CONFIG_RE = re.compile(r"(\[tool\.black\]|\[tool\.isort\]|\[flake8\]|max-line-length\s*=)", re.MULTILINE)
RUFF_CHECK_RE = re.compile(r"ruff\s+check")
RUFF_FORMAT_RE = re.compile(r"ruff\s+format(?:\s+--check)?")
LEGACY_ACTIVE_RE = re.compile(r"\b(black|isort|flake8)\b")
SUPPRESSION_RE = re.compile(r"(#\s*noqa\b|per-file-ignores|extend-exclude|exclude\s*=)")
GENERATED_DIR_RE = re.compile(r"(generated|vendor|vendors|fixtures?/generated|migrations)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a repo for Python lint / format governance.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--agent-brief-out", required=True)
    return parser.parse_args()


def repo_scope(repo: Path, python_files: list[Path]) -> str:
    if not python_files:
        return "no-python-surface"
    roots = {path.relative_to(repo).parts[0] for path in python_files if path.relative_to(repo).parts}
    if len(roots) > 1:
        return "python-monorepo-or-multi-root"
    return "python-repo"


def config_files(repo: Path) -> tuple[list[Path], list[Path]]:
    ruff_configs: list[Path] = []
    legacy_configs: list[Path] = []
    for path in iter_text_files(repo):
        if path.name in {"ruff.toml", ".ruff.toml"}:
            ruff_configs.append(path)
        elif path.name == "pyproject.toml":
            text = read_text(path)
            if RUFF_CONFIG_RE.search(text):
                ruff_configs.append(path)
            if LEGACY_CONFIG_RE.search(text):
                legacy_configs.append(path)
        elif path.name in {".flake8", "tox.ini", "setup.cfg"}:
            text = read_text(path)
            if LEGACY_CONFIG_RE.search(text):
                legacy_configs.append(path)
    return sorted(dict.fromkeys(ruff_configs)), sorted(dict.fromkeys(legacy_configs))


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    summary_out = Path(args.summary_out).resolve()
    report_out = Path(args.report_out).resolve()
    brief_out = Path(args.agent_brief_out).resolve()

    python_files = [path for path in iter_text_files(repo, suffixes=PY_SUFFIXES) if path.suffix in PY_SUFFIXES]
    ruff_configs, legacy_configs = config_files(repo)
    ci_entries = collect_matches(repo, RUFF_CHECK_RE, suffixes={".yml", ".yaml", ".toml", ".json", ".md", ".sh"}, limit=8)
    format_entries = collect_matches(repo, RUFF_FORMAT_RE, suffixes={".yml", ".yaml", ".toml", ".json", ".md", ".sh"}, limit=8)
    precommit_entries = collect_matches(repo, RUFF_CHECK_RE, names={".pre-commit-config.yaml"}, limit=4)
    suppression_hits = collect_matches(repo, SUPPRESSION_RE, suffixes=PY_SUFFIXES | {".toml", ".cfg", ".ini"}, limit=8)
    legacy_active = collect_matches(repo, LEGACY_ACTIVE_RE, suffixes={".yml", ".yaml", ".toml", ".json", ".sh"}, limit=8)
    generated_paths = [path for path in python_files if GENERATED_DIR_RE.search(rel(path, repo))]
    generated_excluded = any_match(repo, re.compile(r"(generated|vendor|migrations)"), names={"pyproject.toml", "ruff.toml", ".ruff.toml", ".flake8", "setup.cfg", "tox.ini"})

    categories = []
    findings = []
    if not python_files:
        for category_id, title in CATEGORY_TITLES.items():
            categories.append(category_entry(category_id, title, "not-applicable", "high", [], "No Python application surface was detected."))
        summary_line = "No Python application surface was detected, so the lint / format audit is not applicable."
        top_actions = ["Keep Python lint / format governance out of scope unless a real Python surface is introduced."]
    else:
        if ruff_configs and not legacy_active and not legacy_configs:
            toolchain_state = "hardened"
            toolchain_note = "Ruff is the visible primary toolchain."
        elif ruff_configs:
            toolchain_state = "partial"
            toolchain_note = "Ruff is present, but legacy config or legacy commands still dilute the modern toolchain target."
        elif legacy_configs or legacy_active:
            toolchain_state = "partial"
            toolchain_note = "Only legacy Black / isort / Flake8 style surfaces are visible, which is not the target modern shape."
        else:
            toolchain_state = "missing"
            toolchain_note = "No credible Python lint / format entrypoint was detected."
        categories.append(
            category_entry(
                "toolchain-normalization",
                CATEGORY_TITLES["toolchain-normalization"],
                toolchain_state,
                "high",
                [rel(path, repo) for path in (ruff_configs or legacy_configs)[:4]] + legacy_active[:2],
                toolchain_note,
            )
        )

        if len(ruff_configs) == 1 and not legacy_configs and not legacy_active:
            coherence_state = "hardened"
            coherence_note = "One Ruff source of truth is visible."
        elif len(ruff_configs) > 1 or (ruff_configs and legacy_active):
            coherence_state = "partial"
            coherence_note = "More than one config surface appears to influence the repo."
        elif ruff_configs:
            coherence_state = "enforced"
            coherence_note = "Ruff config exists, but residual legacy config still needs cleanup."
        else:
            coherence_state = "missing"
            coherence_note = "No clear Python lint / format truth source was found."
        categories.append(
            category_entry(
                "config-coherence",
                CATEGORY_TITLES["config-coherence"],
                coherence_state,
                "medium",
                [rel(path, repo) for path in ruff_configs[:3]] + [rel(path, repo) for path in legacy_configs[:3]],
                coherence_note,
            )
        )

        if ci_entries and format_entries and precommit_entries:
            enforcement_state = "hardened"
            enforcement_note = "Ruff check and format are visible in both CI and pre-commit."
        elif ci_entries and format_entries:
            enforcement_state = "enforced"
            enforcement_note = "CI shows both lint and format checks."
        elif ci_entries or precommit_entries:
            enforcement_state = "partial"
            enforcement_note = "Only part of the Ruff gate chain is visible."
        else:
            enforcement_state = "missing"
            enforcement_note = "No reliable Ruff gate entrypoint is visible in workflow files."
        categories.append(
            category_entry(
                "enforcement-gates",
                CATEGORY_TITLES["enforcement-gates"],
                enforcement_state,
                "medium",
                ci_entries[:3] + format_entries[:3] + precommit_entries[:2],
                enforcement_note,
            )
        )

        if not suppression_hits:
            suppression_state = "hardened"
            suppression_note = "No broad noqa / exclude surface stood out from local evidence."
        elif len(suppression_hits) <= 3:
            suppression_state = "enforced"
            suppression_note = "Suppressions exist but are still sparse enough to review directly."
        else:
            suppression_state = "partial"
            suppression_note = "Suppressions are numerous enough to threaten trust in the lint baseline."
        categories.append(
            category_entry(
                "suppression-governance",
                CATEGORY_TITLES["suppression-governance"],
                suppression_state,
                "medium",
                suppression_hits[:5],
                suppression_note,
            )
        )

        if not generated_paths:
            scope_state = "enforced"
            scope_note = "No generated-like Python tree was detected."
        elif generated_excluded:
            scope_state = "enforced"
            scope_note = "Generated or vendor-like paths appear to be explicitly isolated."
        else:
            scope_state = "partial"
            scope_note = "Generated-like paths exist without clear lint / format scope controls."
        categories.append(
            category_entry(
                "scope-hygiene",
                CATEGORY_TITLES["scope-hygiene"],
                scope_state,
                "medium",
                [rel(path, repo) for path in generated_paths[:4]],
                scope_note,
            )
        )

        if toolchain_state in {"missing", "partial"}:
            evidence = first_match_location(repo, LEGACY_ACTIVE_RE, suffixes={".yml", ".yaml", ".toml", ".json", ".sh"})
            if evidence is None and ruff_configs:
                evidence = rel(ruff_configs[0], repo), 1, "Ruff config exists but legacy command overlap remains."
            if evidence is None:
                evidence = rel(python_files[0], repo), 1, "Python source exists without a clean modern lint stack."
            findings.append(
                finding_entry(
                    "toolchain-normalization",
                    "high" if toolchain_state == "missing" else "medium",
                    "high",
                    "Python lint stack is not cleanly normalized",
                    evidence[0],
                    evidence[1],
                    evidence[2],
                    "Make Ruff the single command-level lint / format truth and demote legacy tools to migration-only residue.",
                    merge_gate="fix-before-release",
                )
            )
        if enforcement_state in {"missing", "partial"}:
            evidence = first_match_location(repo, RUFF_CHECK_RE, suffixes={".yml", ".yaml", ".toml", ".json", ".sh"})
            if evidence is None:
                evidence = rel(ruff_configs[0], repo) if ruff_configs else rel(python_files[0], repo), 1, "No complete Ruff gate chain was visible in CI or pre-commit."
            findings.append(
                finding_entry(
                    "enforcement-gates",
                    "high" if enforcement_state == "missing" else "medium",
                    "medium",
                    "Ruff gates are not fully visible in normal workflow",
                    evidence[0],
                    evidence[1],
                    evidence[2],
                    "Expose both `ruff check` and `ruff format --check` in the main CI and pre-commit path.",
                    merge_gate="fix-before-release",
                )
            )
        if suppression_state == "partial":
            evidence = first_match_location(repo, SUPPRESSION_RE, suffixes=PY_SUFFIXES | {".toml", ".cfg", ".ini"})
            if evidence is None:
                evidence = rel(python_files[0], repo), 1, "Suppression footprint is broad enough to weaken trust."
            findings.append(
                finding_entry(
                    "suppression-governance",
                    "medium",
                    "medium",
                    "Suppressions and excludes are broad enough to hide drift",
                    evidence[0],
                    evidence[1],
                    evidence[2],
                    "Shrink broad excludes and make noqa usage reviewable at the file or rule level.",
                )
            )
        if scope_state == "partial":
            target = generated_paths[0]
            findings.append(
                finding_entry(
                    "scope-hygiene",
                    "medium",
                    "medium",
                    "Generated-like Python paths are not clearly isolated from the lint surface",
                    rel(target, repo),
                    1,
                    "Generated or migration-heavy paths were found without matching scope controls.",
                    "Declare generated and vendor boundaries explicitly so lint debt does not get normalized as baseline noise.",
                )
            )

        top_actions = [
            "Make Ruff the single visible Python lint / format command surface before adding more style rules.",
            "Put `ruff check` and `ruff format --check` on the primary CI and pre-commit path.",
            "Shrink broad suppressions and generated-path escapes until the baseline is reviewable again.",
        ]
        summary_line = (
            "Python lint / format governance is cleanly enforced."
            if not findings
            else "Python lint / format governance exists, but the repo still exposes split truth, weak gates, or broad suppressions."
        )

    coverage = {
        "files_scanned": len(iter_text_files(repo)),
        "python_files": len(python_files),
        "ruff_configs": len(ruff_configs),
        "legacy_configs": len(legacy_configs),
        "ci_entries": len(ci_entries) + len(format_entries) + len(precommit_entries),
        "suppression_hits": len(suppression_hits),
    }
    summary = build_summary(
        skill=SKILL,
        repo=repo,
        repo_scope=repo_scope(repo, python_files),
        coverage=coverage,
        categories=categories,
        findings=findings,
        top_actions=top_actions,
        summary_line=summary_line,
    )

    report = render_standard_report("Python Lint Format Audit Report", summary, focus_label="Category states")
    brief = render_standard_brief(
        "Python Lint Format Audit",
        summary,
        target_shape=[
            "One Ruff-owned lint and format surface is the public truth.",
            "Legacy Black / isort / Flake8 surfaces are migration residue, not an acceptable steady-state control surface.",
            "Generated and vendor paths are isolated instead of silently normalizing baseline debt.",
        ],
        validation_gates=[
            "`ruff check .` succeeds in CI.",
            "`ruff format --check .` succeeds in CI.",
            "Pre-commit runs the same Ruff gates the repo relies on before merge.",
        ],
    )

    write_json(summary_out, summary)
    write_text(report_out, report)
    write_text(brief_out, brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
