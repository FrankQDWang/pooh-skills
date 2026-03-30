# Context7 Runtime Setup

This skill now has two runtime layers:

- local wrapper triage
- agent-first verified audit

## Wrapper

`scripts/run_all.sh` no longer depends on Context7.
It only produces local triage artifacts.

## Verified flow

The verified flow still depends on Context7 because official freshness claims require live docs.

If Context7 is unavailable during a requested verified audit:

- do not fake a verified result
- emit or preserve `blocked`
- keep unresolved surfaces unresolved
