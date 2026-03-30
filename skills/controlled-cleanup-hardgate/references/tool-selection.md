# Tool selection

Use the bundled scripts first. Then validate findings with the fixed Python / TypeScript / docs tool stack that this repository standardizes on.

## Python
- Ruff for fast validation
- basedpyright for Python type / contract checks
- Tach for Python boundary direction when structural leaks are part of the removal story

## JavaScript / TypeScript
- TypeScript compiler and typed ESLint for validation
- Knip for unused-file and export signals
- ast-grep for structural search and migration evidence

## Docs
- built-in link checks, Lychee, and Vale

## Rule of thumb
If a finding is strong enough to justify removal, the heuristic scanner should identify the target set and the locked validation stack should prove the repo is ready. This repository does not perform codemods or automatic rewrites.
