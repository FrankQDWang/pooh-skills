# Live-Doc Verification

This skill treats **Context7-backed official documentation verification** as a hard dependency for an official verdict.

Rules:

- identify the real provider or compatibility layer first
- extract version hints from manifests, lockfiles, or package metadata
- resolve official docs with Context7 before calling anything stale, deprecated, removed, or current
- when wrappers add semantics, verify wrapper docs and underlying provider docs separately

Blocked behavior:

- if Context7 is unavailable, do not emit a successful freshness verdict
- emit blocked artifacts or a blocked summary mode instead
- local signal collection may still run as triage evidence, but it must not be mislabeled as a verified result

Accepted doc evidence for deterministic wrappers:

- a JSON artifact passed via `--doc-evidence-json`
- each entry records `provider`, `library`, `library_id`, `language`, `version_hint`, `queries`, `status`, `checked_at`, `source_ref`, and `notes`
- at least one entry must have `status=verified` for the wrapper to emit a non-blocked official result
