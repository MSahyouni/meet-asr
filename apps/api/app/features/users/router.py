"""
users / router.py
User management endpoints
"""

from fastapi import APIRouter, HTTPException, status, Query
from .schema import UserProfile, UpdateProfileRequest, UserListResponse, UserStatsResponse
from .service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile/{email}", response_model=UserProfile)
async def get_profile(email: str):
    """
    Get user profile
    
    - **email**: User email
    """
    user = UserService.get_user_profile(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserProfile(**user)


@router.put("/profile/{email}", response_model=UserProfile)
async def update_profile(email: str, req: UpdateProfileRequest):
    """
    Update user profile
    
    - **email**: User email
    - **full_name**: New full name (optional)
    - **bio**: User bio (optional)
    - **avatar_url**: Avatar URL (optional)
    """
    try:
        updated_user = UserService.update_profile(email, req.dict(exclude_unset=True))
        return UserProfile(**updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/", response_model=list[UserListResponse])
async def list_users(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)):
    """
    List all users with pagination
    
    - **skip**: Number of users to skip
    - **limit**: Number of users to return (max 100)
    """
    users = UserService.list_users(skip, limit)
    return [UserListResponse(**user) for user in users]


@router.get("/stats/overview", response_model=UserStatsResponse)
async def get_user_stats():
    """Get user statistics"""
    total = UserService.get_user_count()
    active = UserService.get_active_count()
    
    return UserStatsResponse(
        total_users=total,
        active_users=active,
        inactive_users=total - active
    )


@router.delete("/{email}")
async def delete_user(email: str):
    """
    Delete user (soft delete - mark as inactive)
    
    - **email**: User email
    """
    try:
        UserService.delete_user(email)
        return {"status": "success", "message": "User deleted"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
