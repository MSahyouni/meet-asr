"""
dashboard / service.py
Dashboard services
"""

from datetime import datetime, timedelta
from app.infrastructure.database import local_db
from .schema import (
    UserActivity, SystemMetrics, DashboardStats, APIUsage,
    UsageChartData, HealthStatus, UserStatsOverview, ActivityType
)


class DashboardService:
    """Dashboard service"""
    
    @staticmethod
    def get_dashboard_stats(user_email: str) -> DashboardStats:
        """Get dashboard statistics for user"""
        activities = DashboardService.get_user_activities(user_email)
        metrics = DashboardService.get_system_metrics()

        asr_jobs = local_db.count_activities_by_type_for_user(user_email, ActivityType.ASR.value)
        tts_jobs = local_db.count_activities_by_type_for_user(user_email, ActivityType.TTS.value)
        nlp_jobs = local_db.count_activities_by_type_for_user(user_email, ActivityType.NLP.value)
        
        return DashboardStats(
            user_email=user_email,
            total_asr_jobs=asr_jobs,
            total_tts_jobs=tts_jobs,
            total_nlp_jobs=nlp_jobs,
            storage_used=1048576 * (asr_jobs + tts_jobs + nlp_jobs),  # ~1MB per job
            api_calls_this_month=asr_jobs + tts_jobs + nlp_jobs,
            api_calls_limit=10000,  # Example limit
            recent_activities=activities[-5:] if activities else [],  # Last 5
            system_metrics=metrics
        )
    
    @staticmethod
    def record_activity(user_email: str, activity_type: ActivityType, description: str, metadata: dict = None) -> UserActivity:
        """Record user activity"""
        activity_id = f"ACT-{user_email}-{datetime.utcnow().timestamp()}"

        activity = UserActivity(
            activity_id=activity_id,
            user_email=user_email,
            activity_type=activity_type,
            description=description,
            metadata=metadata or {}
        )

        local_db.add_activity(
            activity_id=activity.activity_id,
            user_email=activity.user_email,
            activity_type=activity.activity_type.value if hasattr(activity.activity_type, "value") else str(activity.activity_type),
            description=activity.description,
            timestamp=activity.timestamp,
            metadata=activity.metadata,
        )
        return activity
    
    @staticmethod
    def get_user_activities(user_email: str, limit: int = 20) -> list[UserActivity]:
        """Get user activities"""
        activities = local_db.get_activities(user_email, limit)
        return [UserActivity(**act) for act in activities]
    
    @staticmethod
    def get_system_metrics() -> SystemMetrics:
        """Get system performance metrics"""
        total_requests = local_db.count_activities()
        asr_requests = local_db.count_activities_by_type(ActivityType.ASR.value)
        tts_requests = local_db.count_activities_by_type(ActivityType.TTS.value)
        nlp_requests = local_db.count_activities_by_type(ActivityType.NLP.value)
        total_users = local_db.count_users(active_only=False)
        active_users = local_db.count_users(active_only=True)
        
        return SystemMetrics(
            total_requests=total_requests,
            total_users=total_users,
            active_users=active_users,
            asr_requests=asr_requests,
            tts_requests=tts_requests,
            nlp_requests=nlp_requests,
            avg_response_time=45.5,  # Example
            uptime_percentage=99.9
        )
    
    @staticmethod
    def get_api_usage(user_email: str, days: int = 30) -> list[APIUsage]:
        """Get API usage for user over period"""
        usage_rows = local_db.get_usage_by_date(user_email, days)
        usage_list = []
        for row in usage_rows:
            date = datetime.fromisoformat(f"{row['day']}T00:00:00")
            usage_list.append(APIUsage(
                user_email=user_email,
                date=date,
                asr_calls=int(row.get("asr_calls", 0)),
                tts_calls=int(row.get("tts_calls", 0)),
                nlp_calls=int(row.get("nlp_calls", 0)),
                total_calls=int(row.get("total_calls", 0)),
            ))
        return sorted(usage_list, key=lambda x: x.date, reverse=True)[:days]
    
    @staticmethod
    def get_usage_chart_data(user_email: str, days: int = 30) -> UsageChartData:
        """Get chart data for usage visualization"""
        usage = DashboardService.get_api_usage(user_email, days)
        
        # Sort by date ascending for chart
        usage = sorted(usage, key=lambda x: x.date)
        
        labels = [u.date.strftime("%Y-%m-%d") for u in usage]
        asr_data = [u.asr_calls for u in usage]
        tts_data = [u.tts_calls for u in usage]
        nlp_data = [u.nlp_calls for u in usage]
        
        return UsageChartData(
            labels=labels,
            asr_data=asr_data,
            tts_data=tts_data,
            nlp_data=nlp_data
        )
    
    @staticmethod
    def get_health_status() -> HealthStatus:
        """Get system health status"""
        return HealthStatus(
            status="healthy",
            asr_service="up",
            tts_service="up",
            nlp_service="up",
            database="up",
            cache="up"
        )
    
    @staticmethod
    def get_user_stats_overview() -> UserStatsOverview:
        """Get overall user statistics"""
        total_users = local_db.count_users(active_only=False)
        active_today = local_db.count_active_users_today()
        new_users_this_month = local_db.count_new_users_this_month()

        return UserStatsOverview(
            total_users=total_users,
            active_users_today=active_today,
            new_users_this_month=new_users_this_month,
            churn_rate=0.05,  # 5% churn rate example
            avg_session_duration=3600.0  # 1 hour example
        )
    
    @staticmethod
    def export_report(user_email: str, report_type: str, date_from: datetime, date_to: datetime) -> dict:
        """Export report"""
        report = {
            "user_email": user_email,
            "report_type": report_type,
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat()
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
        if report_type == "usage":
            usage = DashboardService.get_api_usage(user_email)
            report["data"] = [u.dict() for u in usage]
        elif report_type == "activity":
            activities = DashboardService.get_user_activities(user_email)
            report["data"] = [a.dict() for a in activities]
        elif report_type == "performance":
            metrics = DashboardService.get_system_metrics()
            report["data"] = metrics.dict()
        
        return report
