# Manual eval cases

## Should trigger

1. A handler does `session.commit()` and then `event_bus.publish(...)`.
2. A webhook handler uses `@retry` around an external POST with no idempotency key.
3. A consumer mutates local state on `message_received` with no dedupe storage.

## Should usually warn, not hard-fail

1. A repo contains event DTOs but versioning is only partial.
2. A repo uses async workers but no explicit DLQ appears locally.

## Should not trigger

1. Purely synchronous CRUD repo with no broker, webhook, or worker surface.
2. Read-only projections / report generators with no side effects.
3. Activity-local retries inside a clearly idempotent path with visible idempotency key.
