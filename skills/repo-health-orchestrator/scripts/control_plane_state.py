#!/usr/bin/env python3
"""Manage the repo-health orchestrator control-plane state."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from aggregate_repo_health import RED_VERDICTS
from aggregate_repo_health import EXPECTED

STATE_KIND = "repo-health-control-plane"
STATE_VERSION = "1.0"
FINAL_WORKER_STATUSES = {"complete", "blocked", "invalid", "missing", "not-applicable"}

WORKER_TITLES = {
    "structure": "Audit-Dependencies",
    "contracts": "Audit-Contracts",
    "durable-agents": "Audit-Durable-Agents",
    "cleanup": "Audit-Cleanup",
    "distributed-side-effects": "Audit-Distributed-Effects",
    "pythonic-ddd-drift": "Audit-Pythonic-Drift",
}

WORKER_ACCENTS = {
    "structure": "cyan",
    "contracts": "mint",
    "durable-agents": "violet",
    "cleanup": "gold",
    "distributed-side-effects": "rose",
    "pythonic-ddd-drift": "cyan",
}

STAGE_LABELS = {
    "reset-harness": "RESETTING HARNESS",
    "spawning": "SPAWNING SUBAGENTS",
    "running": "RUNNING (Audits Active)",
    "collecting": "COLLECTING ARTIFACTS",
    "aggregating": "AGGREGATING REPORTS",
    "done": "COMPLETE",
}

STAGE_TONES = {
    "reset-harness": "running",
    "spawning": "running",
    "running": "running",
    "collecting": "watch",
    "aggregating": "watch",
    "done": "healthy",
}

PROGRESS_BY_STAGE = {
    "reset-harness": 0.10,
    "spawning": 0.20,
    "collecting": 0.90,
    "aggregating": 1.00,
    "done": 1.00,
}

STATUS_LABELS = {
    "waiting": "WAITING",
    "running": "RUNNING",
    "complete": "COMPLETE",
    "blocked": "BLOCKED",
    "invalid": "INVALID",
    "missing": "MISSING",
    "not-applicable": "NOT APPLICABLE",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage repo-health control-plane state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a fresh control-plane state file.")
    add_common_state_args(init_parser)
    init_parser.add_argument("--context", default="repo-health-orchestrator")
    init_parser.add_argument("--model-label", default="Inherited from session")
    init_parser.add_argument("--reasoning-effort", default="Inherited")
    init_parser.add_argument("--summary-line", default="Preparing repo health audit run.")
    init_parser.add_argument("--stage", default="reset-harness", choices=list(STAGE_LABELS))
    init_parser.add_argument("--state-label", default=None)
    init_parser.add_argument("--state-tone", default=None)

    overall_parser = subparsers.add_parser("update-overall", help="Update overall control-plane fields.")
    add_common_state_args(overall_parser)
    overall_parser.add_argument("--stage", choices=list(STAGE_LABELS), default=None)
    overall_parser.add_argument("--state-label", default=None)
    overall_parser.add_argument("--state-tone", default=None)
    overall_parser.add_argument("--summary-line", default=None)
    overall_parser.add_argument("--model-label", default=None)
    overall_parser.add_argument("--reasoning-effort", default=None)
    overall_parser.add_argument("--overall-health", default=None)
    overall_parser.add_argument("--coverage-status", default=None)
    overall_parser.add_argument("--progress-ratio", type=float, default=None)
    overall_parser.add_argument("--auto-progress", action="store_true")

    worker_parser = subparsers.add_parser("update-worker", help="Update a single worker card.")
    add_common_state_args(worker_parser)
    worker_parser.add_argument("--domain", required=True)
    worker_parser.add_argument("--runtime-status", choices=list(STATUS_LABELS), default=None)
    worker_parser.add_argument("--model-label", default=None)
    worker_parser.add_argument("--status-label", default=None)
    worker_parser.add_argument("--detail", default=None)
    worker_parser.add_argument("--notes", default=None)
    worker_parser.add_argument("--child-verdict", default=None)
    worker_parser.add_argument("--summary-path", default=None)
    worker_parser.add_argument("--output-label", default=None)
    worker_parser.add_argument("--top-categories", nargs="*", default=None)
    worker_parser.add_argument("--severity-critical", type=int, default=None)
    worker_parser.add_argument("--severity-high", type=int, default=None)
    worker_parser.add_argument("--severity-medium", type=int, default=None)
    worker_parser.add_argument("--severity-low", type=int, default=None)

    final_parser = subparsers.add_parser(
        "finalize-from-summary",
        help="Project the final repo-health summary back into the control-plane state.",
    )
    add_common_state_args(final_parser)
    final_parser.add_argument("--summary", required=True)
    final_parser.add_argument("--model-label", default=None)
    final_parser.add_argument("--reasoning-effort", default=None)

    return parser.parse_args()


def add_common_state_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state", required=True, help="Path to repo-health-control-plane.json")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def to_output_label(path_value: str) -> str:
    if not path_value:
        return "No artifact"
    path = Path(path_value)
    parts = list(path.parts)
    if ".repo-harness" in parts:
        index = parts.index(".repo-harness")
        return "/" + "/".join(parts[index:])
    return str(path)


def default_state_path_values(state_path: Path, model_label: str | None = None) -> list[dict[str, Any]]:
    harness_dir = state_path.resolve().parent
    workers = []
    for index, (domain, skill_name, filename) in enumerate(EXPECTED, start=1):
        summary_path = str((harness_dir / filename).resolve())
        workers.append({
            "index": index,
            "domain": domain,
            "title": WORKER_TITLES.get(domain, domain.replace("-", " ").title()),
            "skill_name": skill_name,
            "model_label": model_label or "Inherited from session",
            "accent": WORKER_ACCENTS.get(domain, "cyan"),
            "runtime_status": "waiting",
            "status_label": STATUS_LABELS["waiting"],
            "summary_path": summary_path,
            "output_label": to_output_label(summary_path),
            "detail": "Not started yet",
            "notes": "",
            "child_verdict": "",
            "top_categories": [],
            "severity_counts": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
        })
    return workers


def completion_ratio(state: dict[str, Any]) -> float:
    workers = state.get("workers") or []
    if not workers:
        return 0.0
    done = sum(1 for worker in workers if worker.get("runtime_status") in FINAL_WORKER_STATUSES)
    return done / len(workers)


def derive_progress(stage: str, state: dict[str, Any], explicit: float | None) -> float:
    if explicit is not None:
        return clamp(explicit)
    if stage == "running":
        return clamp(0.20 + (completion_ratio(state) * 0.60))
    return clamp(PROGRESS_BY_STAGE.get(stage, state.get("overall", {}).get("progress_ratio", 0.0)))


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def ensure_state_shape(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("kind") != STATE_KIND:
        raise ValueError(f"unexpected state kind: {state.get('kind')!r}")
    if not isinstance(state.get("workers"), list):
        raise ValueError("state missing workers list")
    return state


def init_state(args: argparse.Namespace) -> dict[str, Any]:
    state_path = Path(args.state).resolve()
    stage = args.stage
    state_label = args.state_label or STAGE_LABELS[stage]
    state_tone = args.state_tone or STAGE_TONES[stage]
    state: dict[str, Any] = {
        "version": STATE_VERSION,
        "kind": STATE_KIND,
        "generated_at": utc_now(),
        "context": args.context,
        "overall": {
            "stage": stage,
            "progress_ratio": derive_progress(stage, {"workers": default_state_path_values(state_path, args.model_label)}, None),
            "state_tone": state_tone,
            "state_label": state_label,
            "model_label": args.model_label,
            "reasoning_effort": args.reasoning_effort,
            "summary_line": args.summary_line,
            "overall_health": "",
            "coverage_status": "",
        },
        "workers": default_state_path_values(state_path, args.model_label),
        "top_actions": [],
        "missing_skills": [],
        "invalid_summaries": [],
    }
    return state


def update_overall(args: argparse.Namespace) -> dict[str, Any]:
    state_path = Path(args.state).resolve()
    state = ensure_state_shape(load_json(state_path))
    overall = state["overall"]
    stage = args.stage or overall.get("stage") or "running"
    overall["stage"] = stage
    if args.state_label is not None:
        overall["state_label"] = args.state_label
    elif args.stage is not None:
        overall["state_label"] = STAGE_LABELS[stage]
    if args.state_tone is not None:
        overall["state_tone"] = args.state_tone
    elif args.stage is not None:
        overall["state_tone"] = STAGE_TONES[stage]
    if args.summary_line is not None:
        overall["summary_line"] = args.summary_line
    if args.model_label is not None:
        overall["model_label"] = args.model_label
    if args.reasoning_effort is not None:
        overall["reasoning_effort"] = args.reasoning_effort
    if args.overall_health is not None:
        overall["overall_health"] = args.overall_health
    if args.coverage_status is not None:
        overall["coverage_status"] = args.coverage_status
    if args.auto_progress or args.progress_ratio is not None or args.stage is not None:
        overall["progress_ratio"] = derive_progress(stage, state, args.progress_ratio)
    state["generated_at"] = utc_now()
    return state


def update_worker(args: argparse.Namespace) -> dict[str, Any]:
    state_path = Path(args.state).resolve()
    state = ensure_state_shape(load_json(state_path))
    target = None
    for worker in state["workers"]:
        if worker.get("domain") == args.domain:
            target = worker
            break
    if target is None:
        raise ValueError(f"unknown worker domain: {args.domain}")

    if args.runtime_status is not None:
        target["runtime_status"] = args.runtime_status
        target["status_label"] = args.status_label or STATUS_LABELS[args.runtime_status]
    elif args.status_label is not None:
        target["status_label"] = args.status_label
    if args.model_label is not None:
        target["model_label"] = args.model_label
    if args.detail is not None:
        target["detail"] = args.detail
    if args.notes is not None:
        target["notes"] = args.notes
    if args.child_verdict is not None:
        target["child_verdict"] = args.child_verdict
    if args.summary_path is not None:
        target["summary_path"] = args.summary_path
    if args.output_label is not None:
        target["output_label"] = args.output_label
    elif args.summary_path is not None:
        target["output_label"] = to_output_label(args.summary_path)
    if args.top_categories is not None:
        target["top_categories"] = args.top_categories

    severity = target.setdefault("severity_counts", {})
    if args.severity_critical is not None:
        severity["critical"] = args.severity_critical
    if args.severity_high is not None:
        severity["high"] = args.severity_high
    if args.severity_medium is not None:
        severity["medium"] = args.severity_medium
    if args.severity_low is not None:
        severity["low"] = args.severity_low

    state["generated_at"] = utc_now()
    return state


def status_from_summary_run(run: dict[str, Any]) -> tuple[str, str, str]:
    status = str(run.get("status") or "missing")
    verdict = str(run.get("child_verdict") or "").strip()
    severity = run.get("severity_counts") or {}
    critical = int(severity.get("critical", 0) or 0)
    high = int(severity.get("high", 0) or 0)
    verdict_key = verdict.lower()

    if status == "present":
        if critical > 0 or high > 0 or verdict_key in RED_VERDICTS:
            return "blocked", STATUS_LABELS["blocked"], verdict or "high-risk findings"
        return "complete", STATUS_LABELS["complete"], verdict or "artifact ready"
    if status == "not-applicable":
        return "not-applicable", STATUS_LABELS["not-applicable"], "domain not applicable"
    if status == "invalid":
        return "invalid", STATUS_LABELS["invalid"], verdict or "summary failed validation"
    return "missing", STATUS_LABELS["missing"], verdict or "artifact missing"


def tone_from_health(overall_health: str) -> tuple[str, str]:
    if overall_health == "blocked":
        return "blocked", "COMPLETE (Blocked Findings)"
    if overall_health == "healthy":
        return "healthy", "COMPLETE (Healthy)"
    if overall_health == "not-applicable":
        return "quiet", "COMPLETE (Not Applicable)"
    if overall_health == "partial-coverage":
        return "watch", "COMPLETE (Partial Coverage)"
    return "watch", "COMPLETE (Watch Items Active)"


def finalize_from_summary(args: argparse.Namespace) -> dict[str, Any]:
    state_path = Path(args.state).resolve()
    state = ensure_state_shape(load_json(state_path))
    summary = load_json(Path(args.summary).resolve())
    workers_by_domain = {worker["domain"]: worker for worker in state["workers"]}

    for run in summary.get("skill_runs") or []:
        domain = str(run.get("domain") or "")
        worker = workers_by_domain.get(domain)
        if worker is None:
            continue
        runtime_status, status_label, detail = status_from_summary_run(run)
        worker["runtime_status"] = runtime_status
        worker["status_label"] = status_label
        worker["detail"] = detail
        worker["notes"] = str(run.get("notes") or "")
        worker["child_verdict"] = str(run.get("child_verdict") or "")
        worker["summary_path"] = str(run.get("summary_path") or worker.get("summary_path") or "")
        worker["output_label"] = to_output_label(worker["summary_path"])
        worker["top_categories"] = [str(item) for item in run.get("top_categories") or []]
        worker["severity_counts"] = {
            "critical": int((run.get("severity_counts") or {}).get("critical", 0) or 0),
            "high": int((run.get("severity_counts") or {}).get("high", 0) or 0),
            "medium": int((run.get("severity_counts") or {}).get("medium", 0) or 0),
            "low": int((run.get("severity_counts") or {}).get("low", 0) or 0),
        }

    overall = state["overall"]
    overall_health = str(summary.get("overall_health") or "")
    state_tone, state_label = tone_from_health(overall_health)
    overall["stage"] = "done"
    overall["progress_ratio"] = 1.0
    overall["state_tone"] = state_tone
    overall["state_label"] = state_label
    overall["overall_health"] = overall_health
    overall["coverage_status"] = str(summary.get("coverage_status") or "")
    overall["summary_line"] = str(summary.get("summary_line") or "")
    if args.model_label is not None:
        overall["model_label"] = args.model_label
    if args.reasoning_effort is not None:
        overall["reasoning_effort"] = args.reasoning_effort

    state["top_actions"] = [str(item) for item in summary.get("top_actions") or []]
    state["missing_skills"] = [str(item) for item in summary.get("missing_skills") or []]
    state["invalid_summaries"] = [str(item) for item in summary.get("invalid_summaries") or []]
    state["generated_at"] = utc_now()
    return state


def main() -> int:
    args = parse_args()
    if args.command == "init":
        state = init_state(args)
    elif args.command == "update-overall":
        state = update_overall(args)
    elif args.command == "update-worker":
        state = update_worker(args)
    elif args.command == "finalize-from-summary":
        state = finalize_from_summary(args)
    else:
        raise ValueError(f"unsupported command: {args.command}")

    state_path = Path(args.state).resolve()
    write_json_atomic(state_path, state)
    print(f"Wrote {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
