# Controlled Cleanup Agent Brief

## Objective
Describe cleanup readiness, blockers, and handoff guidance. Do not delete code or perform automatic edits from this brief.

## Targets
- Highest-confidence cleanup candidates:
- Migrate first:
- Hold for human confirmation:

## Required checks
```bash
bash scripts/run_all.sh /path/to/repo
```

Use strict metadata enforcement only when the cleanup gate is specifically about missing replacement or removal-target fields:

```bash
bash scripts/run_all.sh --strict-removal-targets /path/to/repo
```

## Guardrails
- Update docs, examples, and navigation together with any manual cleanup work.
- Treat reflection, runtime imports, plugin systems, and string-based dispatch as high-risk.
- Return a cleanup candidate list, migration list, verification commands, risks, and rollback notes.

## Expected output
1. concise summary
2. exact files/symbols that look ready for manual cleanup review
3. exact files/symbols still blocking cleanup
4. verification commands and results
5. residual risks
