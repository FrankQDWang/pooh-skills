# Tooling Policy

## Default stance

This audit judges frontend regression quality with a modern evidence bias:

- `pnpm` is the package-manager assumption
- a real browser lane is required for strong confidence
- request-boundary mocking is preferred over internal monkey-patching
- accessibility and visual evidence should live close to the browser lane

## Scoring bias

- `hardened`: browser-real execution, boundary mocks, accessibility, visual evidence, and CI artifacts all exist.
- `enforced`: the modern chain exists, but one evidence lane still needs cleanup or stronger retention.
- `partial`: the repo is still mostly jsdom-only, mock-heavy, or missing one of the core evidence lanes.
- `missing`: no credible frontend regression surface is visible.

## Evidence to trust

1. browser-test config
2. boundary-mock setup
3. accessibility automation
4. screenshot or visual-baseline evidence
5. workflow artifact retention

## Out of scope

- lint or formatting policy
- schema governance
- Lighthouse performance work
- native mobile or Electron specifics
