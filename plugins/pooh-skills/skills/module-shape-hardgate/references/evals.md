# Evaluation cases

Use these as the minimum manual regression set when changing the skill.

## Should trigger

1. `app/api/router.py` is ~1500 code lines and mixes FastAPI routes, Pydantic schemas, SQLAlchemy queries, retry logic, and formatting helpers.
2. `src/server/module.ts` exports 30+ symbols, imports 20+ modules, and contains several handlers plus DB access plus response shaping.
3. One file contains two or more functions above 120 code lines each.
4. A single TypeScript file duplicates near-identical CRUD handlers or validators in several blocks.
5. A module is not just large; it is simultaneously large, wide, mixed-responsibility, and import-heavy.

## Should not trigger

1. Generated OpenAPI / GraphQL / SDK clients under `generated/`, `vendor/`, or equivalent generated paths.
2. Alembic or migration history snapshots that are large by nature but mechanically produced.
3. A narrow `__init__.py` or `index.ts` barrel file that mostly re-exports symbols and contains little real logic.
4. A focused algorithm file that is medium-sized but still coherent and not acting as a hub.
5. A small route registry or dependency injection registry with low logic density.

## False positive / regression cases

1. `index.ts` re-exports many symbols but has almost no executable logic. Expected: do not hard-fail only because export count is high.
2. `__init__.py` exposes a public API surface but is otherwise mechanically simple. Expected: at most low-severity context, not `god-module`.
3. Test fixture files are large because they inline snapshots or payloads. Expected: severity should be reduced or excluded when the file is clearly non-production.
4. A schema-only file is long because it enumerates many field definitions, but has low fan-out and low branching. Expected: do not call it mixed-responsibility without additional evidence.
5. A repo mainly needs dependency cycles or boundary checks. Expected: prefer the dependency-focused skill, not this one.
6. A repo mainly needs domain-boundary leak / fake-DDD diagnosis. Expected: prefer the Pythonic DDD drift skill, not this one.
7. A repo mainly needs runtime / compile-time contract gates. Expected: prefer the signature-contract skill, not this one.
8. A large Python scanner file contains identifiers such as `next_actions` and `component_count`, but no UI path or UI framework imports. Expected: do not add the `ui` responsibility tag from raw identifier text alone.
9. A non-exempt Python or TypeScript source file has a syntax error. Expected: emit a `scan-blocker` finding and set `overall_verdict` to `scan-blocked`.
