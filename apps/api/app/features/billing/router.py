"""
billing / router.py
Billing endpoints
"""

from fastapi import APIRouter, HTTPException, status
from .schema import (
    SubscribeRequest, CancelSubscriptionRequest, UpdateBillingRequest,
    SubscriptionResponse, Invoice, PaymentMethod, BillingPlan,
    PlanType
)
from .service import BillingService

router = APIRouter(prefix="/billing", tags=["Billing"])


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
            detail=f"Plan {plan_type} not found"
        )
    return plan


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe(req: SubscribeRequest):
    """
    Subscribe user to plan
    
    - **user_email**: User email
    - **plan_type**: Plan type (free, pro, enterprise)
    - **billing_cycle**: Billing cycle (monthly or yearly)
    """
    try:
        subscription = BillingService.subscribe(
            req.user_email,
            req.plan_type,
            req.billing_cycle
        )
        return SubscriptionResponse(
            user_email=subscription.user_email,
            plan_type=subscription.plan_type,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            next_billing_date=subscription.end_date
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/subscription/{user_email}", response_model=SubscriptionResponse)
async def get_subscription(user_email: str):
    """Get user subscription"""
    subscription = BillingService.get_subscription(user_email)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No subscription found for {user_email}"
        )
    
    return SubscriptionResponse(
        user_email=subscription.user_email,
        plan_type=subscription.plan_type,
        status=subscription.status,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        next_billing_date=subscription.end_date
    )


@router.put("/subscription/{user_email}", response_model=SubscriptionResponse)
async def update_subscription(user_email: str, req: UpdateBillingRequest):
    """
    Update subscription
    
    - **user_email**: User email
    - **plan_type**: New plan type (optional)
    - **billing_cycle**: New billing cycle (optional)
    - **auto_renew**: Auto renewal setting (optional)
    """
    try:
        subscription = BillingService.update_subscription(
            user_email,
            req.plan_type,
            req.billing_cycle,
            req.auto_renew
        )
        return SubscriptionResponse(
            user_email=subscription.user_email,
            plan_type=subscription.plan_type,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            next_billing_date=subscription.end_date
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/cancel/{user_email}")
async def cancel_subscription(user_email: str, req: CancelSubscriptionRequest = None):
    """Cancel subscription"""
    try:
        BillingService.cancel_subscription(user_email)
        return {"status": "success", "message": "Subscription cancelled"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/invoices/{user_email}", response_model=Invoice)
async def create_invoice(user_email: str, plan_type: PlanType):
    """Create invoice for user"""
    try:
        invoice = BillingService.create_invoice(user_email, plan_type)
        return invoice
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/invoices/{user_email}", response_model=list[Invoice])
async def get_invoices(user_email: str):
    """Get user invoices"""
    return BillingService.get_invoices(user_email)


@router.get("/invoices/detail/{invoice_id}", response_model=Invoice)
async def get_invoice(invoice_id: str):
    """Get specific invoice"""
    invoice = BillingService.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )
    return invoice


@router.post("/invoices/{invoice_id}/pay", response_model=Invoice)
async def pay_invoice(invoice_id: str):
    """Mark invoice as paid"""
    try:
        invoice = BillingService.pay_invoice(invoice_id)
        return invoice
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/payment-methods/{user_email}", response_model=PaymentMethod)
async def add_payment_method(user_email: str, payment_type: str, last_four: str):
    """
    Add payment method
    
    - **user_email**: User email
    - **payment_type**: Type (credit_card, debit_card, paypal)
    - **last_four**: Last 4 digits
    """
    return BillingService.add_payment_method(user_email, payment_type, last_four)


@router.get("/payment-methods/{user_email}", response_model=list[PaymentMethod])
async def get_payment_methods(user_email: str):
    """Get user payment methods"""
    return BillingService.get_payment_methods(user_email)


@router.delete("/payment-methods/{payment_id}")
async def delete_payment_method(payment_id: str):
    """Delete payment method"""
    try:
        BillingService.delete_payment_method(payment_id)
        return {"status": "success", "message": "Payment method deleted"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
