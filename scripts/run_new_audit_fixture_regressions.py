#!/usr/bin/env python3
"""Deterministic fixture regressions for the five newly integrated audit skills."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Case:
    name: str
    skill: str
    script_rel: str
    expected_verdict: str
    expected_states: dict[str, str]
    setup: callable


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_scan(repo: Path, script_rel: str) -> dict:
    out_dir = repo / ".repo-harness"
    summary = out_dir / "summary.json"
    report = out_dir / "report.md"
    brief = out_dir / "agent-brief.md"
    command = [
        "python3",
        str(REPO_ROOT / script_rel),
        "--repo",
        str(repo),
        "--summary-out",
        str(summary),
        "--report-out",
        str(report),
        "--agent-brief-out",
        str(brief),
    ]
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"{script_rel} failed for {repo}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
    payload = json.loads(summary.read_text(encoding="utf-8"))
    if not report.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"{script_rel}: report is empty")
    if not brief.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"{script_rel}: agent brief is empty")
    return payload


def assert_case(case: Case) -> None:
    tempdir = Path(tempfile.mkdtemp(prefix=f"{case.skill}-fixture-"))
    try:
        repo = tempdir / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        case.setup(repo)
        payload = run_scan(repo, case.script_rel)
        if payload.get("overall_verdict") != case.expected_verdict:
            raise RuntimeError(
                f"{case.name}: expected overall_verdict={case.expected_verdict}, got {payload.get('overall_verdict')}"
            )
        categories = {item["id"]: item["state"] for item in payload.get("categories", [])}
        for category_id, expected_state in case.expected_states.items():
            actual = categories.get(category_id)
            if actual != expected_state:
                raise RuntimeError(f"{case.name}: expected {category_id}={expected_state}, got {actual}")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def setup_python_ruff_enforced(repo: Path) -> None:
    write(
        repo / "pyproject.toml",
        """
[project]
name = "fixture"
version = "0.1.0"

[tool.ruff]
line-length = 100
        """.strip()
        + "\n",
    )
    write(repo / "src" / "app.py", "def greet(name: str) -> str:\n    return f'hi {name}'\n")
    write(
        repo / ".pre-commit-config.yaml",
        """
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff-check
        entry: uv run ruff check .
      - id: ruff-format
        name: ruff-format
        entry: uv run ruff format --check .
        """.strip()
        + "\n",
    )
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: uv run ruff check .
      - run: uv run ruff format --check .
        """.strip()
        + "\n",
    )


def setup_python_legacy(repo: Path) -> None:
    write(
        repo / "pyproject.toml",
        """
[project]
name = "fixture"
version = "0.1.0"

[tool.black]
line-length = 88

[tool.isort]
profile = "black"
        """.strip()
        + "\n",
    )
    write(repo / "src" / "legacy.py", "print('legacy')\n")
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: uv run black --check .
      - run: uv run isort --check-only .
      - run: uv run flake8 .
        """.strip()
        + "\n",
    )


def setup_ts_biome_enforced(repo: Path) -> None:
    write(
        repo / "package.json",
        json.dumps(
            {
                "name": "fixture",
                "private": True,
                "scripts": {
                    "lint": "biome check . && eslint .",
                },
            },
            indent=2,
        )
        + "\n",
    )
    write(repo / "biome.json", "{\n  \"formatter\": {\"enabled\": true}\n}\n")
    write(
        repo / "eslint.config.js",
        """
export default [{
  files: ["**/*.ts"],
  languageOptions: {
    parserOptions: {
      projectService: true,
      tsconfigRootDir: import.meta.dirname,
    },
  },
}];
        """.strip()
        + "\n",
    )
    write(repo / "tsconfig.json", "{\n  \"compilerOptions\": {\"strict\": true}\n}\n")
    write(repo / "src" / "index.ts", "export const value: string = 'ok';\n")
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: pnpm biome check .
      - run: pnpm eslint .
        """.strip()
        + "\n",
    )


def setup_ts_legacy(repo: Path) -> None:
    write(
        repo / "package.json",
        json.dumps(
            {
                "name": "fixture",
                "private": True,
                "scripts": {
                    "lint": "eslint .",
                    "format": "prettier --check .",
                },
            },
            indent=2,
        )
        + "\n",
    )
    write(repo / ".eslintrc.json", "{\n  \"root\": true\n}\n")
    write(repo / ".prettierrc", "{\n  \"semi\": true\n}\n")
    write(repo / "tsconfig.json", "{\n  \"compilerOptions\": {\"strict\": true}\n}\n")
    write(repo / "src" / "index.ts", "export const value = 'legacy';\n")


