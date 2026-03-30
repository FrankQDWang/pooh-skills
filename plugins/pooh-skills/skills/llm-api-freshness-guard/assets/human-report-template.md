# LLM API Freshness Audit

## Executive summary
- audit_mode:
- target_scope:
- dependency_status:
- diagnosis:
- verified_doc_entries:
- highest-risk surface:

## Resolved surfaces
| Surface | Resolution | Confidence | Language | Primary SDK | Version hints |
|---|---|---|---|---|---|
| | | | | | |

## Verified findings

### [finding-id] [title]
- kind:
- severity:
- verification_status:
- resolution_level:
- provider:
- wrapper:
- Current behavior:
- Current expectation:
- Recommended change shape:
- Evidence:

## Ambiguous / unverified surfaces
- Which surfaces remain only family-resolved, wrapper-resolved, or ambiguous
- What evidence exists
- Why the run still cannot safely claim one concrete provider when that remains true

## Recommended actions

### now
- use Context7 on legacy-looking executable code paths
- resolve hidden wrapper / gateway provider ownership

### next
- verify family-level surfaces without pretending they are concrete vendors
- compare wrapper semantics against provider pass-through behavior

### later
- centralize adapter ownership and make provider selection more explicit

## Scan limitations
- triage output is not an official freshness verdict
- family-level confidence is weaker than provider-resolved confidence
- docs / comments / examples are only weak evidence
