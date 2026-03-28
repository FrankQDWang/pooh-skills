# Manual eval cases

## Should trigger strongly

1. `domain/` imports `sqlalchemy`, `fastapi`, `requests`, or equivalent infra details.
2. `contexts/billing/domain/...` imports `contexts/orders/domain/...`.
3. An abstract base class contains only `raise NotImplementedError` methods.
4. A `Service` class only forwards calls to a collaborator.

## Should usually warn, not hard-fail

1. Many small `Command` / `Query` / `Handler` classes with weak evidence of read-side payoff.
2. Multiple domain classes are behavior-light while services hold policy logic.

## Should not trigger

1. A lightweight app with no DDD ambition and no fake layering claims.
2. Real adapters using framework imports outside the domain core.
3. One or two abstract bases that genuinely encode stable non-structural contracts.
