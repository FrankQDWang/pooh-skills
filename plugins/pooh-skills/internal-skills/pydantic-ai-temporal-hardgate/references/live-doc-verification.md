# Live-Doc Verification

This skill treats **Context7-backed official documentation verification** as a hard dependency for any confident durable-path verdict.

Rules:

- inspect the repo first for version hints and real runtime surfaces
- verify the current Temporal Python and pydantic-ai durable execution guidance with Context7
- prefer official docs over repo folklore, examples, or cached memory
- treat local static scans as evidence, not as the final authority on the current supported path

Blocked behavior:

- if Context7 is unavailable, emit blocked artifacts or `scan-blocked` style output
- do not claim the repo follows the official durable path without live-doc evidence
- local findings may still be listed, but the run remains blocked until doc verification exists

Accepted doc evidence for deterministic wrappers:

- a JSON artifact passed via `--doc-evidence-json`
- each entry records `subject`, `library`, `library_id`, `version_hint`, `queries`, `status`, `checked_at`, `source_ref`, and `notes`
- at least one entry for `temporal-python` and one entry for `pydantic-ai` should be `verified` before the wrapper emits a non-blocked official result
