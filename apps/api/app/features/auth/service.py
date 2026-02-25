"""
auth / service.py
Authentication business logic
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import secrets


class AuthService:
    """Authentication service"""
    
    # In-memory store (replace with database in production)
    users_db: Dict[str, Any] = {}
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password"""
        return AuthService.hash_password(password) == hashed
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate random token"""
        return secrets.token_urlsafe(length)
    
    @classmethod
    def register_user(cls, email: str, password: str, full_name: str) -> Dict[str, Any]:
        """Register new user"""
        if email in cls.users_db:
            raise ValueError(f"User {email} already exists")
        
        user = {
            "id": cls.generate_token(16),
            "email": email,
            "full_name": full_name,
            "password_hash": cls.hash_password(password),
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
        }
        
        cls.users_db[email] = user
        return {k: v for k, v in user.items() if k != "password_hash"}
    
    @classmethod
    def login(cls, email: str, password: str) -> Dict[str, Any]:
        """Login user and return token"""
        if email not in cls.users_db:
            raise ValueError(f"Invalid credentials")
        
        user = cls.users_db[email]
        
        if not cls.verify_password(password, user["password_hash"]):
            raise ValueError(f"Invalid credentials")
        
        token = cls.generate_token()
        
        return {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "access_token": token,
            "token_type": "bearer",
        }
    
    @classmethod
    def get_user(cls, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        if email not in cls.users_db:
            return None
        
        user = cls.users_db[email]
        return {k: v for k, v in user.items() if k != "password_hash"}
    
    @classmethod
    def change_password(cls, email: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        if email not in cls.users_db:
            raise ValueError("User not found")
        
        user = cls.users_db[email]
        
        if not cls.verify_password(old_password, user["password_hash"]):
            raise ValueError("Invalid current password")
        
        user["password_hash"] = cls.hash_password(new_password)
        return True
