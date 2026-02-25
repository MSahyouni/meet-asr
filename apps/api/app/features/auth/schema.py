"""
auth / schema.py
Authentication request/response schemas
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Login request"""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request"""
    email: EmailStr
    password: str
    full_name: str


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserTokenResponse(BaseModel):
    """User with token response"""
    id: str
    email: str
    full_name: str
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    old_password: str
    new_password: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str
