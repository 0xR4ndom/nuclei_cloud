from functools import wraps
from fastapi import HTTPException, status
from app.models.user import User, UserRole


def require_role(*roles: UserRole):
    """Dependency factory: ensures current user has one of the specified roles."""
    def checker(current_user: User):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return checker


def require_admin(current_user: User) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def can_write(current_user: User) -> User:
    if current_user.role == UserRole.VIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only access",
        )
    return current_user


def owns_or_admin(resource_owner_id: str, current_user: User) -> None:
    """Raise 403 if user doesn't own the resource and isn't admin."""
    if current_user.role != UserRole.ADMIN and resource_owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you don't own this resource",
        )
