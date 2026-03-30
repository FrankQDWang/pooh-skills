# Evaluation cases

Use these as the minimum manual regression set when changing the skill.

## Should trigger

1. "这个仓库已经迁到 v2 了，帮我找出还能删掉的 deprecated API、compat 层和旧文档。"
2. "Audit this repo for legacy aliases, stale docs, and removal targets that should already have been deleted."
3. "做一次可控清理审计，不要保兼容壳，告诉我哪些旧入口可以删，哪些还不能删。"
4. "We finished the migration. I need proof about what old routes, wrappers, and flags are still hanging around."
5. "Look for removal readiness before we delete the legacy path."

## Should not trigger

1. "Scan this monorepo for dependency cycles and architecture boundary leaks."  
Expected: prefer `dependency-audit`, not this skill.
2. "Audit compile-time and runtime API contracts; I want hard gates around signatures and error schemas."  
Expected: prefer `signature-contract-hardgate`, not this skill.
3. "Review our Temporal workflows for determinism and pydantic-ai durable execution risks."  
Expected: prefer `pydantic-ai-temporal-hardgate`, not this skill.

## False Positive / Regression Cases

1. "Read these docs and integration notes. They mention legacy compatibility paths and plugin routing, but do not ask for deletion guidance."  
Expected: do not emit high-confidence cleanup findings from prose-only mentions.
2. "This Markdown file says the old flow is legacy but gives no machine-readable deprecation marker."  
Expected: at most a low-confidence cleanup-opportunity after human confirmation, not `deprecated-surface` or `dynamic-entrypoint-risk`.
3. "This code path has `@deprecated`, `remove-after: 2026-06-30`, and `importlib.import_module(...)`."  
Expected: allow `deprecated-surface`, `marker-gap` if metadata is incomplete, and `dynamic-entrypoint-risk`.
