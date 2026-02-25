"""
billing / service.py
Billing services
"""

from datetime import datetime, timedelta
from .schema import (
    PlanType, SubscriptionStatus, Subscription, Invoice, 
    PaymentMethod, BillingPlan
)


# Temporary in-memory storage (replace with database)
active_subscriptions = {}
active_invoices = {}
payment_methods = {}
billing_plans = {
    PlanType.FREE: BillingPlan(
        plan_type=PlanType.FREE,
        name="Free Plan",
        price=0,
        billing_cycle="monthly",
        features=["Basic ASR", "Basic TTS", "Limited API calls"],
        max_requests_per_month=100
    ),
    PlanType.PRO: BillingPlan(
        plan_type=PlanType.PRO,
        name="Professional Plan",
        price=29.99,
        billing_cycle="monthly",
        features=["Advanced ASR", "Advanced TTS", "Priority support"],
        max_requests_per_month=10000
    ),
    PlanType.ENTERPRISE: BillingPlan(
        plan_type=PlanType.ENTERPRISE,
        name="Enterprise Plan",
        price=299.99,
        billing_cycle="monthly",
        features=["Full Access", "Dedicated support", "Custom integration"],
        max_requests_per_month=None
    )
}


class BillingService:
    """Billing service"""
    
    @staticmethod
    def get_billing_plans() -> list[BillingPlan]:
        """Get all available billing plans"""
        return list(billing_plans.values())
    
    @staticmethod
    def get_plan(plan_type: PlanType) -> BillingPlan | None:
        """Get specific billing plan"""
        return billing_plans.get(plan_type)
    
    @staticmethod
    def subscribe(user_email: str, plan_type: PlanType, billing_cycle: str = "monthly") -> Subscription:
        """Subscribe user to plan"""
        plan = billing_plans.get(plan_type)
        if not plan:
            raise ValueError(f"Plan {plan_type} not found")
        
        # Check if already subscribed
        if user_email in active_subscriptions:
            raise ValueError(f"User {user_email} already has active subscription")
        
        start_date = datetime.utcnow()
        # Calculate end date based on billing cycle
        if billing_cycle == "monthly":
            end_date = start_date + timedelta(days=30)
        elif billing_cycle == "yearly":
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
            auto_renew=True
        )
        
        active_subscriptions[user_email] = subscription.dict()
        return subscription
    
    @staticmethod
    def get_subscription(user_email: str) -> Subscription | None:
        """Get user subscription"""
        sub = active_subscriptions.get(user_email)
        if sub:
            return Subscription(**sub)
        return None
    
    @staticmethod
    def update_subscription(user_email: str, plan_type: PlanType = None, billing_cycle: str = None, auto_renew: bool = None) -> Subscription:
        """Update subscription plan"""
        if user_email not in active_subscriptions:
            raise ValueError(f"No subscription found for {user_email}")
        
        sub = active_subscriptions[user_email]
        
        if plan_type:
            plan = billing_plans.get(plan_type)
            if not plan:
                raise ValueError(f"Plan {plan_type} not found")
            sub["plan_type"] = plan_type
        
        if billing_cycle:
            sub["billing_cycle"] = billing_cycle
        
        if auto_renew is not None:
            sub["auto_renew"] = auto_renew
        
        active_subscriptions[user_email] = sub
        return Subscription(**sub)
    
    @staticmethod
    def cancel_subscription(user_email: str) -> None:
        """Cancel subscription"""
        if user_email not in active_subscriptions:
            raise ValueError(f"No subscription found for {user_email}")
        
        sub = active_subscriptions[user_email]
        sub["status"] = SubscriptionStatus.CANCELLED
        sub["end_date"] = datetime.utcnow()
        active_subscriptions[user_email] = sub
    
    @staticmethod
    def create_invoice(user_email: str, plan_type: PlanType) -> Invoice:
        """Create invoice for user"""
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
            status="pending"
        )
        
        active_invoices[invoice_id] = invoice.dict()
        return invoice
    
    @staticmethod
    def get_invoices(user_email: str) -> list[Invoice]:
        """Get user invoices"""
        invoices = []
        for invoice_data in active_invoices.values():
            if invoice_data["user_email"] == user_email:
                invoices.append(Invoice(**invoice_data))
        return invoices
    
    @staticmethod
    def get_invoice(invoice_id: str) -> Invoice | None:
        """Get specific invoice"""
        invoice_data = active_invoices.get(invoice_id)
        if invoice_data:
            return Invoice(**invoice_data)
        return None
    
    @staticmethod
    def pay_invoice(invoice_id: str) -> Invoice:
        """Mark invoice as paid"""
        if invoice_id not in active_invoices:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        invoice = active_invoices[invoice_id]
        invoice["status"] = "paid"
        active_invoices[invoice_id] = invoice
        return Invoice(**invoice)
    
    @staticmethod
    def add_payment_method(user_email: str, payment_type: str, last_four: str) -> PaymentMethod:
        """Add payment method for user"""
        payment_id = f"PM-{user_email}-{datetime.utcnow().timestamp()}"
        
        payment_method = PaymentMethod(
            payment_id=payment_id,
            user_email=user_email,
            payment_type=payment_type,
            last_four=last_four,
            is_default=len(payment_methods.get(user_email, [])) == 0
        )
        
        if user_email not in payment_methods:
            payment_methods[user_email] = []
        
        payment_methods[user_email].append(payment_method.dict())
        return payment_method
    
    @staticmethod
    def get_payment_methods(user_email: str) -> list[PaymentMethod]:
        """Get user payment methods"""
        methods = payment_methods.get(user_email, [])
        return [PaymentMethod(**method) for method in methods]
    
    @staticmethod
    def delete_payment_method(payment_id: str) -> None:
        """Delete payment method"""
        for email, methods in payment_methods.items():
            for i, method in enumerate(methods):
                if method["payment_id"] == payment_id:
                    methods.pop(i)
                    return
        raise ValueError(f"Payment method {payment_id} not found")
