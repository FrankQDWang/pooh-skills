# Controlled Cleanup Report

## 1. Executive summary
- Scope:
- Verdict: `not ready` | `partially ready` | `ready for controlled deletion`
- Main reason:

## 2. Delete-now candidates
| target | type | why it looks safe | remaining checks |
|---|---|---|---|
|  |  |  |  |

## 3. Blockers
| blocker | severity | impact | what must be true before deletion |
|---|---|---|---|
|  |  |  |  |

## 4. Hidden-reference risks
- Dynamic entrypoints:
- Public SDK/API exposure:
- Config or route string coupling:
- Generated code or docs risk:

## 5. Evidence chain
- Static / lint:
- Types / compile:
- Tests / coverage:
- Docs / link checks:
- Ownership / approvals:
- Rollback or canary:

## 6. Ordered cleanup sequence
1.
2.
3.
4.

## 7. What must not happen
- Do not keep compatibility shims by default.
- Do not delete before references and docs are updated.
- Do not treat heuristic findings as proof when runtime indirection exists.

## 8. Machine-readable artifacts
- summary:
- linkcheck:
- forbidden refs:
