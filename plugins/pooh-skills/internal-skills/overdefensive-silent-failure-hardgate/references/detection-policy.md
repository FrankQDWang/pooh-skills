# Detection policy

## 1. Boundary first, then judgment

The same syntax can mean very different things depending on where it appears.

### Treat it more leniently when
- the code is at a trust boundary
- the fallback is explicit and documented
- the caller or user can observe degraded state
- logs / metrics / alerts exist for the fallback path

### Treat it more harshly when
- the code is internal application / domain / worker logic
- the path claims invariants are already satisfied
- the fallback is invisible to the caller
- the change mainly exists to make type checks or linters stop complaining

## 2. Evidence hierarchy

### High confidence
The syntax itself is already the problem:
- empty catch / `pass`
- `continue` inside a broad exception handler
- `.catch(() => {})`
- `as any`
- `# type: ignore`
- fire-and-forget `create_task(...)`

### Medium confidence
The syntax is suspicious and usually wrong:
- broad `except Exception` returning defaults
- `a?.b?.c` in core logic
- `foo || default`
- `dict.get(...)` for required-looking keys
- `cast(...)` without nearby narrowing

### Low confidence
The syntax may be harmless by itself:
- a single `Optional[...]`
- one `?? default`
- a single `hasattr(...)`

Never present low-confidence signals as hard architecture verdicts.

## 3. Severity bias

Use this default bias unless the code clearly deserves a different one.

- `critical` — bare swallow / skip / off-camera failure on production paths
- `high` — silent failure or escape hatch likely to hide real breakage
- `medium` — contract softening that increases latent failure risk
- `low` — weak signals or hygiene-level softening

## 4. Merge-gate bias

- `block-now` — new silent swallow or skip-on-error should not land
- `block-changed-files` — stop spreading escape hatches and off-camera async failure
- `warn-only` — useful but not hard enough for merge blocking
- `allow-with-explicit-contract` — acceptable only if the degrade path is made explicit
- `unverified` — interesting signal, not enough proof yet

## 5. False-positive handling

Do not hard-fail for any of these by default:
- tests intentionally exercising error paths
- compatibility code around third-party API weirdness when it is instrumented
- product flows that intentionally degrade and expose that state to the user
- cleanup code suppressing `FileNotFoundError` or equivalent idempotent absence
- generated code, unless the user explicitly wants generated code reviewed

## 6. Language-specific caution

### Python
Type hints are not runtime enforcement. A `cast(...)` or `Optional[...]` change can hide trouble without changing runtime behavior at all.

### TypeScript
Type assertions and non-null assertions disappear at compile time. Treat them as "trust me" markers, not safety features.

## 7. Reporting rule

If a repo uses a fallback pattern and also makes the degradation explicit, say that plainly.
This skill is trying to separate **observable degradation** from **silent failure**, not abolish resilience.
