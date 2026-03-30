# Remediation playbook

Use these change shapes instead of patching symptoms with more fallback code.

## exception-swallow
**Bad shape**
- `except Exception: pass`
- `catch {}`

**Target shape**
- catch only the expected exception
- log / metric / alert if degradation is truly intended
- otherwise let the error surface

## skip-on-error
**Bad shape**
- `except Exception: continue`
- batch loop silently dropping rows

**Target shape**
- collect failures explicitly
- emit counts and identifiers
- stop the batch when silent data loss is unacceptable

## cause-chain-loss
**Bad shape**
- `raise RuntimeError("x")` inside `except` without `from e`
- `throw new Error("x")` in `catch` without preserving `cause`

**Target shape**
- preserve the original cause
- translate only when the new error adds real domain meaning

## async-exception-leak
**Bad shape**
- bare `asyncio.create_task(...)`
- promise created without `await`, `return`, or real error handling

**Target shape**
- await it
- gather / join it
- or register an explicit done callback / rejection handler that emits observability data

## optionality-leak
**Bad shape**
- required facts become `Optional` / `undefined` everywhere

**Target shape**
- narrow at the boundary
- keep core paths strict
- let absence stay localized and explicit

## silent-default / truthiness-fallback
**Bad shape**
- `dict.get("required_key")`
- `value = value or default`
- `foo || "default"`

**Target shape**
- enforce required fields explicitly
- distinguish `None` / `undefined` from valid falsy values
- use `??` only when nullish fallback is the real contract

## type-escape-hatch / lint-escape-hatch
**Bad shape**
- `as any`
- `# type: ignore`
- `@ts-ignore`
- `eslint-disable`

**Target shape**
- narrow with real type guards
- add runtime validation at boundaries
- move broken assumptions into explicit compatibility adapters if they must exist

## delete-theater
**Bad shape**
- useless try/catch that only decorates the code with fake seriousness

**Target shape**
- delete the noise
- keep only handling that changes behavior, observability, or contract semantics

## Explicit degradation checklist

Before keeping any fallback, require all of these:
1. Does the caller or user know degradation happened?
2. Is there a log / metric / alert?
3. Is the degraded state named in the contract or docs?
4. Can downstream code distinguish degraded from success?
5. Would a reviewer still call this "handling" if the fallback stopped hiding the failure?
