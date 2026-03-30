# Manual eval cases

## Should trigger

1. `domain/` imports `sqlalchemy`, `fastapi`, `requests`, or equivalent infra details.
2. `contexts/billing/domain/...` imports `contexts/orders/domain/...`.
3. An abstract base class contains only `raise NotImplementedError` methods.
4. A `Service` class only forwards calls to a collaborator.

## Should not trigger

1. A lightweight app with no DDD ambition and no fake layering claims.
2. Real adapters using framework imports outside the domain core.
3. One or two abstract bases that genuinely encode stable non-structural contracts.

## False Positive / Regression Cases

1. Many small `Command` / `Query` / `Handler` classes with weak evidence of read-side payoff.  
Expected: warn or medium-confidence drift finding, not an automatic blocker.
2. Multiple domain classes are behavior-light while services hold policy logic.  
Expected: warn about shape debt, not a fake boundary-leak claim.
3. A real adapter layer uses wrappers because the external SDK is unstable.  
Expected: do not call it ceremony-heavy sludge without cross-context leakage evidence.
