#!/usr/bin/env python3
"""Aggregate machine-readable audit summaries into one repo-health summary."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from repo_health_catalog import EXPECTED
from repo_health_catalog import agent_brief_path as child_agent_brief_path
from repo_health_catalog import report_path as child_report_path
from repo_health_catalog import summary_path as child_summary_path

RED_VERDICTS = {
    "unsafe",
    "blocked",
    "broken",
    "contract-theater",
    "soft-gates",
    "drifting",
    "dual-write-gambling",
    "workflow-time-bomb",
}
YELLOW_VERDICTS = {
    "fragile",
    "watch",
    "partial",
    "partial-coverage",
    "ceremonial",
    "contained",
    "baseline-needed",
    "cleanup-first",
    "boundary-hardening",
    "incremental-governance",
    "paper-guardrails",
    "partially-contained",
    "scan-blocked",
    "triage",
}
POSITIVE_VERDICTS = {
    "sound",
    "hardened",
    "healthy",
    "disciplined",
    "real-gates",
    "hard-harness",
    "durable-harness",
    "well-governed",
}


def recommended_domain_action(run: dict[str, Any], coverage_status: str = "complete") -> str | None:
    status = str(run.get("status") or "")
    domain = str(run.get("domain") or "")
    if status == "blocked":
        failures = run.get("dependency_failures") or []
        if failures:
            failure = failures[0]
            return (
                f"Unblock {run['skill_name']} first: restore `{failure.get('name')}` "
                f"so the audit can run before trusting {domain} coverage."
            )
        return f"Unblock {run['skill_name']} first: restore its runtime prerequisites before trusting {domain} coverage."
    if status in {"missing", "invalid"}:
        if coverage_status == "partial":
            return "Close the remaining missing or invalid audit domains before calling this rollup decision-complete."
        return None
    if status != "present":
        return None

    sev = run.get("severity_counts") or {}
    verdict = str(run.get("child_verdict") or "").lower()
    is_high = int(sev.get("critical", 0)) > 0 or int(sev.get("high", 0)) > 0 or verdict in RED_VERDICTS
    is_watch = int(sev.get("medium", 0)) > 0 or verdict in YELLOW_VERDICTS

    if is_high:
        if domain == "distributed-side-effects":
            return "Fix distributed side-effect correctness first: remove dual writes, add durable handoff, and prove idempotency."
        if domain == "contracts":
            return "Turn contract theater into machine enforcement: harden compile-time, runtime, and merge gates."
        if domain == "structure":
            return "Stop structural debt from spreading: freeze boundary violations and cycles before other cleanup."
        if domain == "pythonic-ddd-drift":
            return "Repair boundary leaks and flatten ceremonial Python layers before adding more abstractions."
        if domain == "module-shape":
            return "Break up oversized modules and fan-out hubs before they keep teaching low-cohesion structure."
        if domain == "cleanup":
            return "Delete expired compatibility surfaces that are still distorting the codebase."
        if domain == "durable-agents":
            return "Repair durable-agent path correctness before trusting Temporal / pydantic-ai behavior."
        if domain == "llm-api-freshness":
            return "Verify current provider docs and migrate stale LLM SDK or endpoint usage before the next AI-facing change."
        if domain == "error-governance":
            return "Repair outward error contracts before more surfaces learn the wrong failure shape."
        if domain == "silent-failure":
            return "Remove swallowed failures and invisible fallback paths before they normalize silent corruption."
        if domain == "schema-governance":
            return "Make canonical schema sources explicit and put lint / bundle / diff gates in CI before shipping more contract drift."
        if domain == "frontend-regression":
            return "Put browser-real regression, boundary mocks, and reviewable CI artifacts in place before trusting frontend stability."
        if domain == "python-lint-format":
            return "Make Ruff the only Python lint / format truth before more legacy style drift accumulates."
        if domain == "ts-lint-format":
            return "Make Biome own the style layer and keep typed lint wired to real TS projects before more workspace drift spreads."
        if domain == "security-posture":
            return "Restore lockfile-backed baseline security gates before trusting dependency or static-scan posture."
    if is_watch:
        if domain == "pythonic-ddd-drift":
            return "Trim abstraction bloat where it adds shape without policy."
        if domain == "cleanup":
            return "Use cleanup debt reduction as a leverage move, not cosmetic tidying."
        if domain == "structure":
            return "Stabilize dependency-audit config and workspace metadata before trying to harden boundaries."
        if domain == "llm-api-freshness":
            return "Run a Context7-backed verification pass to separate real LLM API drift from local suspicion."
        if domain == "module-shape":
            return "Use module-shape findings to target the worst hubs first instead of broad mechanical reshuffling."
        if domain == "silent-failure":
            return "Make fail-loud rules visible before more catch-and-continue patterns spread."
        if domain == "error-governance":
            return "Tighten the public error contract before schema and message text drift farther apart."
        if domain == "schema-governance":
            return "Clarify source-of-truth ownership before lint and publication evidence drift further apart."
        if domain == "frontend-regression":
            return "Upgrade jsdom-heavy frontend testing into a browser-real lane before the current gap becomes normal."
        if domain == "python-lint-format":
            return "Finish the Ruff-first migration before legacy style tools regain command-level authority."
        if domain == "ts-lint-format":
            return "Consolidate the TS style layer under Biome before suppression and workspace drift grow."
        if domain == "security-posture":
            return "Tighten lockfile and ignore governance before today's baseline security gaps turn opaque."
    return None


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:
        return None, f"invalid: {exc}"


def extract_verdict(data: dict[str, Any]) -> str | None:
    for key in ("overall_health", "overall_verdict", "verdict", "status", "audit_mode", "mode"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return None


def extract_dependency_status(data: dict[str, Any]) -> str:
    status = data.get("dependency_status")
    if isinstance(status, str):
        return status
    return "ready"


def extract_dependency_failures(data: dict[str, Any]) -> list[dict[str, Any]]:
    failures = data.get("dependency_failures")
    if isinstance(failures, list):
        return [item for item in failures if isinstance(item, dict)]
    return []


def extract_findings(data: dict[str, Any]) -> list[dict[str, Any]]:
    findings = data.get("findings")
    if isinstance(findings, list):
        return [f for f in findings if isinstance(f, dict)]
    issues = data.get("issues")
    if isinstance(issues, list):
        return [f for f in issues if isinstance(f, dict)]
    return []


def extract_severity_counts(data: dict[str, Any]) -> dict[str, int]:
    sev = data.get("severity_counts")
    if isinstance(sev, dict):
        return {
            "critical": int(sev.get("critical", 0) or 0),
            "high": int(sev.get("high", 0) or 0),
            "medium": int(sev.get("medium", 0) or 0),
            "low": int(sev.get("low", 0) or 0),
        }
    findings = extract_findings(data)
    counter = Counter((f.get("severity") or "low") for f in findings)
    return {
        "critical": int(counter.get("critical", 0)),
        "high": int(counter.get("high", 0)),
        "medium": int(counter.get("medium", 0)),
        "low": int(counter.get("low", 0)),
    }


def extract_top_categories(data: dict[str, Any], limit: int = 3) -> list[str]:
    counter = Counter()
    for finding in extract_findings(data):
        category = finding.get("category") or finding.get("gate") or finding.get("domain") or finding.get("kind")
        if isinstance(category, str):
            counter[category] += 1
    return [cat for cat, _ in counter.most_common(limit)]


def classify_run(
    data: dict[str, Any] | None,
    err: str | None,
    *,
    expected_skill: str,
    expected_run_id: str,
) -> tuple[str, str]:
    if err == "missing":
        return "missing", "summary file not found"
    if err and err.startswith("invalid"):
        return "invalid", err
    if not data:
        return "missing", "summary file not found"
    actual_skill = str(data.get("skill") or "")
    if actual_skill and actual_skill != expected_skill:
        return "invalid", f"summary skill mismatch: expected {expected_skill}, got {actual_skill}"
    actual_run_id = str(data.get("run_id") or "")
    if expected_run_id and actual_run_id != expected_run_id:
        return "invalid", f"run_id mismatch: expected {expected_run_id}, got {actual_run_id or '-'}"
    if extract_dependency_status(data) == "blocked":
        return "blocked", ""
    verdict = extract_verdict(data)
    if verdict == "not-applicable":
        return "not-applicable", "child skill marked this domain not applicable"
    return "present", ""


def normalize_health(skill_runs: list[dict[str, Any]]) -> tuple[str, str]:
    present = [run for run in skill_runs if run["status"] in {"present", "not-applicable", "blocked"}]
    missing = [run for run in skill_runs if run["status"] in {"missing", "invalid"}]
    blocked = False
    watch = False

    for run in skill_runs:
        if run["status"] == "blocked" or run.get("dependency_status") == "blocked":
            blocked = True
            continue
        verdict = str(run.get("child_verdict") or "").lower()
        sev = run.get("severity_counts") or {}
        if int(sev.get("critical", 0)) > 0 or int(sev.get("high", 0)) > 0:
            blocked = True
        elif int(sev.get("medium", 0)) > 0:
            watch = True
        if verdict in RED_VERDICTS:
            blocked = True
        elif verdict in YELLOW_VERDICTS:
            watch = True

    if not present:
        return "not-applicable", "No child summary was available to aggregate."
    if all(run["status"] == "not-applicable" for run in present) and not missing:
        return "not-applicable", "Every available child skill marked the repository not applicable for its domain."
    if blocked:
        return "blocked", "At least one audit domain reports blocker-level risk or high-severity findings."
    if len(missing) >= 3:
        return "partial-coverage", "The rollup exists, but too many expected audit domains are missing or invalid."
    if watch or missing:
        return "watch", "No blocker domain was detected, but medium-severity findings or coverage gaps remain."
    return "healthy", "The aggregated audit set shows no visible blocker domains and coverage is reasonably complete."


def write_markdown(report: dict[str, Any], out_path: Path) -> None:
    lines = [
        "# Repo Health Report",
        "",
        f"- run_id: `{report['run_id']}`",
        f"- overall_health: `{report['overall_health']}`",
        f"- coverage_status: `{report['coverage_status']}`",
        f"- summary: {report['summary_line']}",
        "",
        "## Coverage map",
        "",
        "| Domain | Skill | Status | Dependency | Child verdict | Top categories | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in report["skill_runs"]:
        lines.append(
            f"| {run['domain']} | {run['skill_name']} | {run['status']} | "
            f"{run.get('dependency_status') or ''} | "
            f"{run.get('child_verdict') or ''} | "
            f"{', '.join(run.get('top_categories') or [])} | "
            f"{run.get('notes') or ''} |"
        )
    lines.append("")
    if report.get("top_actions"):
        lines.extend(["## Top actions", ""])
        for action in report["top_actions"]:
            lines.append(f"- {action}")
        lines.append("")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_bootstrap_payload(path: Path | None) -> dict[str, Any]:
    if not path:
        return {
            "dependency_status": "ready",
            "bootstrap_actions": [],
            "dependency_failures": [],
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "dependency_status": str(data.get("dependency_status") or "ready"),
        "bootstrap_actions": [item for item in data.get("bootstrap_actions") or [] if isinstance(item, dict)],
        "dependency_failures": [item for item in data.get("dependency_failures") or [] if isinstance(item, dict)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--harness-dir", required=False)
    parser.add_argument("--bootstrap-json", required=False)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=False)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    harness = Path(args.harness_dir).resolve() if args.harness_dir else repo / ".repo-harness"
    bootstrap_payload = load_bootstrap_payload(Path(args.bootstrap_json).resolve() if args.bootstrap_json else None)

    skill_runs = []
    missing_skills = []
    invalid_summaries = []

    for domain, skill_name in EXPECTED:
        summary_path = child_summary_path(harness, domain)
        report_path = child_report_path(harness, domain)
        agent_brief_path = child_agent_brief_path(harness, domain)
        data, err = load_json(summary_path)
        status, classification_note = classify_run(
            data,
            err,
            expected_skill=skill_name,
            expected_run_id=args.run_id,
        )
        child_verdict = extract_verdict(data) if data else None
        dependency_status = extract_dependency_status(data or {})
        dependency_failures = extract_dependency_failures(data or {})
        sev = extract_severity_counts(data or {})
        top_categories = extract_top_categories(data or {})
        notes = classification_note
        if status == "missing":
            missing_skills.append(skill_name)
        elif status == "invalid":
            invalid_summaries.append(skill_name)
        elif status == "blocked":
            first_failure = dependency_failures[0] if dependency_failures else {}
            failure_name = str(first_failure.get("name") or "dependency")
            failure_reason = str(first_failure.get("failure_reason") or "dependency bootstrap blocked the child skill")
            notes = f"{failure_name}: {failure_reason}"
        elif domain == "llm-api-freshness" and child_verdict == "triage":
            notes = "this run only produced local surface triage; current docs were not verified"
        elif domain == "llm-api-freshness" and child_verdict == "verified":
            notes = "current provider docs were verified for the detected surfaces"

        skill_runs.append({
            "run_id": args.run_id,
            "domain": domain,
            "skill_name": skill_name,
            "status": status,
            "summary_path": str(summary_path.resolve()),
            "report_path": str(report_path.resolve()),
            "agent_brief_path": str(agent_brief_path.resolve()),
            "dependency_status": dependency_status,
            "dependency_failures": dependency_failures,
            "child_verdict": child_verdict,
            "severity_counts": sev,
            "top_categories": top_categories,
            "notes": notes,
        })

    overall_health, summary_line = normalize_health(skill_runs)
    coverage_status = "complete" if not missing_skills and not invalid_summaries else "partial"

    top_actions: list[str] = []
    for run in skill_runs:
        action = recommended_domain_action(run, coverage_status=coverage_status)
        if action and action not in top_actions:
            top_actions.append(action)

    report = {
        "schema_version": "1.0",
        "run_id": args.run_id,
        "skill": "repo-health-orchestrator",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo),
        "overall_health": overall_health,
        "coverage_status": coverage_status,
        "summary_line": summary_line,
        "skill_runs": skill_runs,
        "top_actions": top_actions[:5],
        "missing_skills": missing_skills,
        "invalid_summaries": invalid_summaries,
        "dependency_status": bootstrap_payload["dependency_status"],
        "bootstrap_actions": bootstrap_payload["bootstrap_actions"],
        "dependency_failures": bootstrap_payload["dependency_failures"],
    }

    out_json = Path(args.out_json).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.out_md:
        write_markdown(report, Path(args.out_md).resolve())
    print(f"Wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
