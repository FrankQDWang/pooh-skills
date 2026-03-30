#!/usr/bin/env python3
"""Shared rendering helpers for llm-api-freshness-guard artifacts."""

from __future__ import annotations

import json
from typing import Any, Iterable

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def sort_findings(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (item for item in findings if isinstance(item, dict)),
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity") or "low"), 3),
            str(item.get("surface_id") or ""),
            str(item.get("kind") or ""),
            str(item.get("title") or ""),
        ),
    )


def surface_label(surface: dict[str, Any]) -> str:
    provider = surface.get("provider")
    wrapper = surface.get("wrapper")
    family = surface.get("surface_family") or "unknown"
    if provider and wrapper:
        return f"{provider} via {wrapper}"
    if provider:
        return str(provider)
    if wrapper:
        return f"{wrapper} ({family})"
    return str(family)


def summary_line(summary: dict[str, Any]) -> str:
    mode = str(summary.get("audit_mode") or "triage")
    surfaces = list(summary.get("surface_resolution") or [])
    findings = sort_findings(summary.get("findings") or [])
    verified = [item for item in findings if item.get("verification_status") == "verified"]
    if mode == "not-applicable":
        return "No Python / TypeScript LLM integration surface was detected in the audited scope."
    if mode == "blocked":
        return "Official freshness verification was blocked before the skill could produce a trustworthy result."
    if mode == "verified":
        if verified:
            return f"Verified freshness drift was found across {len(verified)} evidence-backed surface(s)."
        return f"Current docs were verified for {len(surfaces)} detected surface(s) without producing a blocker finding."
    if findings:
        return f"Local triage found {len(surfaces)} candidate surface(s) and {len(findings)} low-confidence freshness clues that still need Context7 verification."
    return f"Local triage found {len(surfaces)} candidate surface(s), but it did not verify current docs yet."