def setup_ts_workspace_partial(repo: Path) -> None:
    write(repo / "pnpm-workspace.yaml", "packages:\n  - packages/*\n")
    write(repo / "biome.json", "{\n  \"formatter\": {\"enabled\": true}\n}\n")
    write(
        repo / "packages" / "web" / "package.json",
        "{\n  \"name\": \"web\",\n  \"dependencies\": {\"react\": \"18.0.0\"}\n}\n",
    )
    write(repo / "packages" / "web" / "src" / "page.ts", "export const page = 'ok';\n")
    write(
        repo / "packages" / "admin" / "package.json",
        "{\n  \"name\": \"admin\",\n  \"dependencies\": {\"zod\": \"4.0.0\"}\n}\n",
    )
    write(repo / "packages" / "admin" / "src" / "page.ts", "export const page = 'ok';\n")


def setup_schema_enforced(repo: Path) -> None:
    write(
        repo / "package.json",
        json.dumps(
            {
                "name": "fixture",
                "private": True,
                "scripts": {
                    "schema:lint": "pnpm redocly lint openapi/openapi.yaml",
                    "schema:bundle": "pnpm redocly bundle openapi/openapi.yaml",
                },
            },
            indent=2,
        )
        + "\n",
    )
    write(repo / "redocly.yaml", "apis:\n  main:\n    root: ./openapi/openapi.yaml\n")
    write(repo / ".spectral.yaml", "extends: spectral:oas\n")
    write(
        repo / "openapi" / "openapi.yaml",
        """
openapi: 3.1.0
info:
  title: Fixture API
  version: "1.0.0"
paths: {}
        """.strip()
        + "\n",
    )
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: schema
on: [push]
jobs:
  schema:
    runs-on: ubuntu-latest
    steps:
      - run: pnpm redocly lint openapi/openapi.yaml
      - run: pnpm oasdiff openapi/openapi.yaml
      - run: echo upload-artifact schema-report
        """.strip()
        + "\n",
    )


def setup_schema_generated_only(repo: Path) -> None:
    write(repo / "generated" / "client-openapi.json", "{\n  \"openapi\": \"3.0.0\"\n}\n")


def setup_frontend_enforced(repo: Path) -> None:
    write(
        repo / "package.json",
        json.dumps(
            {
                "name": "fixture",
                "private": True,
                "scripts": {
                    "test:browser": "vitest --browser",
                    "test:e2e": "playwright test",
                },
            },
            indent=2,
        )
        + "\n",
    )
    write(repo / "src" / "App.tsx", "export function App() { return <main>Hello</main>; }\n")
    write(repo / "playwright.config.ts", "export default { retries: 1 };\n")
    write(repo / "vitest.config.ts", "export default { test: { browser: { enabled: true } } };\n")
    write(repo / "mocks" / "handlers.ts", "import { http } from 'msw'; export const handlers = [http.get('/api', () => new Response())];\n")
    write(
        repo / "tests" / "ui.spec.ts",
        """
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('ui', async ({ page }) => {
  await new AxeBuilder({ page }).analyze();
  await expect(page).toHaveScreenshot();
});
        """.strip()
        + "\n",
    )
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: ui
on: [push]
jobs:
  browser:
    runs-on: ubuntu-latest
    steps:
      - run: pnpm vitest --browser
      - run: pnpm playwright test
      - run: echo upload-artifact playwright-report
        """.strip()
        + "\n",
    )


def setup_frontend_jsdom(repo: Path) -> None:
    write(repo / "package.json", "{\n  \"name\": \"fixture\",\n  \"private\": true\n}\n")
    write(repo / "src" / "App.tsx", "export function App() { return <main>Hello</main>; }\n")
    write(repo / "vitest.config.ts", "export default { test: { environment: 'jsdom' } };\n")
    write(repo / "tests" / "ui.test.tsx", "vi.mock('./api');\n")


