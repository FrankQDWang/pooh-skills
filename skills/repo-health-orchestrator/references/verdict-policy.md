# Verdict normalization policy

Child skills use different verdict vocabularies.
The orchestrator should not erase them.
It should consume only the current-run machine contract and preserve child-specific wording as explanatory evidence.

Some child skills expose a trust mode instead of a health verdict.
For example, `llm-api-freshness-guard` may surface `verified` or `triage` in `child_verdict`.
Preserve that signal for explanation, but machine rollup must come from `rollup_bucket` plus coverage status.
Dependency bootstrap failure still outranks child wording: if `dependency_status=blocked`, that domain is blocked even if its child verdict is otherwise mild.

## Coverage before verdict

First decide whether each domain is `present`, `blocked`, `not-applicable`, `invalid`, or `missing`.

- `invalid` and `missing` are coverage failures, not child verdicts
- `blocked` is current-run coverage with a formal dependency/runtime failure, not missing coverage
- `not-applicable` is a legitimate child outcome
- a domain can be present and still blocked

Do not soften this distinction in the final report.

## Blocked domain

Treat a child domain as blocked when any of the following are true:

- `dependency_status=blocked`
- coverage status is `blocked`
- `rollup_bucket=blocked`
- `rollup_bucket=red`

## Watch domain

Treat a child domain as watch when:

- no blocked condition exists
- `rollup_bucket=yellow`, or
- the child summary is only `triage` and still needs live-doc verification, or
- coverage is weak

## Healthy domain

Treat a child domain as healthy when:

- the summary exists for the current run
- coverage is good enough to trust the scan
- `rollup_bucket=green`

## Partial coverage

If too many expected domains are missing or invalid, the overall rollup must stay `partial-coverage` even if present domains look healthy.

Do not infer red/yellow/green from free-form child verdict strings.
