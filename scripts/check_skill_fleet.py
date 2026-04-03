#!/usr/bin/env python3
"""Static contract checks for the pooh-skills fleet."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
ALLOWED_DESCRIPTION_PREFIXES = ("Audits ", "Coordinates ")
ALLOWED_FRONTMATTER_KEYS = {"name", "description"}
REQUIRED_EVAL_HEADERS = (
    "should trigger",
    "should not trigger",
    "false positive / regression cases",
)
REPO_HEALTH_EXTRA_EVAL_HEADERS = ("failure scenarios",)
SHARED_REF_MAP = {
    "output-contract.md": "shared-output-contract.md",
    "reporting-style.md": "shared-reporting-style.md",
    "runtime-artifact-contract.md": "shared-runtime-artifact-contract.md",
}
RUNTIME_MANIFEST_ALLOWED_KEYS = {
    "schema_version",
    "skill",
    "runtime_features",
    "tools",
}
VERDICT_CONTRACT_ALLOWED_KEYS = {
    "schema_version",
    "skill",
    "overall_verdicts",
    "rollup_map",
}
CHILD_SUMMARY_REQUIRED_KEYS = {
    "schema_version",
    "skill",
    "run_id",
    "generated_at",
    "repo_root",
    "overall_verdict",
    "rollup_bucket",
    "dependency_status",
    "dependency_failures",
    "bootstrap_actions",
    "severity_counts",
    "findings",
}
VALID_ROLLUP_BUCKETS = {"blocked", "red", "yellow", "green", "not-applicable"}
LIVE_DOC_SKILLS = {
    "llm-api-freshness-guard",
    "pydantic-ai-temporal-hardgate",
}
REQUIRED_LIVE_DOC_REFERENCES = (
    "references/live-doc-verification.md",
    "references/context7-query-playbook.md",
)
TIME_SENSITIVE_PATTERNS = (
    re.compile(r"\b20\d{2}\b"),
    re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+20\d{2}\b", re.IGNORECASE),
)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
CASE_LINE_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\S")
ORCHESTRATOR_EXEMPTIONS_FILE = "orchestrator-exempt-skills.json"


@dataclass
class CheckError:
    skill: str
    path: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check pooh-skills static fleet contracts.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--mode", choices=("fast", "strict"), default="fast")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def generated_shared_content(source_name: str, content: str) -> str:
    return (
        "<!-- GENERATED FILE. Edit shared/{name} and run "
        "`python3 scripts/sync_shared_skill_refs.py --write`. -->\n\n{body}".format(
            name=source_name,
            body=content.rstrip() + "\n",
        )
    )


def markdown_anchor_slug(heading: str) -> str:
    slug = heading.strip().lower()
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"[^\w\-\u4e00-\u9fff]", "", slug)
    return slug.strip("-")


def anchors_for_markdown(text: str) -> set[str]:
    return {markdown_anchor_slug(heading) for _, heading in HEADING_RE.findall(text)}


def parse_frontmatter(skill_name: str, path: Path, errors: list[CheckError]) -> tuple[dict[str, str], list[str], str]:
    text = read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        errors.append(CheckError(skill_name, str(path), "SKILL.md must start with frontmatter delimiter `---`."))
        return {}, lines, text

    closing_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_idx = idx
            break
    if closing_idx is None:
        errors.append(CheckError(skill_name, str(path), "SKILL.md frontmatter is not closed with `---`."))
        return {}, lines, text

    frontmatter: dict[str, str] = {}
    for idx, raw_line in enumerate(lines[1:closing_idx], start=2):
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if ":" not in line:
            errors.append(CheckError(skill_name, f"{path}:{idx}", "Frontmatter lines must use `key: value` format."))
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.lstrip()
        if key not in ALLOWED_FRONTMATTER_KEYS:
            errors.append(CheckError(skill_name, f"{path}:{idx}", f"Unsupported frontmatter key `{key}`."))
            continue
        if key == "description" and value and value[0] not in {'"', "'"} and re.search(r":\s", value):
            errors.append(CheckError(skill_name, f"{path}:{idx}", "Unquoted description contains a YAML-risk colon; quote the whole string."))
        if value.startswith(("'", '"')) and value.endswith(value[:1]) and len(value) >= 2:
            value = value[1:-1]
        if not value:
            errors.append(CheckError(skill_name, f"{path}:{idx}", f"Frontmatter key `{key}` may not be empty."))
            continue
        frontmatter[key] = value

    missing = ALLOWED_FRONTMATTER_KEYS - set(frontmatter)
    for key in sorted(missing):
        errors.append(CheckError(skill_name, str(path), f"Missing required frontmatter key `{key}`."))

    body_lines = lines[closing_idx + 1 :]
    return frontmatter, body_lines, text


def validate_description(skill_name: str, path: Path, description: str, errors: list[CheckError]) -> None:
    if len(description) > 1024:
        errors.append(CheckError(skill_name, str(path), "Description exceeds 1024 characters."))
    if not description.startswith(ALLOWED_DESCRIPTION_PREFIXES):
        allowed = " / ".join(prefix.strip() for prefix in ALLOWED_DESCRIPTION_PREFIXES)
        errors.append(CheckError(skill_name, str(path), f"Description must start with one of: {allowed}."))
    if " Use for " not in description:
        errors.append(CheckError(skill_name, str(path), "Description must contain `Use for` to define triggering conditions."))


def resolve_link_target(source: Path, target: str) -> tuple[Path | None, str | None]:
    target = target.strip()
    if target.startswith(("http://", "https://", "mailto:", "tel:")):
        return None, None
    if target.startswith("#"):
        return source, target[1:]
    path_part, _, anchor = target.partition("#")
    path_part = path_part.split("?", 1)[0]
    if not path_part:
        return source, anchor or None
    return (source.parent / path_part).resolve(), anchor or None


def check_links(skill_name: str, skill_dir: Path, errors: list[CheckError]) -> None:
    for path in skill_dir.rglob("*.md"):
        text = read_text(path)
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            resolved, anchor = resolve_link_target(path, target)
            if resolved is None:
                continue
            if not resolved.exists():
                errors.append(CheckError(skill_name, str(path), f"Broken local link target `{target}`."))
                continue
            if path.name == "SKILL.md":
                try:
                    resolved.relative_to(skill_dir)
                except ValueError:
                    errors.append(CheckError(skill_name, str(path), f"SKILL.md link `{target}` escapes the skill directory and will break on install."))
            if anchor:
                anchors = anchors_for_markdown(read_text(resolved))
                if anchor not in anchors:
                    errors.append(CheckError(skill_name, str(path), f"Missing markdown anchor `{anchor}` in `{target}`."))


def section_slice(text: str, header: str) -> str:
    lowered = text.lower()
    marker = f"## {header}".lower()
    start = lowered.find(marker)
    if start < 0:
        return ""
    next_match = re.search(r"^##\s+", text[start + len(marker) :], re.MULTILINE)
    if next_match is None:
        return text[start:]
    end = start + len(marker) + next_match.start()
    return text[start:end]


def count_cases(section_text: str) -> int:
    return sum(1 for line in section_text.splitlines() if CASE_LINE_RE.match(line))


def check_evals(skill_name: str, skill_dir: Path, mode: str, errors: list[CheckError]) -> None:
    evals_path = skill_dir / "references" / "evals.md"
    if not evals_path.exists():
        errors.append(CheckError(skill_name, str(evals_path), "Each skill must provide references/evals.md."))
        return

    evals_text = read_text(evals_path)
    required_headers = list(REQUIRED_EVAL_HEADERS)
    if skill_name == "repo-health-orchestrator":
        required_headers.extend(REPO_HEALTH_EXTRA_EVAL_HEADERS)

    for header in required_headers:
        section = section_slice(evals_text, header)
        if not section:
            errors.append(CheckError(skill_name, str(evals_path), f"Missing required eval section `## {header.title()}`."))
            continue
        if mode == "strict" and count_cases(section) < 1:
            errors.append(CheckError(skill_name, str(evals_path), f"Eval section `## {header.title()}` must contain at least one concrete case."))


def check_live_doc_contract(skill_name: str, skill_dir: Path, errors: list[CheckError]) -> None:
    skill_md = read_text(skill_dir / "SKILL.md")
    for relative_path in REQUIRED_LIVE_DOC_REFERENCES:
        target = skill_dir / relative_path
        if not target.exists():
            errors.append(CheckError(skill_name, str(target), f"Missing required live-doc reference `{relative_path}`."))
            continue
        if relative_path not in skill_md:
            errors.append(CheckError(skill_name, str(skill_dir / 'SKILL.md'), f"SKILL.md must link to `{relative_path}`."))

    if "Context7" not in skill_md:
        errors.append(CheckError(skill_name, str(skill_dir / "SKILL.md"), "Live-doc-sensitive skills must mention Context7 in SKILL.md."))

    live_doc_path = skill_dir / "references" / "live-doc-verification.md"
    if live_doc_path.exists():
        live_doc_text = read_text(live_doc_path)
        if "Context7" not in live_doc_text or "blocked" not in live_doc_text.lower():
            errors.append(CheckError(skill_name, str(live_doc_path), "live-doc-verification.md must define Context7 usage and blocked behavior."))

    run_all_path = skill_dir / "scripts" / "run_all.sh"
    if run_all_path.exists():
        run_all_text = read_text(run_all_path)
        if skill_name == "llm-api-freshness-guard":
            if 'EXTRA_DIR="$OUT_DIR/extra"' not in run_all_text or "surface-evidence.json" not in run_all_text or "triage" not in run_all_text:
                errors.append(CheckError(skill_name, str(run_all_path), "llm-api-freshness-guard run_all.sh must clearly operate in triage mode and emit the local evidence bundle."))
        elif "--doc-evidence-json" not in run_all_text:
            errors.append(CheckError(skill_name, str(run_all_path), "run_all.sh must accept --doc-evidence-json for live-doc-sensitive skills."))

    for pattern in TIME_SENSITIVE_PATTERNS:
        match = pattern.search(skill_md)
        if match:
            errors.append(CheckError(skill_name, str(skill_dir / "SKILL.md"), f"Time-sensitive literal `{match.group(0)}` found in SKILL.md; keep volatile guidance in live-doc references instead."))


def check_runtime_manifest(skill_name: str, skill_dir: Path, errors: list[CheckError]) -> None:
    manifest_path = skill_dir / "assets" / "runtime-dependencies.json"
    if not manifest_path.exists():
        errors.append(CheckError(skill_name, str(manifest_path), "Missing assets/runtime-dependencies.json."))
        return

    try:
        payload = json.loads(read_text(manifest_path))
    except json.JSONDecodeError as exc:
        errors.append(CheckError(skill_name, str(manifest_path), f"runtime-dependencies.json must be valid JSON: {exc}."))
        return

    extra_keys = sorted(set(payload) - RUNTIME_MANIFEST_ALLOWED_KEYS)
    if extra_keys:
        errors.append(CheckError(skill_name, str(manifest_path), f"runtime-dependencies.json has unsupported keys: {', '.join(extra_keys)}."))
    if not isinstance(payload.get("schema_version"), str) or not payload.get("schema_version"):
        errors.append(CheckError(skill_name, str(manifest_path), "runtime-dependencies.json must provide non-empty string `schema_version`."))
    if payload.get("skill") != skill_name:
        errors.append(CheckError(skill_name, str(manifest_path), f"runtime-dependencies.json `skill` must equal `{skill_name}`."))
    for key in ("runtime_features", "tools"):
        value = payload.get(key)
        if not isinstance(value, list):
            errors.append(CheckError(skill_name, str(manifest_path), f"runtime-dependencies.json `{key}` must be a list."))
        elif any(not isinstance(item, str) for item in value):
            errors.append(CheckError(skill_name, str(manifest_path), f"runtime-dependencies.json `{key}` must contain only strings."))


def check_summary_contract(skill_name: str, skill_dir: Path, errors: list[CheckError]) -> None:
    schema_candidates = sorted((skill_dir / "assets").glob("*summary.schema.json"))
    if not schema_candidates:
        errors.append(CheckError(skill_name, str(skill_dir / "assets"), "Missing child summary schema JSON."))
        return
    schema_path = schema_candidates[0]
    try:
        schema = json.loads(read_text(schema_path))
    except json.JSONDecodeError as exc:
        errors.append(CheckError(skill_name, str(schema_path), f"Summary schema must be valid JSON: {exc}."))
        return

    required = schema.get("required")
    if not isinstance(required, list):
        errors.append(CheckError(skill_name, str(schema_path), "Summary schema must declare a top-level `required` list."))
    else:
        missing = sorted(CHILD_SUMMARY_REQUIRED_KEYS - set(required))
        if missing:
            errors.append(CheckError(skill_name, str(schema_path), f"Summary schema missing required contract keys: {', '.join(missing)}."))

    verdict_contract_path = skill_dir / "assets" / "verdict-contract.json"
    if not verdict_contract_path.exists():
        errors.append(CheckError(skill_name, str(verdict_contract_path), "Missing assets/verdict-contract.json."))
        return
    try:
        contract = json.loads(read_text(verdict_contract_path))
    except json.JSONDecodeError as exc:
        errors.append(CheckError(skill_name, str(verdict_contract_path), f"verdict-contract.json must be valid JSON: {exc}."))
        return

    extra_keys = sorted(set(contract) - VERDICT_CONTRACT_ALLOWED_KEYS)
    if extra_keys:
        errors.append(CheckError(skill_name, str(verdict_contract_path), f"verdict-contract.json has unsupported keys: {', '.join(extra_keys)}."))
    if contract.get("schema_version") != "1.0":
        errors.append(CheckError(skill_name, str(verdict_contract_path), "verdict-contract.json must declare schema_version `1.0`."))
    if contract.get("skill") != skill_name:
        errors.append(CheckError(skill_name, str(verdict_contract_path), f"verdict-contract.json `skill` must equal `{skill_name}`."))

    verdicts = contract.get("overall_verdicts")
    rollup_map = contract.get("rollup_map")
    if not isinstance(verdicts, list) or not verdicts or any(not isinstance(item, str) or not item for item in verdicts):
        errors.append(CheckError(skill_name, str(verdict_contract_path), "verdict-contract.json `overall_verdicts` must be a non-empty string list."))
        return
    if not isinstance(rollup_map, dict):
        errors.append(CheckError(skill_name, str(verdict_contract_path), "verdict-contract.json `rollup_map` must be an object."))
        return

    missing_map = sorted(set(verdicts) - set(rollup_map))
    extra_map = sorted(set(rollup_map) - set(verdicts))
    if missing_map:
        errors.append(CheckError(skill_name, str(verdict_contract_path), f"rollup_map is missing verdicts: {', '.join(missing_map)}."))
    if extra_map:
        errors.append(CheckError(skill_name, str(verdict_contract_path), f"rollup_map contains unexpected verdicts: {', '.join(extra_map)}."))
    invalid_buckets = sorted(
        verdict
        for verdict, bucket in rollup_map.items()
        if bucket not in VALID_ROLLUP_BUCKETS
    )
    if invalid_buckets:
        errors.append(CheckError(skill_name, str(verdict_contract_path), f"rollup_map uses invalid buckets for: {', '.join(invalid_buckets)}."))


def check_canonical_shared_refs(skill_name: str, skill_dir: Path, skill_md: str, errors: list[CheckError]) -> None:
    repo_root = skill_dir.parents[1]
    shared_dir = repo_root / "shared"
    references_dir = skill_dir / "references"
    for source_name, target_name in SHARED_REF_MAP.items():
        source_path = shared_dir / source_name
        target_path = references_dir / target_name
        if not target_path.exists():
            errors.append(CheckError(skill_name, str(target_path), f"Missing canonical shared reference `{target_name}`."))
            continue
        expected = generated_shared_content(source_name, read_text(source_path))
        actual = read_text(target_path)
        if actual != expected:
            errors.append(CheckError(skill_name, str(target_path), f"`{target_name}` is out of sync with shared/{source_name}."))
        if target_name not in skill_md:
            errors.append(CheckError(skill_name, str(skill_dir / "SKILL.md"), f"SKILL.md must link to `references/{target_name}`."))


def check_packaging_noise(skill_name: str, skill_dir: Path, errors: list[CheckError]) -> None:
    for pycache_dir in skill_dir.rglob("__pycache__"):
        errors.append(CheckError(skill_name, str(pycache_dir), "Do not commit `__pycache__` directories inside skills."))
    for pyc_path in skill_dir.rglob("*.pyc"):
        errors.append(CheckError(skill_name, str(pyc_path), "Do not commit `.pyc` files inside skills."))
    agents_readme = skill_dir / "agents" / "README.md"
    if agents_readme.exists():
        errors.append(CheckError(skill_name, str(agents_readme), "Do not ship placeholder `agents/README.md`; either provide real agents metadata or omit the directory."))


def check_skill(skill_dir: Path, mode: str) -> list[CheckError]:
    errors: list[CheckError] = []
    skill_name = skill_dir.name
    skill_md_path = skill_dir / "SKILL.md"
    frontmatter, body_lines, skill_md = parse_frontmatter(skill_name, skill_md_path, errors)

    name = frontmatter.get("name")
    if name and name != skill_name:
        errors.append(CheckError(skill_name, str(skill_md_path), f"Frontmatter name `{name}` must match directory name `{skill_name}`."))
    if name and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        errors.append(CheckError(skill_name, str(skill_md_path), "Skill name must be kebab-case."))
    if len(body_lines) >= 500:
        errors.append(CheckError(skill_name, str(skill_md_path), "SKILL.md body must stay under 500 lines."))
    if "description" in frontmatter:
        validate_description(skill_name, skill_md_path, frontmatter["description"], errors)

    check_links(skill_name, skill_dir, errors)
    check_evals(skill_name, skill_dir, mode, errors)
    if mode == "strict":
        check_runtime_manifest(skill_name, skill_dir, errors)
        check_packaging_noise(skill_name, skill_dir, errors)
        if frontmatter.get("description", "").startswith("Audits "):
            check_canonical_shared_refs(skill_name, skill_dir, skill_md, errors)
            if skill_name != "repo-health-orchestrator":
                check_summary_contract(skill_name, skill_dir, errors)
        if skill_name in LIVE_DOC_SKILLS:
            check_live_doc_contract(skill_name, skill_dir, errors)
    return errors


def discover_skills(skills_dir: Path) -> Iterable[Path]:
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            yield child


def load_catalog_module(repo: Path):
    catalog_path = repo / "skills" / "repo-health-orchestrator" / "scripts" / "repo_health_catalog.py"
    spec = importlib.util.spec_from_file_location("repo_health_catalog_contract", catalog_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load orchestrator catalog from {catalog_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, catalog_path


def load_orchestrator_exemptions(repo: Path) -> tuple[set[str], Path]:
    exemptions_path = repo / "skills" / "repo-health-orchestrator" / "assets" / ORCHESTRATOR_EXEMPTIONS_FILE
    if not exemptions_path.exists():
        return set(), exemptions_path
    data = json.loads(read_text(exemptions_path))
    if not isinstance(data, dict) or not isinstance(data.get("exempt_audit_skills"), list):
        raise RuntimeError(f"{exemptions_path} must contain an `exempt_audit_skills` list.")
    return {
        item
        for item in data.get("exempt_audit_skills", [])
        if isinstance(item, str) and item
    }, exemptions_path


def audit_skill_names(skills_dir: Path) -> set[str]:
    names: set[str] = set()
    for skill_dir in discover_skills(skills_dir):
        temp_errors: list[CheckError] = []
        frontmatter, _, _ = parse_frontmatter(skill_dir.name, skill_dir / "SKILL.md", temp_errors)
        if frontmatter.get("description", "").startswith("Audits "):
            names.add(skill_dir.name)
    return names


def check_orchestrator_catalog(repo: Path, skills_dir: Path, errors: list[CheckError]) -> None:
    try:
        catalog_module, catalog_path = load_catalog_module(repo)
        exempt_skills, exemptions_path = load_orchestrator_exemptions(repo)
    except Exception as exc:
        errors.append(CheckError("repo-health-orchestrator", str(repo / "skills" / "repo-health-orchestrator"), str(exc)))
        return

    catalog_skills = set(getattr(catalog_module, "SKILL_NAMES", ()))
    actual_audit_skills = audit_skill_names(skills_dir)
    unmanaged_skills = sorted(actual_audit_skills - catalog_skills - exempt_skills)
    unknown_catalog_skills = sorted(catalog_skills - actual_audit_skills)
    unknown_exemptions = sorted(exempt_skills - actual_audit_skills)

    for skill_name in unmanaged_skills:
        errors.append(
            CheckError(
                "repo-health-orchestrator",
                str(catalog_path),
                f"Audit skill `{skill_name}` is not registered in repo_health_catalog.py and is not exempted in {ORCHESTRATOR_EXEMPTIONS_FILE}.",
            )
        )

    for skill_name in unknown_catalog_skills:
        errors.append(
            CheckError(
                "repo-health-orchestrator",
                str(catalog_path),
                f"Catalog references unknown audit skill `{skill_name}`.",
            )
        )

    for skill_name in unknown_exemptions:
        errors.append(
            CheckError(
                "repo-health-orchestrator",
                str(exemptions_path),
                f"Exemption references unknown audit skill `{skill_name}`.",
            )
        )

    for skill_name in sorted(catalog_skills):
        run_all = skills_dir / skill_name / "scripts" / "run_all.sh"
        if not run_all.exists():
            errors.append(
                CheckError(
                    skill_name,
                    str(run_all),
                    "Catalog-managed audit skills must provide scripts/run_all.sh.",
                )
            )


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    skills_dir = repo / "skills"
    if not skills_dir.exists():
        print(f"error: missing skills directory at {skills_dir}", file=sys.stderr)
        return 2

    all_errors: list[CheckError] = []
    skills_checked = 0
    for skill_dir in discover_skills(skills_dir):
        skills_checked += 1
        all_errors.extend(check_skill(skill_dir, args.mode))

    if args.mode == "strict":
        check_orchestrator_catalog(repo, skills_dir, all_errors)

    payload = {
        "repo_root": str(repo),
        "mode": args.mode,
        "skills_checked": skills_checked,
        "error_count": len(all_errors),
        "errors": [
            {
                "skill": error.skill,
                "path": error.path,
                "message": error.message,
            }
            for error in all_errors
        ],
    }

    if args.json_out:
        out_path = Path(args.json_out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if all_errors:
        for error in all_errors:
            print(f"{error.skill}: {error.path}: {error.message}", file=sys.stderr)
        return 1

    print(f"Checked {skills_checked} skills in {args.mode} mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
