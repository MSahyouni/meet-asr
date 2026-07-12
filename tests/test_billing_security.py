# tests/test_billing_security.py — billing endpoints require JWT / self-or-admin
import importlib
from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

billing_router_module = importlib.import_module("app.features.billing.router")


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(billing_router_module.router)
    return TestClient(app)


def test_plans_remain_public():
    client = _build_client()
    resp = client.get("/billing/plans")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_subscribe_requires_bearer_token():
    client = _build_client()
    resp = client.post(
        "/billing/subscribe",
        json={"plan_type": "pro", "billing_cycle": "monthly"},
    )
    assert resp.status_code == 401
    assert "bearer token" in resp.json()["detail"].lower()


def test_subscribe_uses_token_email_not_body(monkeypatch):
    client = _build_client()
    monkeypatch.setattr(
        billing_router_module,
        "resolve_email_from_authorization",
        lambda _: "token-user@example.com",
    )

    captured = {}

    def _subscribe(email, plan_type, billing_cycle="monthly"):
        captured["email"] = email
        return SimpleNamespace(
            user_email=email,
            plan_type=plan_type,
            status="active",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 2, 1),
        )

    monkeypatch.setattr(billing_router_module.BillingService, "subscribe", staticmethod(_subscribe))

    resp = client.post(
        "/billing/subscribe",
        headers={"Authorization": "Bearer token"},
        json={
            "user_email": "attacker@evil.com",
            "plan_type": "pro",
            "billing_cycle": "monthly",
        },
    )
    assert resp.status_code == 403
    assert "does not match" in resp.json()["detail"].lower()
    assert "email" not in captured


def test_subscribe_succeeds_for_token_subject(monkeypatch):
    client = _build_client()
    monkeypatch.setattr(
        billing_router_module,
        "resolve_email_from_authorization",
        lambda _: "user@example.com",
    )

    def _subscribe(email, plan_type, billing_cycle="monthly"):
        return SimpleNamespace(
            user_email=email,
            plan_type=plan_type.value if hasattr(plan_type, "value") else plan_type,
            status="active",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 2, 1),
        )

    monkeypatch.setattr(billing_router_module.BillingService, "subscribe", staticmethod(_subscribe))

    resp = client.post(
        "/billing/subscribe",
        headers={"Authorization": "Bearer token"},
        json={"plan_type": "pro", "billing_cycle": "monthly"},
    )
    assert resp.status_code == 200
    assert resp.json()["user_email"] == "user@example.com"


def test_get_subscription_forbidden_for_other_user(monkeypatch):
    client = _build_client()
    monkeypatch.setattr(
        billing_router_module,
        "resolve_payload_from_authorization",
        lambda _: {"sub": "user@example.com"},
    )
    monkeypatch.setattr(billing_router_module, "is_admin_email", lambda _: False)

    resp = client.get(
        "/billing/subscription/victim@example.com",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 403


def test_get_subscription_allowed_for_self(monkeypatch):
    client = _build_client()
    monkeypatch.setattr(
        billing_router_module,
        "resolve_payload_from_authorization",
        lambda _: {"sub": "user@example.com"},
    )
    monkeypatch.setattr(billing_router_module, "is_admin_email", lambda _: False)
    monkeypatch.setattr(
        billing_router_module.BillingService,
        "get_subscription",
        staticmethod(
            lambda email: SimpleNamespace(
                user_email=email,
                plan_type="pro",
                status="active",
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 2, 1),
            )
        ),
    )

    resp = client.get(
        "/billing/subscription/user@example.com",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 200
    assert resp.json()["user_email"] == "user@example.com"


def test_invoice_detail_requires_owner(monkeypatch):
    client = _build_client()
    monkeypatch.setattr(
        billing_router_module,
        "resolve_email_from_authorization",
        lambda _: "user@example.com",
    )
    monkeypatch.setattr(
        billing_router_module,
        "resolve_payload_from_authorization",
        lambda _: {"sub": "user@example.com"},
    )
    monkeypatch.setattr(billing_router_module, "is_admin_email", lambda _: False)
    monkeypatch.setattr(
        billing_router_module.BillingService,
        "get_invoice",
        staticmethod(
            lambda _id: SimpleNamespace(
                invoice_id=_id,
                user_email="other@example.com",
                plan_type="pro",
                amount=10.0,
                currency="USD",
                period_start=datetime(2026, 1, 1),
                period_end=datetime(2026, 2, 1),
                status="pending",
                created_at=datetime(2026, 1, 1),
            )
        ),
    )

    resp = client.get(
        "/billing/invoices/detail/INV-1",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 403
