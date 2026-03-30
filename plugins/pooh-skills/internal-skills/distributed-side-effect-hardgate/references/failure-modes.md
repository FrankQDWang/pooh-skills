# High-signal failure modes

## Dual-write hazard

Typical shape:

1. persist business state
2. commit transaction
3. publish message or call external API inline

Crash window:
- database write committed
- external side effect absent or duplicated later

## Pre-commit side effect

Typical shape:

1. send webhook / publish event / call payment API
2. transaction later fails or never commits

Result:
- external system believes the action happened
- local source of truth disagrees

## Idempotency gap

Typical shape:
- consumer / webhook handler mutates state
- no message identity tracking
- no uniqueness barrier
- no dedupe table / idempotency key

Result:
- duplicate effects under redelivery or retry

## Unsafe retry

Typical shape:
- retry decorator wraps `publish`, `post`, `charge`, or equivalent
- no visible idempotency key or dedupe guarantee

Result:
- retry storm becomes side-effect storm

## Event contract gap

Typical shape:
- event payloads have no visible version
- producer and consumer drift independently
- "schema" lives only in tribal memory

## Dead-letter gap

Typical shape:
- handlers can fail
- there is no DLQ / poison queue / failed-event holding path
- failures disappear into logs or infinite redelivery
