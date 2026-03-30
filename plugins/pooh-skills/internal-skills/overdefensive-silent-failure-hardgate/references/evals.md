# Manual eval cases

## Should trigger

1. Python: `except Exception: pass`
2. Python: `except Exception: continue` inside a batch loop
3. Python: `raise RuntimeError("bad")` in `except` without `from e`
4. Python: bare `asyncio.create_task(send_email())`
5. TypeScript: `catch {}`
6. TypeScript: `promise.catch(() => {})`
7. TypeScript: `user?.profile?.id!`
8. TypeScript: `const data = raw as any`
9. TypeScript: `// @ts-ignore`
10. JavaScript: `promise.catch;`

## Should not trigger

1. API boundary validation that converts malformed input into an explicit 4xx response
2. A degraded UI state that is clearly labeled `queued`, `partial`, or `failed`
3. Cleanup code intentionally suppressing `FileNotFoundError` in a documented idempotent path
4. Type assertions immediately followed by runtime validation and narrowing
5. Tests intentionally asserting swallow / fallback behavior for legacy compatibility code

## False Positive / Regression Cases

1. A Python string literal contains `# type: ignore` as an example or rule pattern.
Expected: do not emit a high-confidence `type-escape-hatch` finding unless the phrase appears in a real comment token.
2. A TS source file contains `eslint-disable` only inside a template string or rule-definition string.
Expected: do not emit a code finding from the string literal alone.
3. A repo includes markdown or JSON examples of empty catch blocks outside executable code.
Expected: ignore non-executable examples.
