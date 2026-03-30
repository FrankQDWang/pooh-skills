# Error Governance Standard

This file distills the bundled target policy into an audit-ready reference.
Use it as the normative baseline for `error-governance-hardgate`.

## 1. Universal error object baseline

The target model is a **Problem Details style** error object with one shared JSON shape across HTTP and async/message boundaries.

### Core baseline

Use the Problem Details mental model:

- `type`
- `title`
- `status`
- `detail`
- `instance`

### Repo-required top-level extension fields

The bundled policy requires these top-level fields in every public error object:

- `code` — stable business error key
- `trace_id` — trace identifier
- `timestamp` — RFC 3339 timestamp
- `service` — producing service identifier

### Repo-recommended top-level extension fields

- `span_id`
- `retryable`
- `retry_after_ms`
- `errors[]`

`errors[]` is the structured sub-error array for validation or batch problems.
Prefer field-level structure over prose blobs.

## 2. Field constraints

Treat these as the target shapes when evidence exists:

- `type`: URI reference
- `instance`: URI reference
- `timestamp`: RFC 3339 `date-time`
- `service`: kebab-case service identifier
- `trace_id`: 32 lowercase hex, not all zero
- `span_id`: 16 lowercase hex, not all zero

### `code` pattern

Target regex:

```regex
^[A-Z][A-Z0-9]{1,24}(_[A-Z0-9]{1,24}){1,6}$
```

Interpretation:

- uppercase segmented business key
- at least 2 segments
- usually 3 to 5 segments is the sweet spot
- semantic grouping beats numeric trivia

Examples:

- `AUTH_TOKEN_EXPIRED`
- `ORDER_NOT_FOUND`
- `PAYMENT_METHOD_NOT_SUPPORTED`
- `INVENTORY_RESERVE_CONFLICT`

## 3. `type` vs `code`

Do not blur these two fields.

- `type` = problem type URI, the semantic problem identifier for documentation and contract meaning
- `code` = stable business branching key for programs, generated types, and SSOT dictionaries

Hard rule:

- one `code` must map to one `type`
- do not recycle old `type` values for new meanings
- do not branch on `title` or `detail`

## 4. HTTP mapping discipline

For HTTP surfaces, the target policy expects:

- media type: `application/problem+json`
- `status` aligned with the actual HTTP response code when present
- coarse transport classification via status code, fine business classification via `code`

Typical target mappings:

- auth missing or invalid → `401`
- authenticated but forbidden → `403`
- not found or not disclosed → `404`
- bad syntax or malformed request → `400`
- semantic validation failure → `422`
- state conflict / version conflict → `409`
- rate limit / quota → `429`
- unknown server error → `500`
- upstream bad gateway → `502`
- overload / maintenance → `503`
- upstream timeout → `504`

These are mapping guidelines, not permission to collapse all business meaning into HTTP status alone.
`code` stays the business branch key.

## 5. Async / event mapping discipline

For AsyncAPI or message-driven surfaces, the target policy expects:

- the structured error object lives in **message payload**
- correlation / trace / routing metadata lives in **headers** or equivalent transport metadata
- async error messages are clearly identifiable through one of:
  - explicit error message contract
  - `contentType: application/problem+json`
  - explicit success / error union strategy

In async flows, `status` is a classification field only.
It is **not** transport truth.

## 6. Validation error shape

Validation and batch errors should expose structure, not just narrative text.
Target shape inside `errors[]`:

- `detail` — required human-readable explanation
- `pointer` — preferred field locator
- `target` — optional machine target

The public contract should make field-level repair possible without scraping prose.

## 7. Global handling and leakage boundary

The target repo behavior is:

- internal failure detail is logged internally
- outward-facing responses stay structured and non-sensitive
- stack traces, SQL strings, secret values, and internal topology do not leak publicly
- `trace_id`, `timestamp`, and `service` are present consistently enough for cross-system debugging

## 8. SSOT catalog requirements

The target governance model expects one versioned error dictionary or equivalent SSOT.
Each public error entry should carry at least:

- `code`
- `type`
- `title`
- `http_status`
- `domain`
- `service_owner`
- `retryable`
- `visibility`
- `lifecycle`

Recommended extras:

- `description`
- `docs`
- `since`
- `examples`
- `replaced_by` when deprecated

## 9. Code generation expectations

The target policy expects **one-way generation** from the catalog into language-specific artifacts.
Typical generated outputs:

- Python `Enum` / `Literal` / `TypedDict` or equivalent
- TypeScript string unions, `as const` maps, and error interfaces

Anti-pattern:

- hand-maintained copies of the same public error code list in multiple languages

## 10. CI and merge-gate expectations

A strong repo should be able to prove at least some of these:

- catalog uniqueness for `code` and `type`
- pattern validity for `code`
- domain-prefix consistency
- schema drift checks
- generated-artifact freshness checks
- contract tests that stop runtime / OpenAPI / AsyncAPI divergence

If the repo claims strong contracts but cannot fail a PR on silent error-code drift, classify that as governance weakness.
