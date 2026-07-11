"""
billing / service.py
Billing services (persisted in SQLite via local_db)
"""

from datetime import datetime, timedelta

from app.infrastructure.database import local_db
from .schema import (
    PlanType,
    SubscriptionStatus,
    Subscription,
    Invoice,
    PaymentMethod,
    BillingPlan,
)


billing_plans = {
    PlanType.FREE: BillingPlan(
        plan_type=PlanType.FREE,
        name="Free Plan",
        price=0,
        billing_cycle="monthly",
        features=["Basic ASR", "Basic TTS", "Limited API calls"],
        max_requests_per_month=100,
    ),
    PlanType.PRO: BillingPlan(
        plan_type=PlanType.PRO,
        name="Professional Plan",
        price=29.99,
        billing_cycle="monthly",
        features=["Advanced ASR", "Advanced TTS", "Priority support"],
        max_requests_per_month=10000,
    ),
    PlanType.ENTERPRISE: BillingPlan(
        plan_type=PlanType.ENTERPRISE,
        name="Enterprise Plan",
        price=299.99,
        billing_cycle="monthly",
        features=["Full Access", "Dedicated support", "Custom integration"],
        max_requests_per_month=None,
    ),
}


def _model_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _serialize_subscription(subscription: Subscription) -> dict:
    payload = _model_dump(subscription)
    for key in ("start_date", "end_date", "created_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    payload["user_email"] = str(payload["user_email"])
    return payload


def _serialize_invoice(invoice: Invoice) -> dict:
    payload = _model_dump(invoice)
    for key in ("period_start", "period_end", "created_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    payload["user_email"] = str(payload["user_email"])
    return payload


def _serialize_payment_method(method: PaymentMethod) -> dict:
    payload = _model_dump(method)
    if isinstance(payload.get("created_at"), datetime):
        payload["created_at"] = payload["created_at"].isoformat()
    payload["user_email"] = str(payload["user_email"])
    return payload


class BillingService:
    """Billing service"""

    @staticmethod
    def get_billing_plans() -> list[BillingPlan]:
        return list(billing_plans.values())

    @staticmethod
    def get_plan(plan_type: PlanType) -> BillingPlan | None:
        return billing_plans.get(plan_type)

    @staticmethod
    def subscribe(user_email: str, plan_type: PlanType, billing_cycle: str = "monthly") -> Subscription:
        plan = billing_plans.get(plan_type)
        if not plan:
            raise ValueError(f"Plan {plan_type} not found")

        if local_db.get_subscription(user_email):
            raise ValueError(f"User {user_email} already has active subscription")

        start_date = datetime.utcnow()
        if billing_cycle == "yearly":
            end_date = start_date + timedelta(days=365)
        else:
            end_date = start_date + timedelta(days=30)

        subscription = Subscription(
            user_email=user_email,
            plan_type=plan_type,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=billing_cycle,
            start_date=start_date,
            end_date=end_date,
            auto_renew=True,
        )
        local_db.upsert_subscription(_serialize_subscription(subscription))
        return subscription

    @staticmethod
    def get_subscription(user_email: str) -> Subscription | None:
        sub = local_db.get_subscription(user_email)
        if sub:
            return Subscription(**sub)
        return None

    @staticmethod
    def update_subscription(
        user_email: str,
        plan_type: PlanType = None,
        billing_cycle: str = None,
        auto_renew: bool = None,
    ) -> Subscription:
        existing = local_db.get_subscription(user_email)
        if not existing:
            raise ValueError(f"No subscription found for {user_email}")

        subscription = Subscription(**existing)
        if plan_type:
            if plan_type not in billing_plans:
                raise ValueError(f"Plan {plan_type} not found")
            subscription.plan_type = plan_type
        if billing_cycle:
            subscription.billing_cycle = billing_cycle
        if auto_renew is not None:
            subscription.auto_renew = auto_renew

        local_db.upsert_subscription(_serialize_subscription(subscription))
        return subscription

    @staticmethod
    def cancel_subscription(user_email: str) -> None:
        existing = local_db.get_subscription(user_email)
        if not existing:
            raise ValueError(f"No subscription found for {user_email}")

        subscription = Subscription(**existing)
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.end_date = datetime.utcnow()
        local_db.upsert_subscription(_serialize_subscription(subscription))

    @staticmethod
    def create_invoice(user_email: str, plan_type: PlanType) -> Invoice:
        plan = billing_plans.get(plan_type)
        if not plan:
            raise ValueError(f"Plan {plan_type} not found")

        invoice_id = f"INV-{user_email}-{datetime.utcnow().timestamp()}"
        invoice = Invoice(
            invoice_id=invoice_id,
            user_email=user_email,
            plan_type=plan_type,
            amount=plan.price,
            currency="USD",
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow() + timedelta(days=30),
            status="pending",
        )
        local_db.create_invoice(_serialize_invoice(invoice))
        return invoice

    @staticmethod
    def get_invoices(user_email: str) -> list[Invoice]:
        return [Invoice(**row) for row in local_db.get_invoices_for_user(user_email)]

    @staticmethod
    def get_invoice(invoice_id: str) -> Invoice | None:
        row = local_db.get_invoice(invoice_id)
        if row:
            return Invoice(**row)
        return None

    @staticmethod
    def pay_invoice(invoice_id: str) -> Invoice:
        if not local_db.update_invoice_status(invoice_id, "paid"):
            raise ValueError(f"Invoice {invoice_id} not found")
        row = local_db.get_invoice(invoice_id)
        return Invoice(**row)

    @staticmethod
    def add_payment_method(user_email: str, payment_type: str, last_four: str) -> PaymentMethod:
        payment_id = f"PM-{user_email}-{datetime.utcnow().timestamp()}"
        existing = local_db.get_payment_methods(user_email)
        payment_method = PaymentMethod(
            payment_id=payment_id,
            user_email=user_email,
            payment_type=payment_type,
            last_four=last_four,
            is_default=len(existing) == 0,
        )
        local_db.add_payment_method(_serialize_payment_method(payment_method))
        return payment_method

    @staticmethod
    def get_payment_methods(user_email: str) -> list[PaymentMethod]:
        return [PaymentMethod(**row) for row in local_db.get_payment_methods(user_email)]

    @staticmethod
    def delete_payment_method(payment_id: str) -> None:
        if not local_db.delete_payment_method(payment_id):
            raise ValueError(f"Payment method {payment_id} not found")
