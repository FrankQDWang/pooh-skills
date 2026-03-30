# Tooling policy

## Canonical baseline

The canonical baseline for this skill is the deterministic Python scanner in `scripts/run_module_shape_scan.py`.

Reason: this repository's skill contract prefers stable, portable detection-and-report behavior over a fragile pile of optional external CLIs.

## Optional augmentation tools

If you later want stronger evidence, these are the best add-ons for this skill family:

- `lizard` — cross-language function length / complexity evidence
- `scc` — fast code-size baselines
- `jscpd` — duplicate block detection
- `Tach` — Python-side boundary evidence when module shape and boundary shape interact
- `dependency-cruiser` — TypeScript-side dependency graph evidence

## Important repository-specific note

`pooh-skills` explicitly says Python boundary tooling should standardize on `Tach`, not `import-linter`.

This skill therefore treats boundary tools as **secondary evidence**, not as the core module-shape detector.

## Why the core workflow stays tool-light

The repository authoring contract warns against hardcoding fast-changing ecosystem details into the skill's core workflow. Tool-specific flags, version quirks, and install steps therefore belong in references or runtime manifests rather than in the core decision logic.

## Practical recommendation

Use the built-in baseline first. Add external tools only when you want stronger CI hard gates or richer evidence in especially large repositories.
