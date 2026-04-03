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
        cluster="governance-and-boundaries",
    ),
    DomainSpec(
        domain="contracts",
        skill_name="signature-contract-hardgate",
        title="Audit-Contracts",
        accent="mint",
        cluster="governance-and-boundaries",
    ),
    DomainSpec(
        domain="pythonic-ddd-drift",
        skill_name="pythonic-ddd-drift-audit",
        title="Audit-Pythonic-Drift",
        accent="cyan",
        cluster="governance-and-boundaries",
    ),
    DomainSpec(
        domain="module-shape",
        skill_name="module-shape-hardgate",
        title="Audit-Module-Shape",
        accent="gold",
        cluster="governance-and-boundaries",
    ),
    DomainSpec(
        domain="schema-governance",
        skill_name="openapi-jsonschema-governance-audit",
        title="Audit-Schema-Governance",
        accent="violet",
        cluster="governance-and-boundaries",
    ),
    DomainSpec(
        domain="distributed-side-effects",
        skill_name="distributed-side-effect-hardgate",
        title="Audit-Distributed-Effects",
        accent="rose",
        cluster="runtime-correctness-and-failure-handling",
    ),
    DomainSpec(
        domain="durable-agents",
        skill_name="pydantic-ai-temporal-hardgate",
        title="Audit-Durable-Agents",
        accent="violet",
        cluster="runtime-correctness-and-failure-handling",
    ),
    DomainSpec(
        domain="error-governance",
        skill_name="error-governance-hardgate",
        title="Audit-Error-Governance",
        accent="mint",
        cluster="runtime-correctness-and-failure-handling",
    ),
    DomainSpec(
        domain="silent-failure",
        skill_name="overdefensive-silent-failure-hardgate",
        title="Audit-Silent-Failure",
        accent="rose",
        cluster="runtime-correctness-and-failure-handling",
    ),
    DomainSpec(
        domain="frontend-regression",
        skill_name="ts-frontend-regression-audit",
        title="Audit-Frontend-Regression",
        accent="rose",
        cluster="runtime-correctness-and-failure-handling",
    ),
    DomainSpec(
        domain="python-lint-format",
        skill_name="python-lint-format-audit",
        title="Audit-Python-Lint",
        accent="mint",
        cluster="engineering-quality-and-security",
    ),
    DomainSpec(
        domain="ts-lint-format",
        skill_name="ts-lint-format-audit",
        title="Audit-TS-Lint",
        accent="cyan",
        cluster="engineering-quality-and-security",
    ),
    DomainSpec(
        domain="security-posture",
        skill_name="python-ts-security-posture-audit",
        title="Audit-Security-Posture",
        accent="gold",
        cluster="engineering-quality-and-security",
    ),
    DomainSpec(
        domain="secrets-and-hardcode",
        skill_name="secrets-and-hardcode-audit",
        title="Audit-Secrets-Hardcode",
        accent="rose",
        cluster="engineering-quality-and-security",
    ),
    DomainSpec(
        domain="test-quality",
        skill_name="test-quality-audit",
        title="Audit-Test-Quality",
        accent="mint",
        cluster="engineering-quality-and-security",
    ),
    DomainSpec(
        domain="llm-api-freshness",
        skill_name="llm-api-freshness-guard",
        title="Audit-LLM-Freshness",
        accent="mint",
        cluster="surface-freshness-and-cleanup",
    ),
    DomainSpec(
        domain="cleanup",
        skill_name="controlled-cleanup-hardgate",
        title="Audit-Cleanup",
        accent="gold",
        cluster="surface-freshness-and-cleanup",
    ),
)

CLUSTER_SPECS: tuple[ClusterSpec, ...] = (
    ClusterSpec(
        cluster="governance-and-boundaries",
        title="Governance and Boundaries",
        domains=("structure", "contracts", "pythonic-ddd-drift", "module-shape", "schema-governance"),
    ),
    ClusterSpec(
        cluster="runtime-correctness-and-failure-handling",
        title="Runtime Correctness and Failure Handling",
        domains=("distributed-side-effects", "durable-agents", "error-governance", "silent-failure", "frontend-regression"),
    ),
    ClusterSpec(
        cluster="engineering-quality-and-security",
        title="Engineering Quality and Security",
        domains=("python-lint-format", "ts-lint-format", "security-posture", "secrets-and-hardcode", "test-quality"),
    ),
    ClusterSpec(
        cluster="surface-freshness-and-cleanup",
        title="Surface Freshness and Cleanup",
        domains=("llm-api-freshness", "cleanup"),
    ),
)

DOMAIN_BY_NAME = {spec.domain: spec for spec in DOMAIN_SPECS}
SKILL_NAMES = tuple(spec.skill_name for spec in DOMAIN_SPECS)
EXPECTED = tuple((spec.domain, spec.skill_name) for spec in DOMAIN_SPECS)


def artifact_dir(harness_dir: Path, domain: str) -> Path:
    return harness_dir / "skills" / DOMAIN_BY_NAME[domain].skill_name


def summary_path(harness_dir: Path, domain: str) -> Path:
    return artifact_dir(harness_dir, domain) / "summary.json"


def report_path(harness_dir: Path, domain: str) -> Path:
    return artifact_dir(harness_dir, domain) / "report.md"


def agent_brief_path(harness_dir: Path, domain: str) -> Path:
    return artifact_dir(harness_dir, domain) / "agent-brief.md"


def runtime_path(harness_dir: Path, domain: str) -> Path:
    return artifact_dir(harness_dir, domain) / "runtime.json"


def manifest_path(skills_dir: Path, domain: str) -> Path:
    return skills_dir / DOMAIN_BY_NAME[domain].skill_name / "assets" / "runtime-dependencies.json"
