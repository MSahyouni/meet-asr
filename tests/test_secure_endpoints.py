from datetime import datetime
from types import SimpleNamespace
import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

dashboard_router_module = importlib.import_module("app.features.dashboard.router")
users_router_module = importlib.import_module("app.features.users.router")



def _build_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(users_router_module.router)
    app.include_router(dashboard_router_module.router)
    return TestClient(app)


def test_users_me_requires_bearer_token():
    client = _build_test_client()
    resp = client.get("/users/me")

    assert resp.status_code == 401
    assert "bearer token" in resp.json()["detail"].lower()


def test_users_me_returns_profile(monkeypatch):
    client = _build_test_client()

    monkeypatch.setattr(users_router_module, "resolve_email_from_authorization", lambda _: "user@example.com")
    monkeypatch.setattr(
        users_router_module.UserService,
        "get_user_profile",
        lambda email: {
            "id": "u1",
            "email": email,
            "full_name": "Test User",
            "avatar_url": "",
            "bio": "",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        },
    )

    resp = client.get("/users/me", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert data["full_name"] == "Test User"


def test_users_me_returns_404_when_profile_missing(monkeypatch):
    client = _build_test_client()

    monkeypatch.setattr(users_router_module, "resolve_email_from_authorization", lambda _: "missing@example.com")
    monkeypatch.setattr(users_router_module.UserService, "get_user_profile", lambda _: None)

    resp = client.get("/users/me", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_dashboard_my_summary_requires_bearer_token():
    client = _build_test_client()
    resp = client.get("/dashboard/my-summary")

    assert resp.status_code == 401
    assert "bearer token" in resp.json()["detail"].lower()


def test_dashboard_my_summary_returns_expected_payload(monkeypatch):
    client = _build_test_client()

    monkeypatch.setattr(dashboard_router_module, "resolve_email_from_authorization", lambda _: "user@example.com")
    monkeypatch.setattr(
        dashboard_router_module.DashboardService,
        "get_dashboard_stats",
        lambda email: SimpleNamespace(
            user_email=email,
            total_asr_jobs=4,
            total_tts_jobs=2,
            total_nlp_jobs=1,
            storage_used=7340032,
            api_calls_this_month=7,
            api_calls_limit=10000,
            last_updated=datetime(2026, 1, 2, 12, 0, 0),
        ),
    )
    monkeypatch.setattr(
        dashboard_router_module.DashboardService,
        "get_health_status",
        lambda: SimpleNamespace(status="healthy"),
    )

    resp = client.get("/dashboard/my-summary", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_email"] == "user@example.com"
    assert data["jobs"] == {"asr": 4, "tts": 2, "nlp": 1}
    assert data["api_calls_this_month"] == 7
    assert data["system_health"] == "healthy"
