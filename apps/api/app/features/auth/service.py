"""
auth / service.py
Authentication business logic
"""

from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import secrets

from app.infrastructure.database import local_db
from .security import create_access_token, token_ttl_seconds


class AuthService:
    """Authentication service"""
    
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
        existing = local_db.get_user(email, include_password=True)
        if existing:
            raise ValueError(f"User {email} already exists")

        user = {
            "id": cls.generate_token(16),
            "email": email,
            "full_name": full_name,
            "password_hash": cls.hash_password(password),
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
            "bio": "",
            "avatar_url": "",
        }

        local_db.create_user(email, user)
        return {k: v for k, v in user.items() if k != "password_hash"}
    
    @classmethod
    def login(cls, email: str, password: str) -> Dict[str, Any]:
        """Login user and return token"""
        user = local_db.get_user(email, include_password=True)
        if not user:
            raise ValueError(f"Invalid credentials")

        if not cls.verify_password(password, user["password_hash"]):
            raise ValueError(f"Invalid credentials")

        token = create_access_token(
            email=user["email"],
            user_id=user["id"],
            full_name=user["full_name"],
            token_version=int(user.get("token_version", 0) or 0),
        )

        return {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "access_token": token,
            "token_type": "bearer",
            "expires_in": token_ttl_seconds(),
        }
    
    @classmethod
    def get_user(cls, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        return local_db.get_user(email, include_password=False)
    
    @classmethod
    def change_password(cls, email: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        user = local_db.get_user(email, include_password=True)
        if not user:
            raise ValueError("User not found")

        if not cls.verify_password(old_password, user["password_hash"]):
            raise ValueError("Invalid current password")

        ok = local_db.update_password(email, cls.hash_password(new_password))
        if ok:
            local_db.rotate_token_version(email)
        return ok
