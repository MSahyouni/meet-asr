"""
users / schema.py
User management schemas
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    """User profile"""
    id: str
    email: str
    full_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    is_active: bool = True
    created_at: str


class UpdateProfileRequest(BaseModel):
    """Update profile request"""
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


class UserListResponse(BaseModel):
    """User list response"""
    id: str
    email: str
    full_name: str
    created_at: str


class UserStatsResponse(BaseModel):
    """User statistics"""
    total_users: int
    active_users: int
    inactive_users: int
