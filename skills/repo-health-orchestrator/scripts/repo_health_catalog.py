#!/usr/bin/env python3
"""Shared catalog for repo-health orchestrator domains and artifact paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DomainSpec:
    domain: str
    skill_name: str
    title: str
    accent: str
    summary_filename: str
    report_filename: str
    agent_brief_filename: str
    cluster: str


@dataclass(frozen=True)
class ClusterSpec:
    cluster: str
    title: str
    domains: tuple[str, ...]


DOMAIN_SPECS: tuple[DomainSpec, ...] = (
    DomainSpec(
        domain="structure",
        skill_name="dependency-audit",
        title="Audit-Dependencies",
        accent="cyan",
        summary_filename="repo-audit-summary.json",
        report_filename="repo-audit-report.md",
        agent_brief_filename="repo-audit-agent-brief.md",
        cluster="governance-and-boundaries",
    ),
    DomainSpec(
        domain="contracts",
        skill_name="signature-contract-hardgate",
        title="Audit-Contracts",
        accent="mint",
        summary_filename="contract-hardgate-summary.json",
        report_filename="contract-hardgate-human-report.md",
        agent_brief_filename="contract-hardgate-agent-brief.md",
        cluster="governance-and-boundaries",
    ),
    DomainSpec(
        domain="durable-agents",
        skill_name="pydantic-ai-temporal-hardgate",
        title="Audit-Durable-Agents",
        accent="violet",
        summary_filename="pydantic-temporal-summary.json",
        report_filename="pydantic-temporal-human-report.md",
        agent_brief_filename="pydantic-temporal-agent-brief.md",
        cluster="production-correctness",
    ),
    DomainSpec(
        domain="llm-api-freshness",
        skill_name="llm-api-freshness-guard",
        title="Audit-LLM-Freshness",
        accent="mint",
        summary_filename="llm-api-freshness-summary.json",
        report_filename="llm-api-freshness-report.md",
        agent_brief_filename="llm-api-freshness-agent-brief.md",
        cluster="surface-freshness-and-cleanup",
    ),
    DomainSpec(
        domain="cleanup",
        skill_name="controlled-cleanup-hardgate",
        title="Audit-Cleanup",
        accent="gold",
        summary_filename="controlled-cleanup-summary.json",
        report_filename="controlled-cleanup-report.md",
        agent_brief_filename="controlled-cleanup-agent-brief.md",
        cluster="surface-freshness-and-cleanup",
    ),
    DomainSpec(
        domain="distributed-side-effects",
        skill_name="distributed-side-effect-hardgate",
        title="Audit-Distributed-Effects",
        accent="rose",
        summary_filename="distributed-side-effect-summary.json",
        report_filename="distributed-side-effect-report.md",
        agent_brief_filename="distributed-side-effect-agent-brief.md",
        cluster="production-correctness",
    ),
    DomainSpec(
        domain="pythonic-ddd-drift",
        skill_name="pythonic-ddd-drift-audit",
        title="Audit-Pythonic-Drift",
        accent="cyan",
        summary_filename="pythonic-ddd-drift-summary.json",
        report_filename="pythonic-ddd-drift-report.md",
        agent_brief_filename="pythonic-ddd-drift-agent-brief.md",
        cluster="governance-and-boundaries",
    ),
)

CLUSTER_SPECS: tuple[ClusterSpec, ...] = (
    ClusterSpec(
        cluster="production-correctness",
        title="Production Correctness",
        domains=("distributed-side-effects", "durable-agents"),
    ),
    ClusterSpec(
        cluster="governance-and-boundaries",
        title="Governance and Boundaries",
        domains=("contracts", "structure", "pythonic-ddd-drift"),
    ),
    ClusterSpec(
        cluster="surface-freshness-and-cleanup",
        title="Surface Freshness and Cleanup",
        domains=("llm-api-freshness", "cleanup"),
    ),
)

DOMAIN_BY_NAME = {spec.domain: spec for spec in DOMAIN_SPECS}
EXPECTED = tuple((spec.domain, spec.skill_name, spec.summary_filename) for spec in DOMAIN_SPECS)


def summary_path(harness_dir: Path, domain: str) -> Path:
    return harness_dir / DOMAIN_BY_NAME[domain].summary_filename


def report_path(harness_dir: Path, domain: str) -> Path:
    return harness_dir / DOMAIN_BY_NAME[domain].report_filename


def agent_brief_path(harness_dir: Path, domain: str) -> Path:
    return harness_dir / DOMAIN_BY_NAME[domain].agent_brief_filename
