# Manual eval cases

## Should trigger

1. Audit a repository for global error handling, Problem Details usage, and business error-code governance.
2. Check whether OpenAPI and AsyncAPI error shapes are aligned.
3. Find places where clients branch on `detail` or message text instead of `code`.
4. Review whether Python and TypeScript error-code artifacts come from one SSOT catalog.
5. Check whether outward-facing errors leak stack traces or internal implementation details.

## Should not trigger

1. Fix one `KeyError` or one thrown exception with no governance or public-contract scope.
2. Write a new endpoint or feature unrelated to public error contracts.
3. Explain RFC 9457 in general with no repository, schema, or code surface to inspect.
4. Run a generic architecture or dependency audit.

## False Positive / Regression Cases

1. A repo has one local exception helper but no public API or event-contract surface.
Expected: `not-applicable` or low-confidence output, not a governance hard-fail.
2. OpenAPI examples mention `detail`, but runtime code already uses structured `code`.
Expected: report docs/runtime drift, not a fabricated `text-branching` finding.
3. A string literal contains phrases like `"not found"` inside test fixtures or example payloads.
Expected: do not report production `text-branching` without real control-flow evidence.
