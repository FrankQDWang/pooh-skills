# Evals

## Should trigger

1. A repo has `tests/test_api.py` with `assert True`, `tests/test_user.py` with only happy-path assertions, and no CI workflow running tests.
2. A suite contains `@pytest.mark.skip`, `it.skip(...)`, `retries: 3`, and repeated `mocker.patch(...)` or `vi.mock(...)` against internal modules.
3. The repo has many tests, but none use `pytest.raises`, `assertRaises`, `.toThrow`, or similar failure-path evidence.

## Should not trigger

1. A repo has a GitHub Actions workflow running `pytest`, failure-path tests using `pytest.raises`, and no placeholder assertions.
2. A TS repo uses one boundary mock for an external HTTP client while still exercising real behavior in most tests.
3. A frontend repo has browser-real Playwright lanes and CI artifacts; this skill should not try to re-grade browser fidelity details already owned elsewhere.

## False positive / regression cases

1. A single legitimate `xfail` or `.skip` should not be described as “test suite collapse”; keep the language proportional.
2. A small number of mocks against boundary adapters should not be treated as proof of internal-logic over-mocking.
3. A repo with no Python or TypeScript code should return `not-applicable`.
