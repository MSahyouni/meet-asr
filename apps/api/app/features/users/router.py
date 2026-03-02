"""
users / router.py
User management endpoints
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query, Header
from app.features.auth.security import (
    resolve_email_from_authorization,
    resolve_payload_from_authorization,
    is_admin_email,
)
from .schema import UserProfile, UpdateProfileRequest, UserListResponse, UserStatsResponse
from .service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def _require_current_email(authorization: Optional[str]) -> str:
    email = resolve_email_from_authorization(authorization)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    return email


def _require_self_or_admin(target_email: str, authorization: Optional[str]) -> str:
    payload = resolve_payload_from_authorization(authorization)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    caller_email = str(payload.get("sub") or "")
    if not caller_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )
    if caller_email.lower() == target_email.lower() or is_admin_email(caller_email):
        return caller_email
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: self or admin access required",
    )


def _require_admin(authorization: Optional[str]) -> str:
    payload = resolve_payload_from_authorization(authorization)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    caller_email = str(payload.get("sub") or "")
    if not is_admin_email(caller_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return caller_email


@router.get("/me", response_model=UserProfile)
async def get_my_profile(authorization: Optional[str] = Header(None)):
    """Get current user profile from Bearer token."""
    email = _require_current_email(authorization)
    user = UserService.get_user_profile(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserProfile(**user)


@router.put("/me", response_model=UserProfile)
async def update_my_profile(req: UpdateProfileRequest, authorization: Optional[str] = Header(None)):
    """Update current user profile from Bearer token."""
    email = _require_current_email(authorization)
    try:
        updated_user = UserService.update_profile(email, req.dict(exclude_unset=True))
        return UserProfile(**updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/profile/{email}", response_model=UserProfile)
async def get_profile(email: str, authorization: Optional[str] = Header(None)):
    """
    Get user profile
    
    - **email**: User email
    """
    _require_self_or_admin(email, authorization)
    user = UserService.get_user_profile(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserProfile(**user)


@router.put("/profile/{email}", response_model=UserProfile)
async def update_profile(email: str, req: UpdateProfileRequest, authorization: Optional[str] = Header(None)):
    """
    Update user profile
    
    - **email**: User email
    - **full_name**: New full name (optional)
    - **bio**: User bio (optional)
    - **avatar_url**: Avatar URL (optional)
    """
    try:
        _require_self_or_admin(email, authorization)
        updated_user = UserService.update_profile(email, req.dict(exclude_unset=True))
        return UserProfile(**updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/", response_model=list[UserListResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    authorization: Optional[str] = Header(None),
):
    """
    List all users with pagination
    
    - **skip**: Number of users to skip
    - **limit**: Number of users to return (max 100)
    """
    _require_admin(authorization)
    users = UserService.list_users(skip, limit)
    return [UserListResponse(**user) for user in users]


@router.get("/stats/overview", response_model=UserStatsResponse)
async def get_user_stats(authorization: Optional[str] = Header(None)):
    """Get user statistics"""
    _require_admin(authorization)
    total = UserService.get_user_count()
    active = UserService.get_active_count()
    
    return UserStatsResponse(
        total_users=total,
        active_users=active,
        inactive_users=total - active
    )


@router.delete("/{email}")
async def delete_user(email: str, authorization: Optional[str] = Header(None)):
    """
    Delete user (soft delete - mark as inactive)
    
    - **email**: User email
    """
    try:
        _require_self_or_admin(email, authorization)
        UserService.delete_user(email)
        return {"status": "success", "message": "User deleted"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
