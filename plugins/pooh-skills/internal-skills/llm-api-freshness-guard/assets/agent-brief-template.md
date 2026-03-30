# LLM API Freshness Agent Brief

## Run state
- audit_mode:
- target_scope:
- dependency_status:
- diagnosis:

## Ordered actions

### now
- resolve the real runtime surface before claiming provider-specific drift

### next
- verify wrapper-owned semantics and provider-owned semantics separately

### later
- reduce ambiguity by centralizing adapter ownership and base-url policy

## Surface queue
- surface_id:
- label:
- resolution_level:
- confidence:
- primary_sdk:

## Findings

### [finding-id] [title]
- surface_id:
- kind:
- severity:
- resolution_level:
- surface_family:
- provider:
- wrapper:
- current_behavior:
- current_expectation:
- verification_status:
- recommended_change_shape:
- evidence:

## Output rules for the coding agent
- Do not silently guess the provider when evidence only supports a family-level conclusion.
- Do not report high-severity provider-specific drift without verified docs.
- Keep wrapper and provider semantics separate when both exist.
- Treat triage findings as prompts for Context7 verification, not as migration permission.
