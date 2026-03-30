# Pattern catalog

This reference exists so the core `SKILL.md` stays lean. Read it when you need concrete examples of the failure modes.

## Core distinction

The skill is not anti-recovery. It is anti-**quiet corruption**.

Good recovery has all of these:
- the fallback is intentional
- the fallback is visible in logs / metrics / state
- the caller or user can tell a degraded path happened
- the fallback is documented as part of the contract

Bad recovery looks like:
- "catch and keep going"
- "return None / {} / [] so tests stay green"
- "smear Optional / undefined everywhere"
- "use type assertions / ignore comments to remove red lines"
- "launch async work and never look back"

## Python patterns

### Strong triggers
- `except:`
- `except Exception: pass`
- `except Exception: continue`
- `except Exception: return None`
- `with contextlib.suppress(Exception):`
- `raise RuntimeError(...)` inside `except` without `from e`
- bare `asyncio.create_task(...)` or `asyncio.ensure_future(...)`
- `# type: ignore`, `# pyright: ignore`

### Signals
- `Optional[T]` or `T | None` spreading from boundary code into core logic
- `dict.get("user_id")` where the key looks required
- `getattr(obj, "x", None)` or `hasattr(...)` used to dodge a model contract
- `value = value or default`
- `typing.cast(...)` used to silence a type complaint without narrowing

### Boundary examples that are usually okay
- validating untrusted HTTP / queue / file input
- translating a missing optional field into a 4xx or domain error explicitly
- `contextlib.suppress(FileNotFoundError)` during idempotent cleanup when the cleanup is truly optional and documented

## TypeScript / JavaScript patterns

### Strong triggers
- `catch {}`
- `.catch(() => {})`
- `.catch(() => undefined)`
- `.catch;`
- `as any`
- `as unknown as T`
- `@ts-ignore`
- `eslint-disable`
- `user?.profile?.id!`

### Signals
- `a?.b?.c` on paths that should be invariant
- `foo ?? "default"` when the field is contractually required
- `foo || "default"` where `0`, `""`, or `false` are legitimate values
- widespread `prop?: T` / `T | undefined` in core paths
- useless try/catch layers that only restate or rethrow

### Boundary examples that are usually okay
- explicit runtime validation of JSON from external systems
- a degraded UI state that is clearly labeled `queued`, `partial`, or `failed`
- type assertions at foreign-library edges when followed immediately by runtime narrowing or schema validation

## Cross-language symptoms

These usually point to the same root cause even when the syntax differs:
- **Optionals leak** → required facts become maybe-facts
- **Default value abuse** → contract break becomes "just use a fallback"
- **Truthiness fallback** → legitimate falsy value gets overwritten
- **Exception swallow** → error disappears as a control-flow detail
- **Async off-camera failure** → work fails later and elsewhere
- **Cause chain loss** → the root cause gets flattened
- **Type / lint escape hatch** → feedback is silenced instead of resolved

## Merge root causes whenever possible

If one code path does all of these at once:
- converts a required value into optional
- catches the resulting failure
- returns a default
- hides the type error with `cast` or `as any`

do not report it as four unrelated "style issues". Report it as one contract-softening root cause with multiple symptoms.
