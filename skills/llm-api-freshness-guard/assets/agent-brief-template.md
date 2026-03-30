# LLM API Freshness Agent Brief

## Execution mode
- `report-only`

## Scope summary
- Providers:
- Wrappers / gateways:
- Verification mode:
- Trust rule: `verified` is reserved for runs with real current-doc checks; `blocked` means fix runtime prerequisites first; `local-scan-only` must not be treated as a final migration verdict.
- Files / directories in scope:
- Version hints:
- Current docs checked:

## Findings queue

### [finding-id] [title]
- provider:
- kind:
- severity:
- confidence:
- status:
- scope:
- stale_usage:
- current_expectation:
- evidence_summary:
- decision:
- recommended_change_shape:
- validation_checks:
- docs_verified:
- autofix_allowed:
- notes:

### [finding-id] [title]
- provider:
- kind:
- severity:
- confidence:
- status:
- scope:
- stale_usage:
- current_expectation:
- evidence_summary:
- decision:
- recommended_change_shape:
- validation_checks:
- docs_verified:
- autofix_allowed:
- notes:

## Output rules for the coding agent
- Keep patches small and reversible first.
- Do not rewrite unrelated provider code.
- Do not change runtime semantics unless the finding requires it.
- Preserve behavior when replacing deprecated syntax with current syntax.
- If a wrapper and provider disagree, fix the code only after the source of truth is clear.
- Treat this brief as handoff guidance, not as permission for automatic fixes.
