import importlib
import sys

from app.features.auth import security


def test_token_ttl_seconds_has_minimum(monkeypatch):
    monkeypatch.setenv("JWT_EXPIRES_SECONDS", "10")
    assert security.token_ttl_seconds() == 300


def test_create_and_decode_access_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_EXPIRES_SECONDS", "3600")
    monkeypatch.setenv("JWT_ISSUER", "meet-asr")
    monkeypatch.setenv("JWT_AUDIENCE", "meet-asr-api")

    token = security.create_access_token("user@example.com", "u1", "User One")
    payload = security.decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "user@example.com"
    assert payload["uid"] == "u1"
    assert payload["name"] == "User One"
    assert payload["iss"] == "meet-asr"
    assert payload["aud"] == "meet-asr-api"
    assert "jti" in payload
    assert payload["exp"] > payload["iat"]


def test_decode_rejects_tampered_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ISSUER", "meet-asr")
    monkeypatch.setenv("JWT_AUDIENCE", "meet-asr-api")
    token = security.create_access_token("user@example.com", "u1", "User One")
    head, body, sig = token.split(".")
    replacement = "A" if sig[0] != "A" else "B"
    tampered = f"{head}.{body}.{replacement + sig[1:]}"

    assert security.decode_access_token(tampered) is None


def test_decode_rejects_expired_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_EXPIRES_SECONDS", "300")
    monkeypatch.setenv("JWT_ISSUER", "meet-asr")
    monkeypatch.setenv("JWT_AUDIENCE", "meet-asr-api")
    token = security.create_access_token("user@example.com", "u1", "User One")

    original_time = security.time.time
    try:
        security.time.time = lambda: int(original_time()) + 301
        assert security.decode_access_token(token) is None
    finally:
        security.time.time = original_time


def test_extract_and_resolve_email_from_authorization(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ISSUER", "meet-asr")
    monkeypatch.setenv("JWT_AUDIENCE", "meet-asr-api")
    token = security.create_access_token("user@example.com", "u1", "User One")
    auth_header = f"Bearer {token}"
    monkeypatch.setattr(security, "_is_payload_session_valid", lambda payload: True)

    assert security.extract_bearer_token(auth_header) == token
    assert security.resolve_email_from_authorization(auth_header) == "user@example.com"
    assert security.resolve_payload_from_authorization(auth_header)["uid"] == "u1"


def test_extract_bearer_token_invalid_values():
    assert security.extract_bearer_token(None) is None
    assert security.extract_bearer_token("") is None
    assert security.extract_bearer_token("Basic abc") is None
    assert security.extract_bearer_token("Bearer   ") is None


def test_is_admin_email_case_insensitive(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@local, OWNER@local")

    assert security.is_admin_email("admin@local") is True
    assert security.is_admin_email("owner@local") is True
    assert security.is_admin_email("OWNER@LOCAL") is True
    assert security.is_admin_email("user@local") is False


def test_auth_package_router_import_is_lazy():
    sys.modules.pop("app.features.auth.router", None)
    import app.features.auth as auth_pkg

    importlib.reload(auth_pkg)
    assert "app.features.auth.router" not in sys.modules


def test_decode_rejects_wrong_issuer_or_audience(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ISSUER", "issuer-a")
    monkeypatch.setenv("JWT_AUDIENCE", "aud-a")
    token = security.create_access_token("user@example.com", "u1", "User One")

    monkeypatch.setenv("JWT_ISSUER", "issuer-b")
    assert security.decode_access_token(token) is None

    monkeypatch.setenv("JWT_ISSUER", "issuer-a")
    monkeypatch.setenv("JWT_AUDIENCE", "aud-b")
    assert security.decode_access_token(token) is None


def test_create_token_requires_strong_secret_in_production(monkeypatch):
    monkeypatch.setenv("ASR_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    try:
        security.create_access_token("user@example.com", "u1", "User One")
        assert False, "Expected RuntimeError for weak/default JWT secret in production"
    except RuntimeError as exc:
        assert "JWT_SECRET" in str(exc)