def setup_security_enforced(repo: Path) -> None:
    write(repo / "pyproject.toml", "[project]\nname='fixture'\nversion='0.1.0'\n")
    write(repo / "uv.lock", "version = 1\n")
    write(repo / "src" / "app.py", "print('hi')\n")
    write(repo / "package.json", "{\n  \"name\": \"fixture\",\n  \"private\": true\n}\n")
    write(repo / "pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
    write(repo / "web" / "index.ts", "export const x = 1;\n")
    write(repo / ".bandit", "[bandit]\nexclude = tests\n# baseline allowlist is owned and reviewed\n")
    write(repo / "audit-ci.json", "{\n  \"allowlist\": [\"GHSA-example\"]\n}\n")
    write(
        repo / ".github" / "workflows" / "ci.yml",
        """
name: security
on: [push]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - run: uv sync --frozen
      - run: uv export --frozen && echo dependency audit
      - run: bandit -r src
      - run: pnpm install --frozen-lockfile
      - run: pnpm audit
      - run: echo upload-artifact security-report
        """.strip()
        + "\n",
    )


def setup_security_blocked(repo: Path) -> None:
    write(
        repo / "pyproject.toml",
        """
[project]
name='fixture'
version='0.1.0'

[tool.uv]
index-url = "https://private.example.com/simple"
        """.strip()
        + "\n",
    )
    write(repo / "src" / "app.py", "print('blocked')\n")
    write(repo / ".npmrc", "registry=https://private.example.com/npm/\n")
    write(repo / "package.json", "{\n  \"name\": \"fixture\",\n  \"private\": true\n}\n")
    write(repo / "web" / "index.ts", "export const x = 1;\n")


CASES = [
    Case(
        "python-ruff-enforced",
        "python-lint-format-audit",
        "skills/python-lint-format-audit/scripts/run_python_lint_format_scan.py",
        "enforced",
        {"toolchain-normalization": "hardened", "enforcement-gates": "hardened"},
        setup_python_ruff_enforced,
    ),
    Case(
        "python-legacy-partial",
        "python-lint-format-audit",
        "skills/python-lint-format-audit/scripts/run_python_lint_format_scan.py",
        "partial",
        {"toolchain-normalization": "partial"},
        setup_python_legacy,
    ),
    Case(
        "python-not-applicable",
        "python-lint-format-audit",
        "skills/python-lint-format-audit/scripts/run_python_lint_format_scan.py",
        "not-applicable",
        {"toolchain-normalization": "not-applicable"},
        lambda repo: write(repo / "README.md", "# empty\n"),
    ),
    Case(
        "ts-biome-enforced",
        "ts-lint-format-audit",
        "skills/ts-lint-format-audit/scripts/run_ts_lint_format_scan.py",
        "enforced",
        {"toolchain-consolidation": "hardened", "typed-lint-layer": "hardened"},
        setup_ts_biome_enforced,
    ),
    Case(
        "ts-legacy-partial",
        "ts-lint-format-audit",
        "skills/ts-lint-format-audit/scripts/run_ts_lint_format_scan.py",
        "partial",
        {"toolchain-consolidation": "partial"},
        setup_ts_legacy,
    ),
    Case(
        "ts-workspace-partial",
        "ts-lint-format-audit",
        "skills/ts-lint-format-audit/scripts/run_ts_lint_format_scan.py",
        "partial",
        {"workspace-coverage": "partial"},
        setup_ts_workspace_partial,
    ),
    Case(
        "schema-enforced",
        "openapi-jsonschema-governance-audit",
        "skills/openapi-jsonschema-governance-audit/scripts/run_openapi_jsonschema_governance_scan.py",
        "enforced",
        {"artifact-health": "hardened", "breaking-change-detection": "enforced"},
        setup_schema_enforced,
    ),
    Case(
        "schema-generated-only",
        "openapi-jsonschema-governance-audit",
        "skills/openapi-jsonschema-governance-audit/scripts/run_openapi_jsonschema_governance_scan.py",
        "partial",
        {"source-of-truth-discipline": "missing"},
        setup_schema_generated_only,
    ),
    Case(
        "schema-not-applicable",
        "openapi-jsonschema-governance-audit",
        "skills/openapi-jsonschema-governance-audit/scripts/run_openapi_jsonschema_governance_scan.py",
        "not-applicable",
        {"artifact-health": "not-applicable"},
        lambda repo: write(repo / "README.md", "# empty\n"),
    ),
    Case(
        "frontend-browser-real",
        "ts-frontend-regression-audit",
        "skills/ts-frontend-regression-audit/scripts/run_ts_frontend_regression_scan.py",
        "enforced",
        {"browser-fidelity": "hardened", "visual-regression": "hardened"},
        setup_frontend_enforced,
    ),
    Case(
        "frontend-jsdom-only",
        "ts-frontend-regression-audit",
        "skills/ts-frontend-regression-audit/scripts/run_ts_frontend_regression_scan.py",
        "partial",
        {"browser-fidelity": "partial"},
        setup_frontend_jsdom,
    ),
    Case(
        "frontend-not-applicable",
        "ts-frontend-regression-audit",
        "skills/ts-frontend-regression-audit/scripts/run_ts_frontend_regression_scan.py",
        "not-applicable",
        {"browser-fidelity": "not-applicable"},
        lambda repo: write(repo / "README.md", "# empty\n"),
    ),
    Case(
        "security-full-chain",
        "python-ts-security-posture-audit",
        "skills/python-ts-security-posture-audit/scripts/run_python_ts_security_posture_scan.py",
        "enforced",
        {"lockfile-install-discipline": "enforced", "python-static-security": "enforced"},
        setup_security_enforced,
    ),
    Case(
        "security-blocked-private-registry",
        "python-ts-security-posture-audit",
        "skills/python-ts-security-posture-audit/scripts/run_python_ts_security_posture_scan.py",
        "scan-blocked",
        {"python-known-vulns": "blocked", "lockfile-install-discipline": "blocked"},
        setup_security_blocked,
    ),
    Case(
        "security-not-applicable",
        "python-ts-security-posture-audit",
        "skills/python-ts-security-posture-audit/scripts/run_python_ts_security_posture_scan.py",
        "not-applicable",
        {"python-known-vulns": "not-applicable"},
        lambda repo: write(repo / "README.md", "# empty\n"),
    ),
]


def main() -> int:
    for case in CASES:
        assert_case(case)
    print("New audit fixture regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
