"""
auth / router.py
Authentication endpoints
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status, Header
from .schema import (
    LoginRequest, RegisterRequest, TokenResponse,
    UserTokenResponse, ChangePasswordRequest
)
from .service import AuthService
from .security import decode_access_token, extract_bearer_token
from app.features.dashboard.service import DashboardService
from app.features.dashboard.schema import ActivityType

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _resolve_email(email: Optional[str], authorization: Optional[str]) -> str:
    if email:
        return email
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing email or bearer token",
        )
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return str(payload["sub"])


@router.post("/register", response_model=dict)
async def register(req: RegisterRequest):
    """
    Register new user
    
    - **email**: User email
    - **password**: User password
    - **full_name**: Full name
    """
    try:
        user = AuthService.register_user(req.email, req.password, req.full_name)
        try:
            DashboardService.record_activity(
                req.email,
                ActivityType.LOGIN,
                "user registered",
                {"event": "register"},
            )
        except Exception:
            pass
        return {
            "status": "success",
            "message": "User registered successfully",
            "user": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=UserTokenResponse)
async def login(req: LoginRequest):
    """
    Login user and get access token
    
    - **email**: User email
    - **password**: User password
    """
    try:
        result = AuthService.login(req.email, req.password)
        try:
            DashboardService.record_activity(
                req.email,
                ActivityType.LOGIN,
                "user login",
                {"event": "login"},
            )
        except Exception:
            pass
        return UserTokenResponse(**result)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.get("/me")
async def get_current_user(email: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """
    Get current user info
    
    - **email**: User email (from token in production)
    """
    resolved_email = _resolve_email(email, authorization)
    user = AuthService.get_user(resolved_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, email: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """
    Change user password
    
    - **email**: User email
    - **old_password**: Current password
    - **new_password**: New password
    """
    try:
        resolved_email = _resolve_email(email, authorization)
        AuthService.change_password(resolved_email, req.old_password, req.new_password)
        return {"status": "success", "message": "Password changed"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/logout")
async def logout(email: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """
    Logout user (invalidate token)
    
    - **email**: User email
    """
    resolved_email = _resolve_email(email, authorization)
    try:
        DashboardService.record_activity(
            resolved_email,
            ActivityType.LOGOUT,
            "user logout",
            {"event": "logout"},
        )
    except Exception:
        pass
    return {"status": "success", "message": "Logged out"}
