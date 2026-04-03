#!/usr/bin/env python3
"""Synthesize richer repo-health evidence, report, and agent brief."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aggregate_repo_health import recommended_domain_action
from repo_health_catalog import CLUSTER_SPECS
from repo_health_catalog import DOMAIN_SPECS
from repo_health_catalog import agent_brief_path as child_agent_brief_path
from repo_health_catalog import report_path as child_report_path
from repo_health_catalog import summary_path as child_summary_path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build richer repo-health evidence and final markdown outputs.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--harness-dir", required=False)
    parser.add_argument("--out-evidence", required=True)
    parser.add_argument("--out-report", required=False)
    parser.add_argument("--out-brief", required=False)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return "", "missing"
    except Exception as exc:
        return "", f"invalid: {exc}"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def compact_excerpt(text: str, limit: int = 320) -> str:
    if not text.strip():
        return ""
    lines: list[str] = []
    in_fence = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:]
        lines.append(" ".join(stripped.split()))
        if len(lines) >= 3:
            break
    excerpt = " ".join(lines).strip()
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[: limit - 1].rstrip() + "…"


def run_risk_bucket(run: dict[str, Any]) -> tuple[int, str]:
    status = str(run.get("status") or "")
    dependency_status = str(run.get("dependency_status") or "ready")
    verdict = str(run.get("child_verdict") or "").lower()
    rollup_bucket = str(run.get("rollup_bucket") or "")

    if dependency_status == "blocked":
        return 0, "dependency-blocked"
    if status in {"missing", "invalid"}:
        return 4, "coverage-gap"
    if status == "not-applicable" or rollup_bucket == "not-applicable":
        return 9, "not-applicable"
    if rollup_bucket in {"blocked", "red"}:
        return 1, "high-risk"
    if verdict == "triage":
        return 3, "trust-gap"
    if rollup_bucket == "yellow":
        return 2, "watch"
    return 8, "stable"


def why_now(run: dict[str, Any], bucket_label: str) -> str:
    if bucket_label == "dependency-blocked":
        return "This domain never reached a trustworthy audit result because runtime prerequisites failed first."
    if bucket_label == "high-risk":
        return "This domain already carries blocker evidence or high-severity findings that can distort downstream work."
    if bucket_label == "watch":
        return "This domain is not a blocker yet, but leaving it alone will keep avoidable drift in the repo."
    if bucket_label == "trust-gap":
        return "This domain still needs stronger verification before its current surface can be trusted as clean."
    if bucket_label == "coverage-gap":
        return "The current rollup is incomplete here, so healthy signals elsewhere remain conditional."
    if bucket_label == "not-applicable":
        return "This domain does not currently apply to the repository."
    return "Current-run evidence does not surface urgency here."


def missing_detail(path: Path, err: str | None, label: str) -> dict[str, str] | None:
    if not err:
        return None
    if err == "missing":
        return {"kind": f"missing-{label}", "detail": f"{label} not produced at {path}"}
    return {"kind": f"invalid-{label}", "detail": f"{label} could not be read from {path}: {err}"}


def build_domain_records(summary: dict[str, Any], harness_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    runs_by_domain = {
        str(run.get("domain")): run
        for run in summary.get("skill_runs") or []
        if isinstance(run, dict)
    }
    domains: list[dict[str, Any]] = []
    unknowns: list[dict[str, str]] = []

    for spec in DOMAIN_SPECS:
        run = runs_by_domain.get(spec.domain, {})
        summary_path = Path(run.get("summary_path") or child_summary_path(harness_dir, spec.domain))
        report_path = Path(run.get("report_path") or child_report_path(harness_dir, spec.domain))
        brief_path = Path(run.get("agent_brief_path") or child_agent_brief_path(harness_dir, spec.domain))
        report_text, report_err = load_text(report_path)
        brief_text, brief_err = load_text(brief_path)
        evidence_gaps: list[str] = []

        if run.get("status") in {"missing", "invalid"}:
            evidence_gaps.append(f"{run.get('status')}-summary")
        report_gap = missing_detail(report_path, report_err, "human-report")
        if report_gap:
            unknowns.append({"scope": spec.domain, **report_gap})
            evidence_gaps.append(report_gap["kind"])
        brief_gap = missing_detail(brief_path, brief_err, "agent-brief")
        if brief_gap:
            unknowns.append({"scope": spec.domain, **brief_gap})
            evidence_gaps.append(brief_gap["kind"])

        bucket_rank, bucket_label = run_risk_bucket(run)
        domain_record = {
            "domain": spec.domain,
            "cluster": spec.cluster,
            "skill_name": spec.skill_name,
            "status": run.get("status") or "missing",
            "dependency_status": run.get("dependency_status") or "ready",
            "dependency_failures": run.get("dependency_failures") or [],
            "child_verdict": run.get("child_verdict") or "",
            "severity_counts": run.get("severity_counts") or {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "top_categories": run.get("top_categories") or [],
            "notes": run.get("notes") or "",
            "summary_path": str(summary_path.resolve()),
            "report_path": str(report_path.resolve()),
            "agent_brief_path": str(brief_path.resolve()),
            "report_excerpt": compact_excerpt(report_text),
            "brief_excerpt": compact_excerpt(brief_text),
            "evidence_gaps": evidence_gaps,
            "risk_rank": bucket_rank,
            "risk_label": bucket_label,
        }
        domains.append(domain_record)

        if bucket_label == "trust-gap":
            unknowns.append({
                "scope": spec.domain,
                "kind": "trust-gap",
                "detail": "Current evidence is still trust-limited and should not be mistaken for a fully verified clean bill.",
            })

    return domains, unknowns


def cluster_status(cluster_domains: list[dict[str, Any]]) -> str:
    if not cluster_domains:
        return "missing"
    if all(domain["status"] == "not-applicable" for domain in cluster_domains):
        return "not-applicable"
    if any(domain["risk_label"] in {"dependency-blocked", "high-risk"} for domain in cluster_domains):
        return "blocked"
    if any(domain["risk_label"] in {"watch", "trust-gap", "coverage-gap"} for domain in cluster_domains):
        return "watch"
    return "healthy"


def cluster_summary(cluster_title: str, status: str, domain_labels: list[str]) -> str:
    labels = ", ".join(domain_labels)
    if status == "blocked":
        return f"{cluster_title} is the main blocker cluster right now, driven by {labels}."
    if status == "watch":
        return f"{cluster_title} still needs cleanup or stronger proof before {labels} can be trusted as stable."
    if status == "not-applicable":
        return f"{cluster_title} is not currently in play for this repository."
    return f"{cluster_title} shows no visible blocker from the current run across {labels}."


def build_clusters(domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    domains_by_name = {domain["domain"]: domain for domain in domains}
    clusters: list[dict[str, Any]] = []
    for spec in CLUSTER_SPECS:
        members = [domains_by_name[name] for name in spec.domains if name in domains_by_name]
        top_category_counter = Counter()
        for member in members:
            top_category_counter.update(member.get("top_categories") or [])
        top_categories = [name for name, _ in top_category_counter.most_common(4)]
        status = cluster_status(members)
        clusters.append({
            "cluster": spec.cluster,
            "title": spec.title,
            "domains": [member["domain"] for member in members],
            "status": status,
            "top_categories": top_categories,
            "summary": cluster_summary(spec.title, status, [member["domain"] for member in members]),
        })
    return clusters


def build_ordered_actions(
    domains: list[dict[str, Any]],
    coverage_status: str,
    unknowns: list[dict[str, str]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for domain in domains:
        action = recommended_domain_action(domain, coverage_status=coverage_status)
        if not action:
            continue
        bucket_rank = int(domain["risk_rank"])
        if bucket_rank >= 8:
            continue
        tier = "now" if bucket_rank <= 1 else "next" if bucket_rank <= 3 else "later"
        actions.append({
            "domain": domain["domain"],
            "cluster": domain["cluster"],
            "tier": tier,
            "priority_rank": bucket_rank,
            "action": action,
            "why_now": why_now(domain, domain["risk_label"]),
        })

    if coverage_status == "partial":
        actions.append({
            "domain": "overall",
            "cluster": "cross-cutting",
            "tier": "later",
            "priority_rank": 4,
            "action": "Close the missing or invalid audit domains before treating the repo-health rollup as decision-complete.",
            "why_now": "Coverage gaps remain visible in the current run and should be closed before any clean verdict is trusted.",
        })

    deduped: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    for action in sorted(actions, key=lambda item: (item["priority_rank"], item["domain"], item["action"])):
        if action["action"] in seen_actions:
            continue
        seen_actions.add(action["action"])
        action["priority"] = len(deduped) + 1
        deduped.append(action)
    return deduped


def choose_domain_handoff(domain: dict[str, Any]) -> str:
    if domain.get("brief_excerpt"):
        return str(domain["brief_excerpt"])
    if domain.get("report_excerpt"):
        return str(domain["report_excerpt"])
    if domain.get("notes"):
        return str(domain["notes"])
    return "Read the child summary directly before making edits here."


def teaching_line(clusters: list[dict[str, Any]]) -> str:
    blocked = [cluster for cluster in clusters if cluster["status"] == "blocked"]
    watch = [cluster for cluster in clusters if cluster["status"] == "watch"]
    if blocked and blocked[0]["cluster"] == "governance-and-boundaries":
        return "It is teaching AI that local convenience outranks machine-enforced contracts and boundary discipline."
    if blocked and blocked[0]["cluster"] == "runtime-correctness-and-failure-handling":
        return "It is teaching AI to let side effects and durable execution outrun proof."
    if blocked and blocked[0]["cluster"] == "engineering-quality-and-security":
        return "It is teaching AI that modern engineering controls are optional, even when baseline quality and security still drift."
    if blocked and blocked[0]["cluster"] == "surface-freshness-and-cleanup":
        return "It is teaching AI to normalize stale interfaces and defer cleanup until drift becomes ambient."
    if watch:
        return "It is teaching AI that partial proof is good enough, even when structural doubts are still visible."
    return "It is teaching AI that current repository habits are at least consistent enough to keep reinforcement damage limited."


def render_report(evidence: dict[str, Any]) -> str:
    snapshot = evidence["overall_snapshot"]
    lines = [
        "# Repo Health Report",
        "",
        "## 1. Executive summary",
        "",
        f"- run_id: `{snapshot['run_id']}`",
        f"- overall_health: `{snapshot['overall_health']}`",
        f"- coverage_status: `{snapshot['coverage_status']}`",
        f"- one-line diagnosis: `{snapshot['summary_line']}`",
        "",
        "## 2. Coverage and trust",
        "",
        "| Domain | Status | Dependency | Verdict | Evidence gaps |",
        "|---|---|---|---|---|",
    ]
    for domain in evidence["domains"]:
        gaps = ", ".join(domain["evidence_gaps"]) if domain["evidence_gaps"] else ""
        lines.append(
            f"| {domain['domain']} | {domain['status']} | {domain['dependency_status']} | "
            f"{domain['child_verdict']} | {gaps} |"
        )

    lines.extend(["", "## 3. Root cause clusters", ""])
    for cluster in evidence["clusters"]:
        lines.extend([
            f"### {cluster['title']}",
            "",
            f"- status: `{cluster['status']}`",
            f"- domains: `{', '.join(cluster['domains'])}`",
            f"- top categories: `{', '.join(cluster['top_categories'])}`" if cluster["top_categories"] else "- top categories: `none surfaced`",
            "",
            cluster["summary"],
            "",
        ])

    risky_domains = [domain for domain in evidence["domains"] if domain["risk_rank"] <= 3]
    lines.extend(["## 4. Highest-risk domains", ""])
    if risky_domains:
        for domain in sorted(risky_domains, key=lambda item: (item["risk_rank"], item["domain"]))[:4]:
            lines.extend([
                f"### {domain['domain']}",
                "",
                f"- skill: `{domain['skill_name']}`",
                f"- status: `{domain['status']}`",
                f"- dependency_status: `{domain['dependency_status']}`",
                f"- child_verdict: `{domain['child_verdict']}`",
                f"- top_categories: `{', '.join(domain['top_categories'])}`" if domain["top_categories"] else "- top_categories: `none surfaced`",
                f"- why now: {why_now(domain, domain['risk_label'])}",
                "",
                f"Evidence: {domain['report_excerpt'] or domain['notes'] or 'No human-report excerpt was available.'}",
                "",
            ])
    else:
        lines.extend(["No current domain rises above stable/watch level from the available evidence.", ""])

    buckets = {"now": [], "next": [], "later": []}
    for action in evidence["ordered_actions"]:
        buckets[action["tier"]].append(action)

    lines.extend(["## 5. Ordered action queue", ""])
    for tier, title in (("now", "Now"), ("next", "Next"), ("later", "Later")):
        lines.extend([f"### {title}", ""])
        if buckets[tier]:
            for action in buckets[tier]:
                lines.append(f"- {action['action']} ({action['domain']}: {action['why_now']})")
        else:
            lines.append("- none")
        lines.append("")

    lines.extend(["## 6. Unknowns / evidence gaps", ""])
    if evidence["unknowns"]:
        for unknown in evidence["unknowns"]:
            lines.append(f"- [{unknown['scope']}] {unknown['kind']}: {unknown['detail']}")
    else:
        lines.append("- no additional evidence gaps were surfaced beyond the machine summary")
    lines.append("")

    lines.extend([
        "## 7. What this repo is teaching AI to do wrong overall",
        "",
        evidence["teaching_line"],
        "",
    ])
    return "\n".join(lines)


def render_agent_brief(evidence: dict[str, Any]) -> str:
    snapshot = evidence["overall_snapshot"]
    lines = [
        "# Repo Health Orchestrator Agent Brief",
        "",
        "Keep this brief short and action-ordered.",
        "",
        "## Overall",
        "",
        f"- run_id: `{snapshot['run_id']}`",
        f"- overall_health: `{snapshot['overall_health']}`",
        f"- coverage_status: `{snapshot['coverage_status']}`",
        f"- summary_line: `{snapshot['summary_line']}`",
        "",
        "## Action queue",
        "",
    ]
    if evidence["ordered_actions"]:
        for action in evidence["ordered_actions"][:5]:
            lines.append(f"{action['priority']}. `{action['action']}`")
    else:
        lines.append("1. `No immediate action queue was derived from current evidence.`")

    lines.extend(["", "## Domains", ""])
    for domain in evidence["domains"]:
        top_action = next(
            (action["action"] for action in evidence["ordered_actions"] if action["domain"] == domain["domain"]),
            "Maintain current posture and verify only if related work reopens this surface.",
        )
        lines.extend([
            f"### {domain['domain']}",
            "",
            f"- status: `{domain['status']}`",
            f"- dependency_status: `{domain['dependency_status']}`",
            f"- child_verdict: `{domain['child_verdict']}`",
            f"- top_categories: `{', '.join(domain['top_categories'])}`" if domain["top_categories"] else "- top_categories: `none surfaced`",
            f"- top_action: `{top_action}`",
            f"- why_now: `{why_now(domain, domain['risk_label'])}`",
            f"- handoff_notes: `{choose_domain_handoff(domain)}`",
            "",
        ])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    summary_path = Path(args.summary).resolve()
    harness_dir = Path(args.harness_dir).resolve() if args.harness_dir else repo / ".repo-harness"
    summary = load_json(summary_path)
    if summary.get("skill") != "repo-health-orchestrator":
        raise SystemExit(f"Unexpected summary skill field in {summary_path}")

    domains, unknowns = build_domain_records(summary, harness_dir)
    clusters = build_clusters(domains)
    ordered_actions = build_ordered_actions(domains, str(summary.get("coverage_status") or "complete"), unknowns)

    evidence = {
        "schema_version": "1.0",
        "skill": "repo-health-orchestrator",
        "kind": "repo-health-evidence",
        "run_id": str(summary.get("run_id") or ""),
        "generated_at": utc_now(),
        "repo_root": str(repo),
        "overall_snapshot": {
            "summary_path": str(summary_path),
            "run_id": str(summary.get("run_id") or ""),
            "overall_health": str(summary.get("overall_health") or ""),
            "coverage_status": str(summary.get("coverage_status") or ""),
            "summary_line": str(summary.get("summary_line") or ""),
            "top_actions": [str(item) for item in summary.get("top_actions") or []],
        },
        "domains": domains,
        "clusters": clusters,
        "ordered_actions": ordered_actions,
        "unknowns": unknowns,
        "teaching_line": teaching_line(clusters),
    }

    out_evidence = Path(args.out_evidence).resolve()
    out_evidence.parent.mkdir(parents=True, exist_ok=True)
    out_evidence.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.out_report:
        write_text(Path(args.out_report).resolve(), render_report(evidence))
    if args.out_brief:
        write_text(Path(args.out_brief).resolve(), render_agent_brief(evidence))

    print(f"Wrote {out_evidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
