#!/usr/bin/env python3
"""Deterministic filesystem-based scanner for ts-lint-format-audit."""

from __future__ import annotations

import argparse
import json
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

SKILL = "ts-lint-format-audit"
TS_SUFFIXES = {".ts", ".tsx"}
CATEGORY_TITLES = {
    "toolchain-consolidation": "Toolchain consolidation",
    "typed-lint-layer": "Typed lint layer",
    "workspace-coverage": "Workspace coverage",
    "suppression-governance": "Suppression governance",
    "ci-enforcement": "CI enforcement",
}
SUPPRESSION_RE = re.compile(r"(eslint-disable|@ts-ignore|@ts-expect-error)")
TYPE_AWARE_RE = re.compile(r"(projectService|parserOptions\s*:\s*\{[^}]*project|tsconfig)", re.IGNORECASE | re.DOTALL)
BIOME_CMD_RE = re.compile(r"\bbiome\b")
ESLINT_CMD_RE = re.compile(r"\beslint\b")
PRETTIER_CMD_RE = re.compile(r"\bprettier\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a repo for TypeScript lint / format governance.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--agent-brief-out", required=True)
    return parser.parse_args()


def load_package_json(path: Path) -> dict:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}


def repo_scope(repo: Path, ts_files: list[Path]) -> str:
    if not ts_files:
        return "no-typescript-surface"
    workspace = repo / "pnpm-workspace.yaml"
    if workspace.exists():
        return "pnpm-workspace"
    roots = {path.relative_to(repo).parts[0] for path in ts_files if path.relative_to(repo).parts}
    if len(roots) > 1:
        return "multi-package-ts-repo"
    return "typescript-repo"


