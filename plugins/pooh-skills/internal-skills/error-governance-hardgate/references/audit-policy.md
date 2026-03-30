# Audit Policy

This file explains how to apply the bundled standard to real repositories without turning the audit into cargo cult compliance theater.

## Evidence hierarchy

Prefer evidence in this order:

1. runtime handler / middleware / serializer code
2. shared schemas and catalogs
3. OpenAPI / AsyncAPI contracts
4. generated Python / TypeScript artifacts
5. tests and snapshots
6. docs and ADRs
7. comments and TODOs

If lower-tier evidence contradicts higher-tier evidence, trust the higher tier and report drift.

## What counts as a real contract

Strong evidence:

- one shared schema reused by multiple endpoints / messages
- generated types that match the catalog
- middleware or boundary translators that normalize exceptions into one public shape
- tests that pin the public contract
- CI checks that fail on drift

Weak evidence:

- wiki pages no code follows
- comments that describe a schema but no shared artifact exists
- copy-pasted example payloads with no validation
- enums maintained manually in Python and TypeScript side by side

## Confidence rules

Use `high` confidence when multiple layers agree.
Use `medium` when the shape is clear but not comprehensively enforced.
Use `low` when inferring from scattered response examples or partial repo snapshots.

Examples:

- shared JSON Schema + middleware + tests all match → `high`
- OpenAPI matches, but handlers return custom dicts in some files → `medium`
- only README examples exist → `low`

## Severity rules

### Critical

Use `critical` for:

- public branching depends on `title`, `detail`, or free-text messages
- outward responses leak stack traces, SQL, secrets, or internal implementation detail
- incompatible public error shapes coexist on the same product surface
- public `code` values are unstable, duplicated, or semantically reused

### High

Use `high` for:

- required fields missing from most public errors
- no credible SSOT exists for public error codes
- OpenAPI / AsyncAPI / runtime handlers contradict each other
- generated artifacts are hand-edited or drifted
- no boundary layer exists and exceptions leak framework-specific noise

### Medium

Use `medium` for:

- retry semantics are partial or ambiguous
- validation details are present but weakly structured
- ownership / lifecycle metadata is incomplete
- only some protocols carry traceability fields

### Low

Use `low` for:

- naming cleanup
- documentation clarity
- optional metadata enrichment

## Anti-patterns to call out sharply

Name these directly when you see them:

- **message-as-API** — clients branch on prose instead of structured keys
- **copy-paste contract** — each handler invents its own error JSON shape
- **split-brain catalog** — Python, TypeScript, and docs each carry separate public code lists
- **observability cosplay** — raw internals leak outward because nobody separated public response from internal logging
- **protocol amnesia** — HTTP and async flows model the same failure in incompatible ways
- **stringly typed governance** — numeric or vague codes wrapped in human text and called “typed”

## Repair patterns to prefer

Prefer these change shapes over heroic rewrites:

- extract one shared UniversalProblem schema
- create one versioned error catalog
- generate Python / TypeScript types from the catalog
- add one boundary translator that strips internal details and injects shared metadata
- add contract tests for representative HTTP and async failures
- add CI checks for catalog uniqueness and generated-file freshness
- migrate clients from message parsing to `code`-based branching

## Search surfaces and heuristics

Look in places like:

- `openapi/`, `contracts/`, `specs/`, `docs/api/`
- `asyncapi/`, `events/`, `schemas/`, `messages/`
- `errors.*`, `problem.*`, `exceptions.*`, `middleware.*`, `handlers.*`
- generated client packages, SDK folders, shared DTO libraries
- tests named `test_errors`, `test_problem_details`, `contract`, `snapshot`, `schema`
- catalog files like `error-codes.yaml`, `errors.json`, `problem-types.yaml`, `error_catalog.*`

Useful heuristics:

- if you see `return {"error": ...}` in multiple shapes, suspect `universal-problem-gap`
- if you see `if "not found" in err.detail`, suspect `text-branching`
- if you see plain strings in async error payloads, suspect `async-contract-gap`
- if code lists exist in both `python/` and `typescript/` with no generator, suspect `codegen-drift`
- if docs mention `trace_id` but runtime code only injects it on one path, suspect `traceability-gap`

## Output discipline

Your report should answer three things fast:

1. Is the public error contract actually one contract?
2. Can clients branch safely and durably?
3. What is the smallest structural hardening move with the biggest leverage?

Do not drown the reader in every exception class you found.
Summarize the governance disease, not just the symptoms.
