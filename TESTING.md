# Testing Strategy

This project uses a layered Python test strategy so regressions are caught early and CI remains fast.

## Test layers

- `unit` tests validate pure helpers and deterministic logic in isolation.
- `integration` tests validate API route behavior and contract mapping with mocked dependencies.
- `e2e` tests run smoke scenarios through the ASGI app to verify end-to-end wiring.

## Directory layout

- `tests/api/unit`
- `tests/api/integration`
- `tests/api/e2e`
- `tests/agents/unit` (agent services/helpers)
- `tests/agents/integration` (agent graph/workflow boundaries, as needed)

## Markers

Pytest markers are enforced with `--strict-markers`:

- `unit`
- `integration`
- `e2e`

## Coverage policy

Coverage is enforced in CI with `pytest-cov`:

- Scope: `app.main`, `app.api.router`, `app.api.routes.meta`, and `app.api.routes.analyze`.
- Threshold: `85%` line coverage (`--cov-fail-under=85`).
- Report: terminal missing-lines output (`--cov-report=term-missing`).

## Useful commands

```bash
# full suite (same profile as CI)
uv run pytest -q

# run only fast unit tests
uv run pytest -q -m unit

# run integration + e2e
uv run pytest -q -m "integration or e2e"
```
