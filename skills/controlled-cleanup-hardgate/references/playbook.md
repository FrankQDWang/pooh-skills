# Cleanup playbook

## Flow
1. Define the replacement path.
2. Add or normalize deprecation markers.
3. Migrate call sites mechanically where possible.
4. Block new references to the old surface.
5. Collect the full evidence set before deciding whether to block or delete.
6. Delete the old code or docs physically.
7. Run validation, docs checks, and rollout checks.
8. Use canary or staged rollout for risky production paths.

## Default judgment model
- Delete now: replacement exists, references are gone, docs are aligned, and no dynamic-risk blocker remains.
- Delete after migration: replacement exists but references/docs/flags still remain.
- Hold: runtime indirection, external consumers, or missing evidence make deletion unsafe.

## Required evidence before calling something "done"
- Old symbol/path/file is no longer referenced in code or docs.
- Old artifact is physically removed.
- Validation chain is explicit and runnable.
- Rollback or staged rollout is thought through for risky changes.

## Strong recommendation
Treat "keeping a deprecated wrapper" as a failure to finish cleanup unless the user explicitly wants a compatibility window.
