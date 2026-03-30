# Tooling map

Use this only when you need to map findings to existing linters or compiler switches.

## Python
- Ruff / Bandit style mappings:
  - empty swallow → `S110` / `B110`
  - `except ...: continue` → `S112`
  - missing `from e` in `except` → `B904`
- Optional enrichers:
  - Ruff
  - Bandit
  - mypy / pyright
  - grep / ripgrep for fast pattern location

## TypeScript / JavaScript
- ESLint / typescript-eslint style mappings:
  - empty `catch {}` → `no-empty`
  - useless rethrow catch → `no-useless-catch`
  - cause preservation → `preserve-caught-error`
  - unsafe optional chaining → `no-unsafe-optional-chaining`
  - floating promises → `no-floating-promises`
  - non-null assertion → `no-non-null-assertion`
  - `?. ... !` combo → `no-non-null-asserted-optional-chain`
  - ts-comment suppression → `ban-ts-comment`
- TypeScript compiler switches worth checking:
  - `useUnknownInCatchVariables`
  - `exactOptionalPropertyTypes`
  - `noUncheckedIndexedAccess`

## Policy note
External tools are helpful, but this skill should still be able to produce a deterministic baseline from its bundled scripts.
Do not pretend an external tool ran when it did not.
