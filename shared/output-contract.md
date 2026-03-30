# Shared Output Contract

Every audit skill in this repository must produce the same three deliverables:

- one human-readable report for the repo owner
- one short agent brief for a strong coding agent
- one machine-readable summary JSON for orchestration and validation

These outputs must be truthful even when certainty is weak.

- If the audit is not applicable, emit `not-applicable` artifacts instead of forcing a verdict.
- If required runtime prerequisites are missing, emit blocked artifacts instead of pretending the scan succeeded.
- If evidence is incomplete, mark uncertainty explicitly with repository-defined values such as `unverified`, `scan-blocked`, or `not-applicable`.

Do not silently downgrade blocked or unverified states into “looks fine”.
