"""
users / service.py
User management business logic
"""

from typing import Optional, Dict, List, Any

from app.infrastructure.database import local_db


class UserService:
    """User management service"""
    
    @classmethod
    def update_profile(cls, email: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        updated = local_db.update_user_profile(email, profile_data)
        if not updated:
            raise ValueError("User not found")
        return updated
    
    @classmethod
    def get_user_profile(cls, email: str) -> Optional[Dict[str, Any]]:
        """Get user profile"""
        return local_db.get_user(email, include_password=False)
    
    @classmethod
    def list_users(cls, skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """List all users with pagination"""
        return local_db.list_users(skip, limit)
    
    @classmethod
    def get_user_count(cls) -> int:
        """Get total user count"""
        return local_db.count_users(active_only=False)
    
    @classmethod
    def get_active_count(cls) -> int:
        """Get active user count"""
        return local_db.count_users(active_only=True)
    
    @classmethod
    def delete_user(cls, email: str) -> bool:
        """Delete user (soft delete - set inactive)"""
        if not local_db.get_user(email, include_password=False):
            raise ValueError("User not found")

        return local_db.set_user_active(email, False)
