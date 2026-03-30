# Tooling Policy

## Default stance

This audit judges TypeScript lint / format governance with a modern tool bias:

- `pnpm` is the package-manager surface
- `Biome` owns formatting, import sorting, and basic lint control
- typed ESLint owns semantic rules that require TypeScript project context

## Scoring bias

- `hardened`: Biome clearly owns the style layer, typed lint is real, and CI enforces both.
- `enforced`: the modern shape exists, but workspace coverage or suppression governance still needs work.
- `partial`: style ownership is split, or legacy `ESLint + Prettier` still defines the main path.
- `missing`: no credible modern TS lint / format control surface is visible.

## Evidence to trust

1. `biome.json` or `biome.jsonc`
2. `eslint.config.*` when used for typed lint
3. `tsconfig*.json`
4. workspace package scripts and `pnpm-workspace.yaml`
5. CI workflow entries
6. `eslint-disable`, `@ts-ignore`, and `@ts-expect-error`

## Out of scope

- browser regression quality
- API/schema governance
- auto-fix policy
- pure `tsc` type checking as a substitute for lint governance
