# Controlled Cleanup Agent Brief

## Objective
Finish cleanup by deleting deprecated or legacy surfaces when evidence is strong enough. Do not preserve wrappers, aliases, or compatibility shims unless explicitly requested.

## Targets
- Remove:
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

## Extra policy checks
```bash
python3 scripts/check_forbidden_refs.py --repo . --pattern-file .repo-harness/cleanup-targets.json --out .repo-harness/controlled-cleanup-forbidden.json
```

## Guardrails
- Old code/docs should be physically removed when replacement and migration are complete.
- Update docs, examples, and navigation together with code.
- Treat reflection, runtime imports, plugin systems, and string-based dispatch as high-risk.
- Return a deletion list, migration list, verification commands, risks, and rollback notes.

## Expected output
1. concise summary
2. exact files/symbols to delete
3. exact files/symbols still blocking deletion
4. verification commands and results
5. residual risks