def render_report(summary: dict[str, Any]) -> str:
    surfaces = list(summary.get("surface_resolution") or [])
    findings = sort_findings(summary.get("findings") or [])
    verified_findings = [item for item in findings if item.get("verification_status") == "verified"]
    unresolved_surfaces = [
        surface for surface in surfaces
        if str(surface.get("resolution_level") or "") != "provider-resolved" or str(summary.get("audit_mode") or "") != "verified"
    ]
    priorities = summary.get("priorities") or {"now": [], "next": [], "later": []}
    doc_verification = list(summary.get("doc_verification") or [])

    lines = [
        "# LLM API Freshness Audit",
        "",
        "## Executive summary",
        f"- audit_mode: `{summary.get('audit_mode', 'triage')}`",
        f"- target_scope: `{summary.get('target_scope', 'repo')}`",
        f"- dependency_status: `{summary.get('dependency_status', 'ready')}`",
        f"- diagnosis: {summary_line(summary)}",
        f"- surface_count: `{len(surfaces)}`",
        f"- verified_doc_entries: `{len([item for item in doc_verification if item.get('status') == 'verified'])}`",
        "",
        "## Resolved surfaces",
        "",
        "| Surface | Resolution | Confidence | Language | Primary SDK | Version hints |",
        "|---|---|---|---|---|---|",
    ]
    if not surfaces:
        lines.append("| none | n/a | n/a | n/a | n/a | n/a |")
    else:
        for surface in surfaces:
            version_hints = ", ".join(surface.get("version_hints") or []) or "-"
            lines.append(
                f"| {surface_label(surface)} | `{surface.get('resolution_level', 'ambiguous')}` | "
                f"`{surface.get('confidence', 'low')}` | `{surface.get('language', 'unknown')}` | "
                f"`{surface.get('primary_sdk', 'unknown')}` | {version_hints} |"
            )

    lines.extend(["", "## Verified findings", ""])
    if not verified_findings:
        if str(summary.get("audit_mode") or "") == "verified":
            lines.append("No verified freshness drift was recorded in this run.")
        else:
            lines.append("No verified findings exist in this artifact. Triage output is not an official freshness verdict.")
    else:
        for finding in verified_findings:
            lines.extend(_report_finding_block(finding))

    lines.extend(["", "## Ambiguous / unverified surfaces", ""])
    if not unresolved_surfaces and str(summary.get("audit_mode") or "") == "verified":
        lines.append("No unresolved surface remained after the verified pass.")
    else:
        for surface in unresolved_surfaces:
            evidence = list(surface.get("evidence") or [])
            evidence_text = "; ".join(
                f"{item.get('path', '.')}"
                + (f":{item.get('line')}" if isinstance(item.get("line"), int) else "")
                for item in evidence[:3]
                if isinstance(item, dict)
            ) or "No strong code evidence captured."
            lines.append(
                f"- `{surface.get('surface_id', 'surface')}` {surface_label(surface)} "
                f"-> `{surface.get('resolution_level', 'ambiguous')}` / `{surface.get('confidence', 'low')}`. "
                f"Evidence: {evidence_text}"
            )

    lines.extend(["", "## Recommended actions", ""])
    for section in ("now", "next", "later"):
        lines.append(f"### {section}")
        actions = priorities.get(section) or []
        if not actions:
            lines.append("- none")
        else:
            for action in actions:
                lines.append(f"- {action}")

    lines.extend(["", "## Scan limitations", ""])
    limitations = list(summary.get("scan_limitations") or [])
    if not limitations:
        lines.append("- none")
    else:
        for item in limitations:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def render_agent_brief(summary: dict[str, Any]) -> str:
    surfaces = list(summary.get("surface_resolution") or [])
    findings = sort_findings(summary.get("findings") or [])
    priorities = summary.get("priorities") or {"now": [], "next": [], "later": []}

    lines = [
        "# LLM API Freshness Agent Brief",
        "",
        "Use this only as report-oriented handoff guidance. Do not silently rewrite provider integrations.",
        "",
        "## Run state",
        f"- audit_mode: `{summary.get('audit_mode', 'triage')}`",
        f"- target_scope: `{summary.get('target_scope', 'repo')}`",
        f"- dependency_status: `{summary.get('dependency_status', 'ready')}`",
        f"- diagnosis: {summary_line(summary)}",
        "",
        "## Ordered actions",
    ]
    for section in ("now", "next", "later"):
        actions = priorities.get(section) or ["none"]
        lines.append(f"### {section}")
        for action in actions:
            lines.append(f"- {action}")

    lines.extend(["", "## Surface queue", ""])
    if not surfaces:
        lines.append("- No LLM surface candidate was detected.")
    else:
        for surface in surfaces:
            lines.append(
                f"- `{surface.get('surface_id', 'surface')}` {surface_label(surface)} | "
                f"{surface.get('resolution_level', 'ambiguous')} | {surface.get('confidence', 'low')} | "
                f"primary_sdk={surface.get('primary_sdk', 'unknown')}"
            )

    lines.extend(["", "## Findings", "", "```yaml"])
    if not findings:
        lines.extend([
            "- id: llm-freshness-000",
            "  kind: no-finding",
            "  severity: low",
            "  title: No freshness finding was emitted in this artifact",
            "  verification_status: not-run",
            "  notes: Keep the current surface explicit and rerun the audit after meaningful LLM integration changes.",
        ])
    else:
        for finding in findings[:12]:
            lines.extend([
                f"- id: {finding.get('id', 'unknown')}",
                f"  surface_id: {finding.get('surface_id', 'surface')}",
                f"  kind: {finding.get('kind', 'unknown')}",
                f"  severity: {finding.get('severity', 'low')}",
                f"  resolution_level: {finding.get('resolution_level', 'ambiguous')}",
                f"  surface_family: {finding.get('surface_family', 'unknown')}",
                f"  provider: {json.dumps(finding.get('provider'), ensure_ascii=False)}",
                f"  wrapper: {json.dumps(finding.get('wrapper'), ensure_ascii=False)}",
                f"  title: {json.dumps(str(finding.get('title', '')), ensure_ascii=False)}",
                f"  current_behavior: {json.dumps(str(finding.get('current_behavior', '')), ensure_ascii=False)}",
                f"  current_expectation: {json.dumps(str(finding.get('current_expectation', '')), ensure_ascii=False)}",
                f"  verification_status: {finding.get('verification_status', 'not-run')}",
                f"  recommended_change_shape: {json.dumps(str(finding.get('recommended_change_shape', '')), ensure_ascii=False)}",
                "  evidence:",
            ])
            evidence = list(finding.get("evidence") or [])
            if not evidence:
                lines.append("    - none")
            else:
                for item in evidence[:4]:
                    if not isinstance(item, dict):
                        continue
                    path = item.get("path", ".")
                    line = item.get("line")
                    snippet = json.dumps(str(item.get("snippet", "")), ensure_ascii=False)
                    loc = f"{path}:{line}" if isinstance(line, int) else str(path)
                    lines.append(f"    - {loc} {snippet}")
    lines.extend(["```", ""])
    return "\n".join(lines)


def _report_finding_block(finding: dict[str, Any]) -> list[str]:
    evidence_lines = []
    for item in list(finding.get("evidence") or [])[:4]:
        if not isinstance(item, dict):
            continue
        loc = item.get("path", ".")
        if isinstance(item.get("line"), int):
            loc = f"{loc}:{item['line']}"
        evidence_lines.append(f"- `{loc}` {item.get('snippet', '')}")
    if not evidence_lines:
        evidence_lines.append("- No code evidence was attached.")

    return [
        f"### {finding.get('id', 'finding')} {finding.get('title', '')}",
        f"- kind: `{finding.get('kind', 'unknown')}`",
        f"- severity: `{finding.get('severity', 'low')}`",
        f"- verification_status: `{finding.get('verification_status', 'not-run')}`",
        f"- resolution_level: `{finding.get('resolution_level', 'ambiguous')}`",
        f"- provider: `{finding.get('provider') or 'unknown'}`",
        f"- wrapper: `{finding.get('wrapper') or 'none'}`",
        "",
        "**Current behavior**",
        str(finding.get("current_behavior", "")),
        "",
        "**Current expectation**",
        str(finding.get("current_expectation", "")),
        "",
        "**Recommended change shape**",
        str(finding.get("recommended_change_shape", "")),
        "",
        "**Evidence**",
        *evidence_lines,
        "",
    ]
