"""
billing / schema.py
Billing domain schemas
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime
from enum import Enum


class PlanType(str, Enum):
    """Billing plan types"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BillingPlan(BaseModel):
    """Billing plan model"""
    plan_type: PlanType
    name: str
    price: float = Field(ge=0)
    billing_cycle: str  # "monthly", "yearly"
    features: list[str]
    max_requests_per_month: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(use_enum_values=True)


class Subscription(BaseModel):
    """User subscription model"""
    user_email: EmailStr
    plan_type: PlanType
    status: SubscriptionStatus
    billing_cycle: str
    start_date: datetime
    end_date: datetime | None = None
    auto_renew: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(use_enum_values=True)


class Invoice(BaseModel):
    """Invoice model"""
    invoice_id: str
    user_email: EmailStr
    plan_type: PlanType
    amount: float = Field(ge=0)
    currency: str = "USD"
    period_start: datetime
    period_end: datetime
    status: str  # "paid", "pending", "failed"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(use_enum_values=True)


class PaymentMethod(BaseModel):
    """Payment method model"""
    payment_id: str
    user_email: EmailStr
    payment_type: str  # "credit_card", "debit_card", "paypal"
    last_four: str | None = None  # Last 4 digits
    is_default: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(use_enum_values=True)


class SubscribeRequest(BaseModel):
    """Subscribe to plan request"""
    user_email: EmailStr
    plan_type: PlanType
    billing_cycle: str = Field(default="monthly")


class CancelSubscriptionRequest(BaseModel):
    """Cancel subscription request"""
    user_email: EmailStr
    reason: str | None = None


class UpdateBillingRequest(BaseModel):
    """Update billing request"""
    plan_type: PlanType | None = None
    billing_cycle: str | None = None
    auto_renew: bool | None = None


class SubscriptionResponse(BaseModel):
    """Subscription response"""
    user_email: EmailStr
    plan_type: PlanType
    status: SubscriptionStatus
    start_date: datetime
    end_date: datetime | None
    next_billing_date: datetime | None
    
    model_config = ConfigDict(use_enum_values=True)
