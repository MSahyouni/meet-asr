# Backend Tests Mirror

This folder mirrors the canonical test suite layout used in the reference architecture.

Current source of truth for tests remains the repository root `tests/` directory.

Suggested mapping:
- `tests/smoke_test.py` -> `apps/api/tests/unit/`
- `tests/test_api_units.py` -> `apps/api/tests/unit/`
- `tests/test_auth_security.py` -> `apps/api/tests/integration/`
- `tests/test_secure_endpoints.py` -> `apps/api/tests/integration/`
- `tests/test_tts_integration.py` -> `apps/api/tests/integration/`
