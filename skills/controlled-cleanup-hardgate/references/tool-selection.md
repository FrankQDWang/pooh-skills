# Tool selection

Use the bundled scripts first. Reach for stronger language-aware tools only when the repo needs them.

## Python
- Ruff / mypy / pyright for fast validation
- Vulture for unused-code hints
- LibCST for safe codemods

## JavaScript / TypeScript
- TypeScript compiler and ESLint for validation
- Knip for unused-file and export signals
- jscodeshift, ts-morph, or ast-grep for codemods

## Java
- OpenRewrite for large-scale source transforms
- Error Prone / SpotBugs for validation

## Go
- golangci-lint / Staticcheck
- `go test -coverprofile` for coverage-backed confidence

## Docs
- markdownlint, Vale, link checkers, and docs-site broken-link checks

## Rule of thumb
If deletion depends on syntax-aware rewrites, type graphs, or framework metadata, the heuristic scanner should identify the target set and the language-aware tool should perform the change.
