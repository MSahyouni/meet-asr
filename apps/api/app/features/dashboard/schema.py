"""
dashboard / schema.py
Dashboard domain schemas
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from enum import Enum


class ActivityType(str, Enum):
    """Activity types"""
    ASR = "asr"
    TTS = "tts"
    NLP = "nlp"
    LOGIN = "login"
    LOGOUT = "logout"
    SUBSCRIPTION_CHANGE = "subscription_change"
    FILE_UPLOAD = "file_upload"


class UserActivity(BaseModel):
    """User activity model"""
    activity_id: str
    user_email: EmailStr
    activity_type: ActivityType
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class SystemMetrics(BaseModel):
    """System performance metrics"""
    total_requests: int
    total_users: int
    active_users: int
    asr_requests: int
    tts_requests: int
    nlp_requests: int
    avg_response_time: float  # ms
    uptime_percentage: float  # 0-100
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    user_email: EmailStr
    total_asr_jobs: int
    total_tts_jobs: int
    total_nlp_jobs: int
    storage_used: int  # bytes
    api_calls_this_month: int
    api_calls_limit: int | None = None  # None for unlimited
    recent_activities: list[UserActivity]
    system_metrics: SystemMetrics
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class APIUsage(BaseModel):
    """API usage statistics"""
    user_email: EmailStr
    date: datetime
    asr_calls: int
    tts_calls: int
    nlp_calls: int
    total_calls: int


class UsageChartData(BaseModel):
    """Usage chart data"""
    labels: list[str]  # dates or time periods
    asr_data: list[int]
    tts_data: list[int]
    nlp_data: list[int]


class HealthStatus(BaseModel):
    """System health status"""
    status: str  # "healthy", "degraded", "down"
    asr_service: str  # "up", "down"
    tts_service: str  # "up", "down"
    nlp_service: str  # "up", "down"
    database: str  # "up", "down"
    cache: str  # "up", "down"
    last_check: datetime = Field(default_factory=datetime.utcnow)


class UserStatsOverview(BaseModel):
    """User statistics overview"""
    total_users: int
    active_users_today: int
    new_users_this_month: int
    churn_rate: float  # 0-1
    avg_session_duration: float  # seconds


class ReportRequest(BaseModel):
    """Report generation request"""
    user_email: EmailStr
    report_type: str  # "usage", "billing", "activity", "performance"
    date_from: datetime
    date_to: datetime
    format: str = "json"  # "json", "csv", "pdf"
