# Tooling Policy

## Default stance

This audit judges OpenAPI / JSON Schema governance with a modern evidence bias:

- `uv` and `pnpm` are the only package-manager assumptions
- source specs must be distinct from generated bundles and clients
- `Redocly`, `Spectral`, `ajv-cli`, and `check-jsonschema` are preferred governance probes
- breaking-change detection must be reproducible and CI-visible

## Scoring bias

- `hardened`: source-of-truth is explicit, lint/bundle/diff all exist, and CI preserves the evidence.
- `enforced`: the modern chain mostly exists, but one part still needs cleanup or clearer ownership.
- `partial`: schema files exist but the chain is local-only, fragmented, or ambiguous.
- `missing`: no credible schema governance surface is visible.

## Evidence to trust

1. source spec directories
2. ruleset config files
3. lint and bundle scripts
4. breaking-change diff commands in CI
5. publication or artifact-retention steps in workflows

## Out of scope

- runtime schema enforcement
- GraphQL, AsyncAPI, protobuf
- code generation fixes
- auto-remediation
