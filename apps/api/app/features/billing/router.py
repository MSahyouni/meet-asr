"""
billing / router.py
Billing endpoints (JWT-protected; email comes from token, not client spoofing)
"""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status

from app.features.auth.security import (
    is_admin_email,
    resolve_email_from_authorization,
    resolve_payload_from_authorization,
)
from .schema import (
    SubscribeRequest,
    CancelSubscriptionRequest,
    UpdateBillingRequest,
    SubscriptionResponse,
    Invoice,
    PaymentMethod,
    BillingPlan,
    PlanType,
)
from .service import BillingService

router = APIRouter(prefix="/billing", tags=["Billing"])


def _require_current_email(authorization: Optional[str]) -> str:
    email = resolve_email_from_authorization(authorization)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    return email


def _require_self_or_admin(target_email: str, authorization: Optional[str]) -> str:
    payload = resolve_payload_from_authorization(authorization)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    caller_email = str(payload.get("sub") or "")
    if not caller_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )
    if caller_email.lower() == (target_email or "").strip().lower() or is_admin_email(caller_email):
        return caller_email
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: self or admin access required",
    )


def _require_invoice_owner_or_admin(invoice_id: str, authorization: Optional[str]) -> Invoice:
    _require_current_email(authorization)
    invoice = BillingService.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found",
        )
    _require_self_or_admin(str(invoice.user_email), authorization)
    return invoice


def _require_payment_owner_or_admin(payment_id: str, authorization: Optional[str]) -> PaymentMethod:
    _require_current_email(authorization)
    method = BillingService.get_payment_method(payment_id)
    if not method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment method {payment_id} not found",
        )
    _require_self_or_admin(str(method.user_email), authorization)
    return method


@router.get("/plans", response_model=list[BillingPlan])
async def get_plans():
    """Get all available billing plans"""
    return BillingService.get_billing_plans()


@router.get("/plans/{plan_type}", response_model=BillingPlan)
async def get_plan(plan_type: PlanType):
    """Get specific billing plan"""
    plan = BillingService.get_plan(plan_type)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_type} not found",
        )
    return plan


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe(
    req: SubscribeRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Subscribe the authenticated user to a plan.

    Email is taken from the Bearer token. Optional body `user_email` must match
    the token subject when provided.
    """
    token_email = _require_current_email(authorization)
    claimed = (req.user_email or "").strip()
    if claimed and claimed.lower() != token_email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_email does not match logged-in user",
        )
    try:
        subscription = BillingService.subscribe(
            token_email,
            req.plan_type,
            req.billing_cycle,
        )
        return SubscriptionResponse(
            user_email=subscription.user_email,
            plan_type=subscription.plan_type,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            next_billing_date=subscription.end_date,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/subscription/{user_email}", response_model=SubscriptionResponse)
async def get_subscription(
    user_email: str,
    authorization: Optional[str] = Header(None),
):
    """Get user subscription (self or admin)"""
    _require_self_or_admin(user_email, authorization)
    subscription = BillingService.get_subscription(user_email)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No subscription found for {user_email}",
        )

    return SubscriptionResponse(
        user_email=subscription.user_email,
        plan_type=subscription.plan_type,
        status=subscription.status,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        next_billing_date=subscription.end_date,
    )


@router.put("/subscription/{user_email}", response_model=SubscriptionResponse)
async def update_subscription(
    user_email: str,
    req: UpdateBillingRequest,
    authorization: Optional[str] = Header(None),
):
    """Update subscription (self or admin)"""
    _require_self_or_admin(user_email, authorization)
    try:
        subscription = BillingService.update_subscription(
            user_email,
            req.plan_type,
            req.billing_cycle,
            req.auto_renew,
        )
        return SubscriptionResponse(
            user_email=subscription.user_email,
            plan_type=subscription.plan_type,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            next_billing_date=subscription.end_date,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/cancel/{user_email}")
async def cancel_subscription(
    user_email: str,
    req: Optional[CancelSubscriptionRequest] = None,
    authorization: Optional[str] = Header(None),
):
    """Cancel subscription (self or admin)"""
    _require_self_or_admin(user_email, authorization)
    if req and req.user_email and str(req.user_email).lower() != user_email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_email does not match path",
        )
    try:
        BillingService.cancel_subscription(user_email)
        return {"status": "success", "message": "Subscription cancelled"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/invoices/{user_email}", response_model=Invoice)
async def create_invoice(
    user_email: str,
    plan_type: PlanType,
    authorization: Optional[str] = Header(None),
):
    """Create invoice for user (self or admin)"""
    _require_self_or_admin(user_email, authorization)
    try:
        return BillingService.create_invoice(user_email, plan_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/invoices/detail/{invoice_id}", response_model=Invoice)
async def get_invoice(
    invoice_id: str,
    authorization: Optional[str] = Header(None),
):
    """Get specific invoice (owner or admin)"""
    return _require_invoice_owner_or_admin(invoice_id, authorization)


@router.get("/invoices/{user_email}", response_model=list[Invoice])
async def get_invoices(
    user_email: str,
    authorization: Optional[str] = Header(None),
):
    """Get user invoices (self or admin)"""
    _require_self_or_admin(user_email, authorization)
    return BillingService.get_invoices(user_email)


@router.post("/invoices/{invoice_id}/pay", response_model=Invoice)
async def pay_invoice(
    invoice_id: str,
    authorization: Optional[str] = Header(None),
):
    """Mark invoice as paid (owner or admin)"""
    _require_invoice_owner_or_admin(invoice_id, authorization)
    try:
        return BillingService.pay_invoice(invoice_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/payment-methods/{user_email}", response_model=PaymentMethod)
async def add_payment_method(
    user_email: str,
    payment_type: str,
    last_four: str,
    authorization: Optional[str] = Header(None),
):
    """Add payment method (self or admin)"""
    _require_self_or_admin(user_email, authorization)
    return BillingService.add_payment_method(user_email, payment_type, last_four)


@router.get("/payment-methods/{user_email}", response_model=list[PaymentMethod])
async def get_payment_methods(
    user_email: str,
    authorization: Optional[str] = Header(None),
):
    """Get user payment methods (self or admin)"""
    _require_self_or_admin(user_email, authorization)
    return BillingService.get_payment_methods(user_email)


@router.delete("/payment-methods/{payment_id}")
async def delete_payment_method(
    payment_id: str,
    authorization: Optional[str] = Header(None),
):
    """Delete payment method (owner or admin)"""
    _require_payment_owner_or_admin(payment_id, authorization)
    try:
        BillingService.delete_payment_method(payment_id)
        return {"status": "success", "message": "Payment method deleted"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