def config_files(repo: Path) -> tuple[list[Path], list[Path], list[Path]]:
    biome_configs = [path for path in iter_text_files(repo) if path.name in {"biome.json", "biome.jsonc"}]
    eslint_configs = [
        path
        for path in iter_text_files(repo)
        if path.name.startswith("eslint.config") or path.name.startswith(".eslintrc")
    ]
    prettier_configs = [path for path in iter_text_files(repo) if path.name.startswith(".prettierrc") or path.name == "prettier.config.js"]
    return biome_configs, eslint_configs, prettier_configs


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    summary_out = Path(args.summary_out).resolve()
    report_out = Path(args.report_out).resolve()
    brief_out = Path(args.agent_brief_out).resolve()

    ts_files = [path for path in iter_text_files(repo, suffixes=TS_SUFFIXES) if path.suffix in TS_SUFFIXES]
    biome_configs, eslint_configs, prettier_configs = config_files(repo)
    biome_mentions = collect_matches(repo, BIOME_CMD_RE, suffixes={".json", ".yaml", ".yml", ".sh", ".toml"}, limit=8)
    eslint_mentions = collect_matches(repo, ESLINT_CMD_RE, suffixes={".json", ".yaml", ".yml", ".sh", ".toml", ".js", ".ts"}, limit=8)
    prettier_mentions = collect_matches(repo, PRETTIER_CMD_RE, suffixes={".json", ".yaml", ".yml", ".sh", ".toml", ".js", ".ts"}, limit=8)
    suppression_hits = collect_matches(repo, SUPPRESSION_RE, suffixes=TS_SUFFIXES, limit=8)
    type_aware_config = any(TYPE_AWARE_RE.search(read_text(path)) for path in eslint_configs)

    package_json_paths = [path for path in iter_text_files(repo) if path.name == "package.json"]
    workspace_packages = []
    for path in package_json_paths:
        payload = load_package_json(path)
        if any(key in payload for key in ("dependencies", "devDependencies")):
            workspace_packages.append(rel(path, repo))

    categories = []
    findings = []
    if not ts_files:
        for category_id, title in CATEGORY_TITLES.items():
            categories.append(category_entry(category_id, title, "not-applicable", "high", [], "No TypeScript application surface was detected."))
        summary_line = "No TypeScript application surface was detected, so the lint / format audit is not applicable."
        top_actions = ["Keep TypeScript lint / format governance out of scope unless a real TypeScript surface is introduced."]
    else:
        if biome_configs and not prettier_mentions:
            consolidation_state = "hardened" if eslint_configs else "enforced"
            consolidation_note = "Biome is visible as the primary style-layer surface, with ESLint reserved for typed lint when present."
        elif eslint_mentions and prettier_mentions and not biome_configs:
            consolidation_state = "partial"
            consolidation_note = "A legacy ESLint / Prettier stack is still governing the repo, but it is no longer the target modern shape."
        elif biome_configs or eslint_configs:
            consolidation_state = "partial"
            consolidation_note = "The style-layer truth is split between more than one active stack."
        else:
            consolidation_state = "missing"
            consolidation_note = "No credible TypeScript lint / format command surface was detected."
        categories.append(
            category_entry(
                "toolchain-consolidation",
                CATEGORY_TITLES["toolchain-consolidation"],
                consolidation_state,
                "high",
                [rel(path, repo) for path in biome_configs[:2]] + [rel(path, repo) for path in eslint_configs[:2]] + prettier_mentions[:2],
                consolidation_note,
            )
        )

        if eslint_configs and type_aware_config:
            typed_state = "hardened" if biome_configs else "enforced"
            typed_note = "Type-aware lint config is visible."
        elif eslint_configs:
            typed_state = "partial"
            typed_note = "ESLint is present, but type-aware project wiring is weak or absent."
        else:
            typed_state = "missing"
            typed_note = "No visible typed-lint carrier was detected."
        categories.append(
            category_entry(
                "typed-lint-layer",
                CATEGORY_TITLES["typed-lint-layer"],
                typed_state,
                "medium",
                [rel(path, repo) for path in eslint_configs[:3]],
                typed_note,
            )
        )

        workspace_state = "enforced"
        workspace_note = "Workspace lint coverage looks centrally reachable."
        if len(workspace_packages) > 1 and not (biome_mentions or eslint_mentions):
            workspace_state = "partial"
            workspace_note = "Multiple TS packages exist, but no clear workspace-wide lint entrypoint is visible."
        categories.append(
            category_entry(
                "workspace-coverage",
                CATEGORY_TITLES["workspace-coverage"],
                workspace_state,
                "medium",
                workspace_packages[:5] + biome_mentions[:2] + eslint_mentions[:2],
                workspace_note,
            )
        )

        if not suppression_hits:
            suppression_state = "hardened"
            suppression_note = "No broad suppression drift stood out from local evidence."
        elif len(suppression_hits) <= 4:
            suppression_state = "enforced"
            suppression_note = "Suppressions exist but are still reviewable."
        else:
            suppression_state = "partial"
            suppression_note = "Suppressions are common enough to weaken trust in the TypeScript baseline."
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

        if biome_mentions or eslint_mentions:
            ci_state = "hardened" if any(item.startswith(".github/workflows/") for item in biome_mentions + eslint_mentions) else "enforced"
            ci_note = "A lint / format path is visible in normal repo workflow."
        else:
            ci_state = "missing"
            ci_note = "No visible lint / format path was found in workflow evidence."
        categories.append(
            category_entry(
                "ci-enforcement",
                CATEGORY_TITLES["ci-enforcement"],
                ci_state,
                "medium",
                [item for item in biome_mentions + eslint_mentions if item.startswith(".github/workflows/")][:6],
                ci_note,
            )
        )

        if consolidation_state in {"missing", "partial"}:
            evidence = first_match_location(repo, PRETTIER_CMD_RE, suffixes={".json", ".yaml", ".yml", ".sh", ".toml", ".js", ".ts"})
            if evidence is None:
                evidence = rel(ts_files[0], repo), 1, "TypeScript style-layer truth is split or missing."
            findings.append(
                finding_entry(
                    "toolchain-consolidation",
                    "high" if consolidation_state == "missing" else "medium",
                    "high",
                    "TypeScript style layer is not cleanly consolidated",
                    evidence[0],
                    evidence[1],
                    evidence[2],
                    "Separate style-layer ownership from typed lint, and make the command surface unambiguous.",
                    merge_gate="fix-before-release",
                )
            )
        if typed_state in {"missing", "partial"}:
            evidence = first_match_location(repo, TYPE_AWARE_RE, suffixes={".js", ".ts", ".json", ".yaml", ".yml"})
            if evidence is None:
                evidence = rel(eslint_configs[0], repo) if eslint_configs else rel(ts_files[0], repo), 1, "Typed lint is absent or not clearly wired to project types."
            findings.append(
                finding_entry(
                    "typed-lint-layer",
                    "high" if typed_state == "missing" else "medium",
                    "medium",
                    "Typed lint is missing or weakly wired",
                    evidence[0],
                    evidence[1],
                    evidence[2],
                    "Keep type-aware lint as a separate semantic layer and wire it to real tsconfig inputs.",
                    merge_gate="fix-before-release",
                )
            )
        if suppression_state == "partial":
            evidence = first_match_location(repo, SUPPRESSION_RE, suffixes=TS_SUFFIXES)
            if evidence is None:
                evidence = rel(ts_files[0], repo), 1, "Suppression density is high enough to hide drift."
            findings.append(
                finding_entry(
                    "suppression-governance",
                    "medium",
                    "medium",
                    "TypeScript suppressions are dense enough to weaken lint trust",
                    evidence[0],
                    evidence[1],
                    evidence[2],
                    "Shrink `eslint-disable` / `@ts-ignore` escape hatches until each one is reviewable and justified.",
                )
            )

        top_actions = [
            "Make one style-layer truth explicit and keep typed lint as a separate semantic layer.",
            "Ensure typed lint is wired to real project types before calling the TS baseline enforced.",
            "Cut down suppressions until workspace-wide lint results are believable again.",
        ]
        summary_line = (
            "TypeScript lint / format governance is cleanly enforced."
            if not findings
            else "TypeScript lint / format governance exists, but consolidation, typed lint, or suppression discipline still needs work."
        )

    coverage = {
        "files_scanned": len(iter_text_files(repo)),
        "ts_files": len(ts_files),
        "biome_configs": len(biome_configs),
        "eslint_configs": len(eslint_configs),
        "workspace_packages": len(workspace_packages),
        "suppression_hits": len(suppression_hits),
    }
    summary = build_summary(
        skill=SKILL,
        repo=repo,
        repo_scope=repo_scope(repo, ts_files),
        coverage=coverage,
        categories=categories,
        findings=findings,
        top_actions=top_actions,
        summary_line=summary_line,
    )

    report = render_standard_report("TypeScript Lint Format Audit Report", summary, focus_label="Category states")
    brief = render_standard_brief(
        "TypeScript Lint Format Audit",
        summary,
        target_shape=[
            "Biome owns formatting, import sorting, and basic lint decisions.",
            "Typed lint is a separate semantic layer connected to real tsconfig inputs.",
            "Workspace packages are covered by one centrally reviewable lint path.",
        ],
        validation_gates=[
            "`biome check .` or the equivalent style-layer command runs in CI.",
            "Typed ESLint runs with project-aware configuration in CI.",
            "Suppressions remain sparse enough to review directly.",
        ],
    )

    write_json(summary_out, summary)
    write_text(report_out, report)
    write_text(brief_out, brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
