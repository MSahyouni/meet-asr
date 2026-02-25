"""
auth / router.py
Authentication endpoints
"""

from fastapi import APIRouter, HTTPException, status
from .schema import (
    LoginRequest, RegisterRequest, TokenResponse,
    UserTokenResponse, ChangePasswordRequest
)
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
        return UserTokenResponse(**result)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.get("/me")
async def get_current_user(email: str):
    """
    Get current user info
    
    - **email**: User email (from token in production)
    """
    user = AuthService.get_user(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.post("/change-password")
async def change_password(email: str, req: ChangePasswordRequest):
    """
    Change user password
    
    - **email**: User email
    - **old_password**: Current password
    - **new_password**: New password
    """
    try:
        AuthService.change_password(email, req.old_password, req.new_password)
        return {"status": "success", "message": "Password changed"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/logout")
async def logout(email: str):
    """
    Logout user (invalidate token)
    
    - **email**: User email
    """
    return {"status": "success", "message": "Logged out"}
