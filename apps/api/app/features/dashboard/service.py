"""
dashboard / service.py
Dashboard services
"""

from datetime import datetime, timedelta
from .schema import (
    UserActivity, SystemMetrics, DashboardStats, APIUsage,
    UsageChartData, HealthStatus, UserStatsOverview, ActivityType
)


# Temporary in-memory storage (replace with database)
user_activities = {}
api_usage_records = {}


class DashboardService:
    """Dashboard service"""
    
    @staticmethod
    def get_dashboard_stats(user_email: str) -> DashboardStats:
        """Get dashboard statistics for user"""
        activities = DashboardService.get_user_activities(user_email)
        metrics = DashboardService.get_system_metrics()
        
        # Count jobs by type
        asr_jobs = sum(1 for a in activities if a.activity_type == ActivityType.ASR)
        tts_jobs = sum(1 for a in activities if a.activity_type == ActivityType.TTS)
        nlp_jobs = sum(1 for a in activities if a.activity_type == ActivityType.NLP)
        
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
        
        if user_email not in user_activities:
            user_activities[user_email] = []
        
        user_activities[user_email].append(activity.dict())
        return activity
    
    @staticmethod
    def get_user_activities(user_email: str, limit: int = 20) -> list[UserActivity]:
        """Get user activities"""
        activities = user_activities.get(user_email, [])
        # Return most recent first
        sorted_activities = sorted(activities, key=lambda x: x["timestamp"], reverse=True)
        return [UserActivity(**act) for act in sorted_activities[:limit]]
    
    @staticmethod
    def get_system_metrics() -> SystemMetrics:
        """Get system performance metrics"""
        # Calculate totals from all activities
        total_requests = sum(len(acts) for acts in user_activities.values())
        
        asr_requests = sum(
            sum(1 for act in acts if act.get("activity_type") == ActivityType.ASR)
            for acts in user_activities.values()
        )
        tts_requests = sum(
            sum(1 for act in acts if act.get("activity_type") == ActivityType.TTS)
            for acts in user_activities.values()
        )
        nlp_requests = sum(
            sum(1 for act in acts if act.get("activity_type") == ActivityType.NLP)
            for acts in user_activities.values()
        )
        
        return SystemMetrics(
            total_requests=total_requests,
            total_users=len(user_activities),
            active_users=len(user_activities),  # Simplified
            asr_requests=asr_requests,
            tts_requests=tts_requests,
            nlp_requests=nlp_requests,
            avg_response_time=45.5,  # Example
            uptime_percentage=99.9
        )
    
    @staticmethod
    def get_api_usage(user_email: str, days: int = 30) -> list[APIUsage]:
        """Get API usage for user over period"""
        activities = user_activities.get(user_email, [])
        usage_by_date = {}
        
        # Group by date
        for activity in activities:
            date = activity["timestamp"].date()
            if date not in usage_by_date:
                usage_by_date[date] = {
                    "asr": 0,
                    "tts": 0,
                    "nlp": 0
                }
            
            if activity["activity_type"] == ActivityType.ASR:
                usage_by_date[date]["asr"] += 1
            elif activity["activity_type"] == ActivityType.TTS:
                usage_by_date[date]["tts"] += 1
            elif activity["activity_type"] == ActivityType.NLP:
                usage_by_date[date]["nlp"] += 1
        
        # Convert to APIUsage objects
        usage_list = []
        for date, counts in usage_by_date.items():
            usage_list.append(APIUsage(
                user_email=user_email,
                date=datetime.combine(date, datetime.min.time()),
                asr_calls=counts["asr"],
                tts_calls=counts["tts"],
                nlp_calls=counts["nlp"],
                total_calls=counts["asr"] + counts["tts"] + counts["nlp"]
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
        # In production, check actual service health
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
        total_users = len(user_activities)
        
        # Count active users today
        today = datetime.utcnow().date()
        active_today = 0
        for user_activities_list in user_activities.values():
            for activity in user_activities_list:
                if activity["timestamp"].date() == today:
                    active_today += 1
                    break
        
        return UserStatsOverview(
            total_users=total_users,
            active_users_today=active_today,
            new_users_this_month=max(0, total_users - 5),  # Example
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
