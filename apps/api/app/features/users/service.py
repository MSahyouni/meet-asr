"""
users / service.py
User management business logic
"""

from typing import Optional, Dict, List, Any


class UserService:
    """User management service"""
    
    # Reference to auth service users db
    users_db: Dict[str, Any] = {}
    
    @classmethod
    def update_profile(cls, email: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        if email not in cls.users_db:
            raise ValueError("User not found")
        
        user = cls.users_db[email]
        
        # Update allowed fields
        if "full_name" in profile_data and profile_data["full_name"]:
            user["full_name"] = profile_data["full_name"]
        
        if "bio" in profile_data:
            user["bio"] = profile_data.get("bio", "")
        
        if "avatar_url" in profile_data:
            user["avatar_url"] = profile_data.get("avatar_url", "")
        
        return {k: v for k, v in user.items() if k != "password_hash"}
    
    @classmethod
    def get_user_profile(cls, email: str) -> Optional[Dict[str, Any]]:
        """Get user profile"""
        if email not in cls.users_db:
            return None
        
        user = cls.users_db[email]
        return {k: v for k, v in user.items() if k != "password_hash"}
    
    @classmethod
    def list_users(cls, skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """List all users with pagination"""
        users = list(cls.users_db.values())
        return [
            {k: v for k, v in user.items() if k != "password_hash"}
            for user in users[skip:skip + limit]
        ]
    
    @classmethod
    def get_user_count(cls) -> int:
        """Get total user count"""
        return len(cls.users_db)
    
    @classmethod
    def get_active_count(cls) -> int:
        """Get active user count"""
        return sum(1 for user in cls.users_db.values() if user.get("is_active", True))
    
    @classmethod
    def delete_user(cls, email: str) -> bool:
        """Delete user (soft delete - set inactive)"""
        if email not in cls.users_db:
            raise ValueError("User not found")
        
        cls.users_db[email]["is_active"] = False
        return True
