"""
dashboard / router.py
Dashboard endpoints
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query, Header
from datetime import datetime
from app.features.auth.security import (
    resolve_email_from_authorization,
    resolve_payload_from_authorization,
    is_admin_email,
)
from .schema import (
    DashboardStats, UserActivity, SystemMetrics, APIUsage,
    UsageChartData, HealthStatus, UserStatsOverview, ReportRequest,
    ActivityType
)
from .service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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
    if caller_email.lower() == target_email.lower() or is_admin_email(caller_email):
        return caller_email
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: self or admin access required",
    )


def _require_admin(authorization: Optional[str]) -> str:
    payload = resolve_payload_from_authorization(authorization)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    caller_email = str(payload.get("sub") or "")
    if not is_admin_email(caller_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return caller_email


@router.get("/my-summary")
async def get_my_summary(authorization: Optional[str] = Header(None)):
    """Get quick dashboard summary for current user from Bearer token."""
    user_email = _require_current_email(authorization)
    stats = DashboardService.get_dashboard_stats(user_email)
    health = DashboardService.get_health_status()
    return {
        "user_email": user_email,
        "jobs": {
            "asr": stats.total_asr_jobs,
            "tts": stats.total_tts_jobs,
            "nlp": stats.total_nlp_jobs,
        },
        "storage_used": stats.storage_used,
        "api_calls_this_month": stats.api_calls_this_month,
        "api_calls_limit": stats.api_calls_limit,
        "system_health": health.status,
        "last_updated": stats.last_updated,
    }


@router.get("/my-activities", response_model=list[UserActivity])
async def get_my_activities(
    authorization: Optional[str] = Header(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get activities for current user from Bearer token."""
    user_email = _require_current_email(authorization)
    return DashboardService.get_user_activities(user_email, limit)


@router.get("/my-usage", response_model=list[APIUsage])
async def get_my_usage(
    authorization: Optional[str] = Header(None),
    days: int = Query(30, ge=1, le=365),
):
    """Get API usage for current user from Bearer token."""
    user_email = _require_current_email(authorization)
    return DashboardService.get_api_usage(user_email, days)


@router.get("/my-usage-chart", response_model=UsageChartData)
async def get_my_usage_chart(
    authorization: Optional[str] = Header(None),
    days: int = Query(30, ge=1, le=365),
):
    """Get usage chart data for current user from Bearer token."""
    user_email = _require_current_email(authorization)
    return DashboardService.get_usage_chart_data(user_email, days)


@router.get("/stats/{user_email}", response_model=DashboardStats)
async def get_stats(user_email: str, authorization: Optional[str] = Header(None)):
    """Get user dashboard statistics"""
    try:
        _require_self_or_admin(user_email, authorization)
        stats = DashboardService.get_dashboard_stats(user_email)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/activity/{user_email}", response_model=UserActivity)
async def record_activity(
    user_email: str,
    activity_type: ActivityType,
    description: str,
    metadata: dict = None,
    authorization: Optional[str] = Header(None),
):
    """Record user activity"""
    try:
        _require_self_or_admin(user_email, authorization)
        activity = DashboardService.record_activity(user_email, activity_type, description, metadata)
        return activity
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/activities/{user_email}", response_model=list[UserActivity])
async def get_activities(
    user_email: str,
    limit: int = Query(20, ge=1, le=100),
    authorization: Optional[str] = Header(None),
):
    """
    Get user activities
    
    - **user_email**: User email
    - **limit**: Maximum number of activities to return
    """
    _require_self_or_admin(user_email, authorization)
    activities = DashboardService.get_user_activities(user_email, limit)
    return activities


@router.get("/metrics", response_model=SystemMetrics)
async def get_metrics(authorization: Optional[str] = Header(None)):
    """Get system performance metrics"""
    _require_admin(authorization)
    metrics = DashboardService.get_system_metrics()
    return metrics


@router.get("/usage/{user_email}", response_model=list[APIUsage])
async def get_usage(
    user_email: str,
    days: int = Query(30, ge=1, le=365),
    authorization: Optional[str] = Header(None),
):
    """
    Get API usage for user
    
    - **user_email**: User email
    - **days**: Number of days to retrieve
    """
    _require_self_or_admin(user_email, authorization)
    usage = DashboardService.get_api_usage(user_email, days)
    return usage


@router.get("/usage-chart/{user_email}", response_model=UsageChartData)
async def get_usage_chart(
    user_email: str,
    days: int = Query(30, ge=1, le=365),
    authorization: Optional[str] = Header(None),
):
    """
    Get usage chart data for visualization
    
    - **user_email**: User email
    - **days**: Number of days to include in chart
    """
    _require_self_or_admin(user_email, authorization)
    chart_data = DashboardService.get_usage_chart_data(user_email, days)
    return chart_data


@router.get("/health", response_model=HealthStatus)
async def get_health(authorization: Optional[str] = Header(None)):
    """Get system health status"""
    _require_admin(authorization)
    health = DashboardService.get_health_status()
    return health


@router.get("/overview", response_model=UserStatsOverview)
async def get_overview(authorization: Optional[str] = Header(None)):
    """Get overall user statistics overview"""
    _require_admin(authorization)
    overview = DashboardService.get_user_stats_overview()
    return overview


@router.post("/report")
async def export_report(req: ReportRequest, authorization: Optional[str] = Header(None)):
    """
    Export report
    
    - **user_email**: User email
    - **report_type**: Type of report (usage, billing, activity, performance)
    - **date_from**: Start date
    - **date_to**: End date
    - **format**: Format (json, csv, pdf)
    """
    try:
        _require_self_or_admin(req.user_email, authorization)
        report = DashboardService.export_report(
            req.user_email,
            req.report_type,
            req.date_from,
            req.date_to
        )
        return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/summary/{user_email}")
async def get_summary(user_email: str, authorization: Optional[str] = Header(None)):
    """Get quick summary for user dashboard"""
    _require_self_or_admin(user_email, authorization)
    stats = DashboardService.get_dashboard_stats(user_email)
    health = DashboardService.get_health_status()
    
    return {
        "user_email": user_email,
        "jobs": {
            "asr": stats.total_asr_jobs,
            "tts": stats.total_tts_jobs,
            "nlp": stats.total_nlp_jobs
        },
        "storage_used": stats.storage_used,
        "api_calls_this_month": stats.api_calls_this_month,
        "api_calls_limit": stats.api_calls_limit,
        "system_health": health.status,
        "last_updated": stats.last_updated
    }
