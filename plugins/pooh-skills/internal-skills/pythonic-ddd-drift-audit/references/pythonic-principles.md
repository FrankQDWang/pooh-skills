# Pythonic architecture principles for this audit

This audit is anchored in a few non-negotiable ideas:

## 1. Pythonic does not mean shapeless

In a large repo, Pythonic means reducing reader burden:
- explicit boundaries
- light abstractions
- types where they clarify contracts
- objects that carry meaningful behavior instead of decorative ceremony

## 2. Domain purity matters more than folder names

A `domain/` package that imports FastAPI, SQLAlchemy, HTTP clients, or queue clients is not pure just because the directory is named nicely.

## 3. Structural abstraction is often better than nominal ceremony

If a dependency is just "something with these methods", a structural port (`Protocol`, callable shape, thin typed contract) is often better than inheritance scaffolding.

## 4. Bounded contexts should not share their guts

Cross-context collaboration should happen through explicit boundaries:
- events
- DTOs
- public application services
- anti-corruption / translation layers

Direct domain-model imports across contexts are usually model bleed.

## 5. CQRS is local medicine, not universal religion

If read and write needs are genuinely different, CQRS can help.
If not, it often becomes file-count inflation with no payoff.

## 6. Flattening is a valid repair

A repo does not become less mature by deleting meaningless wrappers.
Often it becomes more honest.
