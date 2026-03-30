#!/usr/bin/env python3
"""Finalize a verified llm-api-freshness audit from local evidence plus doc evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from llm_api_freshness_artifacts import render_agent_brief
from llm_api_freshness_artifacts import render_report
from validate_llm_api_freshness_summary import validate_summary


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize a verified LLM API freshness audit.")
    parser.add_argument("--evidence-json", required=True, help="Path to .repo-harness/llm-api-surface-evidence.json")
    parser.add_argument("--summary-in", required=True, help="Path to the agent-authored summary draft")
    parser.add_argument("--summary-out", required=True, help="Where to write the normalized summary")
    parser.add_argument("--report-out", required=True, help="Where to write the rendered report")
    parser.add_argument("--brief-out", required=True, help="Where to write the rendered agent brief")
    parser.add_argument("--doc-evidence-json", help="Optional JSON list/object containing doc_verification entries")
    return parser.parse_args(argv)


def merge_doc_verification(summary: dict[str, Any], doc_payload: Any) -> None:
    if doc_payload is None:
        return
    if isinstance(doc_payload, dict):
        entries = doc_payload.get("doc_verification", [])
    elif isinstance(doc_payload, list):
        entries = doc_payload
    else:
        raise ValueError("doc evidence must be a list or an object with doc_verification")

    merged = list(summary.get("doc_verification") or [])
    seen = {
        (
            str(item.get("surface_id")),
            str(item.get("library_id")),
            str(item.get("source_ref")),
            str(item.get("status")),
        )
        for item in merged
        if isinstance(item, dict)
    }
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = (
            str(entry.get("surface_id")),
            str(entry.get("library_id")),
            str(entry.get("source_ref")),
            str(entry.get("status")),
        )
        if key in seen:
            continue
        merged.append(entry)
        seen.add(key)
    summary["doc_verification"] = merged


def normalize_summary(summary: dict[str, Any], evidence_bundle: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(summary)
    normalized["skill"] = "llm-api-freshness-guard"
    normalized.setdefault("version", str(evidence_bundle.get("version") or "2.0.0"))
    normalized.setdefault("generated_at", str(evidence_bundle.get("generated_at") or ""))
    normalized.setdefault("audit_mode", "verified")
    normalized.setdefault("target_scope", str(evidence_bundle.get("target_scope") or "repo"))
    normalized.setdefault("repo_profile", dict(evidence_bundle.get("repo_profile") or {}))
    normalized.setdefault("surface_resolution", list(evidence_bundle.get("surface_candidates") or []))
    normalized.setdefault("doc_verification", [])
    normalized.setdefault("findings", [])
    normalized.setdefault("priorities", {"now": [], "next": [], "later": []})
    normalized.setdefault("scan_limitations", [])
    normalized.setdefault("dependency_status", "ready")
    normalized.setdefault("bootstrap_actions", [])
    normalized.setdefault("dependency_failures", [])
    return normalized


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    evidence_bundle = load_json(Path(args.evidence_json).resolve())
    summary = normalize_summary(load_json(Path(args.summary_in).resolve()), evidence_bundle)

    if args.doc_evidence_json:
        merge_doc_verification(summary, load_json(Path(args.doc_evidence_json).resolve()))

    errors = validate_summary(summary)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2

    write_json(Path(args.summary_out).resolve(), summary)
    write_text(Path(args.report_out).resolve(), render_report(summary))
    write_text(Path(args.brief_out).resolve(), render_agent_brief(summary))
    print(f"Wrote {Path(args.summary_out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
