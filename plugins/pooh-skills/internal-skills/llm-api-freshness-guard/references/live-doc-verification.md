# Live-Doc Verification Contract

Use this only for the official `verified` flow.
Context7 is the required live-doc source for that flow.

## Truth rules

- `triage` means local evidence only
- `verified` means current docs were actually checked
- `blocked` means the verified flow could not complete truthfully because Context7 or another required verification dependency failed
- `not-applicable` means no relevant Python / TypeScript LLM surface was found

## Required `doc_verification` fields

Every doc entry must record:

- `surface_id`
- `surface_family`
- `provider`
- `wrapper`
- `library`
- `library_id`
- `language`
- `queries`
- `status`
- `checked_at`
- `source_ref`
- `notes`

## Severity guardrails

- `high` / `critical` requires verified docs and a concrete runtime mismatch
- `family-resolved` findings may not exceed `medium`
- `triage` findings may not exceed `low`
