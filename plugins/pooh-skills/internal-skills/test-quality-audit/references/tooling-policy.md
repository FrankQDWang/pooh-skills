# Tooling policy

The canonical baseline for this skill is the deterministic local scanner in `scripts/run_test_quality_scan.py`.

This skill intentionally stays narrow:

- detect whether CI runs a real test gate
- detect placeholder or tautological tests
- detect skip, xfail, or retry sprawl
- detect heavy internal-logic mocking patterns
- detect missing failure-path evidence

This skill intentionally does not:

- compute or enforce coverage ratios
- judge browser-real frontend regression quality
- judge Temporal replay or time-skipping verification quality
- auto-fix tests or CI pipelines

When the local repo surface is incomplete, prefer a visible `watch` trust gap over a fake-clean verdict.
