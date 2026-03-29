#!/usr/bin/env python3
"""Aggregate machine-readable audit summaries into one repo-health summary."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED = [
    ("structure", "dependency-audit", "repo-audit-summary.json"),
    ("contracts", "signature-contract-hardgate", "contract-hardgate-summary.json"),
    ("durable-agents", "pydantic-ai-temporal-hardgate", "pydantic-temporal-summary.json"),
    ("llm-api-freshness", "llm-api-freshness-guard", "llm-api-freshness-summary.json"),
    ("cleanup", "controlled-cleanup-hardgate", "controlled-cleanup-summary.json"),
    ("distributed-side-effects", "distributed-side-effect-hardgate", "distributed-side-effect-summary.json"),
    ("pythonic-ddd-drift", "pythonic-ddd-drift-audit", "pythonic-ddd-drift-summary.json"),
]

RED_VERDICTS = {
    "unsafe",
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
    "soft-gates",
    "baseline-needed",
    "cleanup-first",
    "boundary-hardening",
    "incremental-governance",
    "paper-guardrails",
    "partially-contained",
    "scan-blocked",
    "local-scan-only",
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


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:
        return None, f"invalid: {exc}"


def extract_verdict(data: dict[str, Any]) -> str | None:
    for key in ("overall_health", "overall_verdict", "verdict", "status", "mode"):
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
        category = (
            finding.get("category")
            or finding.get("gate")
            or finding.get("domain")
            or finding.get("kind")
        )
        if isinstance(category, str):
            counter[category] += 1
    return [cat for cat, _ in counter.most_common(limit)]


def domain_status(data: dict[str, Any] | None, err: str | None) -> str:
    if err == "missing":
        return "missing"
    if err and err.startswith("invalid"):
        return "invalid"
    if not data:
        return "missing"
    if extract_dependency_status(data) == "blocked":
        return "blocked"
    verdict = extract_verdict(data)
    if verdict == "not-applicable":
        return "not-applicable"
    return "present"


def normalize_health(skill_runs: list[dict[str, Any]]) -> tuple[str, str]:
    present = [run for run in skill_runs if run["status"] in {"present", "not-applicable", "blocked"}]
    missing = [run for run in skill_runs if run["status"] in {"missing", "invalid"}]
    blocked = False
    watch = False

    for run in skill_runs:
        if run["status"] == "blocked" or run.get("dependency_status") == "blocked":
            blocked = True
            continue
        verdict = (run.get("child_verdict") or "").lower()
        sev = run.get("severity_counts") or {}
        if int(sev.get("critical", 0)) > 0 or int(sev.get("high", 0)) > 0:
            blocked = True
        elif int(sev.get("medium", 0)) > 0:
            watch = True

        if verdict in RED_VERDICTS:
            blocked = True
        elif verdict in YELLOW_VERDICTS:
            watch = True
        elif verdict in POSITIVE_VERDICTS:
            pass

    if len(present) == 0:
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
    lines = []
    lines.append("# Repo Health Report")
    lines.append("")
    lines.append(f"- overall_health: `{report['overall_health']}`")
    lines.append(f"- coverage_status: `{report['coverage_status']}`")
    lines.append(f"- summary: {report['summary_line']}")
    lines.append("")
    lines.append("## Coverage map")
    lines.append("")
    lines.append("| Domain | Skill | Status | Dependency | Child verdict | Top categories | Notes |")
    lines.append("|---|---|---|---|---|---|---|")
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
        lines.append("## Top actions")
        lines.append("")
        for action in report["top_actions"]:
            lines.append(f"- {action}")
        lines.append("")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--harness-dir", required=False)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=False)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    harness = Path(args.harness_dir).resolve() if args.harness_dir else repo / ".repo-harness"

    skill_runs = []
    missing_skills = []
    invalid_summaries = []

    for domain, skill_name, filename in EXPECTED:
        summary_path = harness / filename
        data, err = load_json(summary_path)
        status = domain_status(data, err)
        child_verdict = extract_verdict(data) if data else None
        dependency_status = extract_dependency_status(data or {})
        dependency_failures = extract_dependency_failures(data or {})
        sev = extract_severity_counts(data or {})
        top_categories = extract_top_categories(data or {})
        notes = ""
        if err == "missing":
            missing_skills.append(skill_name)
            notes = "summary file not found"
        elif err:
            invalid_summaries.append(filename)
            notes = err
        elif status == "blocked":
            first_failure = dependency_failures[0] if dependency_failures else {}
            failure_name = str(first_failure.get("name") or "dependency")
            failure_reason = str(first_failure.get("failure_reason") or "dependency bootstrap blocked the child skill")
            notes = f"{failure_name}: {failure_reason}"
        elif status == "not-applicable":
            notes = "child skill marked this domain not applicable"
        elif domain == "llm-api-freshness" and child_verdict == "local-scan-only":
            notes = "current provider docs were not verified in this run"
        elif domain == "llm-api-freshness" and child_verdict == "verified":
            notes = "current provider docs were verified for the detected surfaces"

        skill_runs.append({
            "domain": domain,
            "skill_name": skill_name,
            "status": status,
            "summary_path": str(summary_path),
            "dependency_status": dependency_status,
            "dependency_failures": dependency_failures,
            "child_verdict": child_verdict,
            "severity_counts": sev,
            "top_categories": top_categories,
            "notes": notes,
        })

    overall_health, summary_line = normalize_health(skill_runs)
    coverage_status = "complete" if not missing_skills and not invalid_summaries else "partial"

    # top actions derived from blocker/watch domains
    top_actions = []
    for run in skill_runs:
        if run["status"] == "blocked":
            failures = run.get("dependency_failures") or []
            if failures:
                failure = failures[0]
                top_actions.append(
                    f"Unblock {run['skill_name']} first: restore `{failure.get('name')}` so the audit can run before trusting {run['domain']} coverage."
                )
            else:
                top_actions.append(
                    f"Unblock {run['skill_name']} first: restore its runtime prerequisites before trusting {run['domain']} coverage."
                )
            continue

        if run["status"] != "present":
            continue
        sev = run["severity_counts"]
        if sev["critical"] > 0 or sev["high"] > 0:
            if run["domain"] == "distributed-side-effects":
                top_actions.append("Fix distributed side-effect correctness first: remove dual writes, add durable handoff, and prove idempotency.")
            elif run["domain"] == "contracts":
                top_actions.append("Turn contract theater into machine enforcement: harden compile-time, runtime, and merge gates.")
            elif run["domain"] == "structure":
                top_actions.append("Stop structural debt from spreading: freeze boundary violations and cycles before other cleanup.")
            elif run["domain"] == "pythonic-ddd-drift":
                top_actions.append("Repair boundary leaks and flatten ceremonial Python layers before adding more abstractions.")
            elif run["domain"] == "cleanup":
                top_actions.append("Delete expired compatibility surfaces that are still distorting the codebase.")
            elif run["domain"] == "durable-agents":
                top_actions.append("Repair durable-agent path correctness before trusting Temporal / pydantic-ai behavior.")
            elif run["domain"] == "llm-api-freshness":
                top_actions.append("Verify current provider docs and migrate stale LLM SDK or endpoint usage before the next AI-facing change.")
        elif sev["medium"] > 0:
            if run["domain"] == "pythonic-ddd-drift":
                top_actions.append("Trim abstraction bloat where it adds shape without policy.")
            elif run["domain"] == "cleanup":
                top_actions.append("Use cleanup debt reduction as a leverage move, not cosmetic tidying.")
            elif run["domain"] == "structure":
                top_actions.append("Stabilize dependency-audit config and workspace metadata before trying to harden boundaries.")
            elif run["domain"] == "llm-api-freshness":
                top_actions.append("Run a Context7-backed verification pass to separate real LLM API drift from local suspicion.")

    # remove duplicates while keeping order
    deduped_actions = []
    seen = set()
    for action in top_actions:
        if action not in seen:
            deduped_actions.append(action)
            seen.add(action)

    report = {
        "schema_version": "1.0",
        "skill": "repo-health-orchestrator",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo),
        "overall_health": overall_health,
        "coverage_status": coverage_status,
        "summary_line": summary_line,
        "skill_runs": skill_runs,
        "top_actions": deduped_actions[:5],
        "missing_skills": missing_skills,
        "invalid_summaries": invalid_summaries,
        "dependency_status": "ready",
        "bootstrap_actions": [],
        "dependency_failures": [],
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
