"""
auth / service.py
Authentication business logic
"""

from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import secrets

import bcrypt

from app.infrastructure.database import local_db
from .security import create_access_token, token_ttl_seconds

_BCRYPT_PREFIX = ("$2a$", "$2b$", "$2y$")


class AuthService:
    """Authentication service"""

    @staticmethod
    def _is_bcrypt_hash(hashed: str) -> bool:
        value = (hashed or "").strip()
        return any(value.startswith(prefix) for prefix in _BCRYPT_PREFIX)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
        return digest.decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password (bcrypt; legacy SHA-256 hex supported for migration)."""
        stored = (hashed or "").strip()
        if not stored:
            return False
        if AuthService._is_bcrypt_hash(stored):
            try:
                return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
            except ValueError:
                return False
        # Legacy SHA-256 (pre-bcrypt accounts)
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored

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
            raise ValueError("Invalid credentials")

        stored_hash = user["password_hash"]
        if not cls.verify_password(password, stored_hash):
            raise ValueError("Invalid credentials")

        if not cls._is_bcrypt_hash(stored_hash):
            local_db.update_password(email, cls.hash_password(password))

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
