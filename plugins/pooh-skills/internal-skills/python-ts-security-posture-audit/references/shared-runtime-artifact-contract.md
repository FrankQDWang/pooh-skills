<!-- GENERATED FILE. Edit shared/runtime-artifact-contract.md and run `python3 scripts/sync_shared_skill_refs.py --write`. -->

# Shared Runtime Artifact Contract

Every deterministic wrapper must preserve the same runtime truth model:

- bootstrap first
- block honestly when required runtime dependencies are unavailable
- inject runtime status into the sidecar before finalizing
- validate the machine-readable summary before marking the run complete
- refuse to mark the run complete when `summary.json`, `report.md`, or `agent-brief.md` is missing

When a wrapper cannot produce an official verdict because a required live-doc or runtime dependency is missing, it must emit blocked artifacts. It may still emit local triage evidence, but that evidence must not be mislabeled as a successful audit result.
