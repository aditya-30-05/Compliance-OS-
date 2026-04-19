"""
Role-Based Access Control (RBAC) guard.
Use as a FastAPI dependency to restrict routes by role.
"""

from fastapi import Depends, HTTPException, status
from backend.auth.dependencies import get_current_user
from backend.models.user import User, UserRole


def require_roles(*allowed_roles: UserRole):
    """
    Factory that returns a dependency checking user role.
    Usage: Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN))
    """

    async def _check_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[r.value for r in allowed_roles]}",
            )
        return user

    return _check_role
