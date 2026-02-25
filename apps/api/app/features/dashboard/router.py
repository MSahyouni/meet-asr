"""
dashboard / router.py
Dashboard endpoints
"""

from fastapi import APIRouter, HTTPException, status, Query
from datetime import datetime
from .schema import (
    DashboardStats, UserActivity, SystemMetrics, APIUsage,
    UsageChartData, HealthStatus, UserStatsOverview, ReportRequest,
    ActivityType
)
from .service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats/{user_email}", response_model=DashboardStats)
async def get_stats(user_email: str):
    """Get user dashboard statistics"""
    try:
        stats = DashboardService.get_dashboard_stats(user_email)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/activity/{user_email}", response_model=UserActivity)
async def record_activity(user_email: str, activity_type: ActivityType, description: str, metadata: dict = None):
    """Record user activity"""
    try:
        activity = DashboardService.record_activity(user_email, activity_type, description, metadata)
        return activity
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/activities/{user_email}", response_model=list[UserActivity])
async def get_activities(user_email: str, limit: int = Query(20, ge=1, le=100)):
    """
    Get user activities
    
    - **user_email**: User email
    - **limit**: Maximum number of activities to return
    """
    activities = DashboardService.get_user_activities(user_email, limit)
    return activities


@router.get("/metrics", response_model=SystemMetrics)
async def get_metrics():
    """Get system performance metrics"""
    metrics = DashboardService.get_system_metrics()
    return metrics


@router.get("/usage/{user_email}", response_model=list[APIUsage])
async def get_usage(user_email: str, days: int = Query(30, ge=1, le=365)):
    """
    Get API usage for user
    
    - **user_email**: User email
    - **days**: Number of days to retrieve
    """
    usage = DashboardService.get_api_usage(user_email, days)
    return usage


@router.get("/usage-chart/{user_email}", response_model=UsageChartData)
async def get_usage_chart(user_email: str, days: int = Query(30, ge=1, le=365)):
    """
    Get usage chart data for visualization
    
    - **user_email**: User email
    - **days**: Number of days to include in chart
    """
    chart_data = DashboardService.get_usage_chart_data(user_email, days)
    return chart_data


@router.get("/health", response_model=HealthStatus)
async def get_health():
    """Get system health status"""
    health = DashboardService.get_health_status()
    return health


@router.get("/overview", response_model=UserStatsOverview)
async def get_overview():
    """Get overall user statistics overview"""
    overview = DashboardService.get_user_stats_overview()
    return overview


@router.post("/report")
async def export_report(req: ReportRequest):
    """
    Export report
    
    - **user_email**: User email
    - **report_type**: Type of report (usage, billing, activity, performance)
    - **date_from**: Start date
    - **date_to**: End date
    - **format**: Format (json, csv, pdf)
    """
    try:
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
async def get_summary(user_email: str):
    """Get quick summary for user dashboard"""
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
