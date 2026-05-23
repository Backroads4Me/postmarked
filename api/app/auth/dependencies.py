from fastapi import Depends, HTTPException, status
from app.models.enums import UserRole, ApprovalState
from app.models.user import User
from app.auth.auth_config import fastapi_users_app

current_user = fastapi_users_app.current_user()
current_active_user = fastapi_users_app.current_user(active=True)

async def current_approved_user(user: User = Depends(current_active_user)):
    if user.approval_state == ApprovalState.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been rejected",
        )
    if user.approval_state != ApprovalState.APPROVED and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval"
        )
    return user

async def current_admin_user(user: User = Depends(current_active_user)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin access required"
        )
    return user
