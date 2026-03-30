# Distributed side-effect hardening principles

This skill assumes the following engineering posture:

## 1. Dual writes are guilty until proven otherwise

If code performs a database write and a broker publish / webhook / remote side effect in the same business flow, the default assumption is **fragile correctness** unless a credible outbox / relay / CDC handoff exists.

## 2. Retries are not safety; retries are amplification

A retry wrapped around a non-idempotent effect is not resilience. It is a duplicate generator.

## 3. Consumers must survive at-least-once delivery

Assume the broker can redeliver.
Assume the handler can restart mid-flight.
Assume the same event can arrive twice.
If the consumer cannot survive that, it is not production-safe.

## 4. Event contracts are real interfaces

Integration events should be explicit about shape and version. A pile of loose dictionaries or ad-hoc JSON payloads is not an interface contract.

## 5. Dead-letter handling is not optional once the system matters

If the system has asynchronous handlers that can fail, then failed messages need somewhere explicit to go, even if the first implementation is intentionally minimal.

## 6. Not applicable is a valid outcome

Do not force this skill onto repos that have no meaningful broker / queue / webhook / worker / integration-side-effect surface.
