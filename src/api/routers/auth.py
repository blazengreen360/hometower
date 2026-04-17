"""Auth router — login, logout, and self-service password change endpoints."""
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session

from src.api.middleware.rate_limit import limiter
from src.api.dependencies.rbac import require_role
from src.models.types import Role
from src.services import auth_service
from src.utils.auth import decode_jwt
from src.utils.db import get_session
from src.utils.settings import settings

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    user_id: str
    role: str
    token_exp: int
    token_type: str = "cookie"
    access_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    data: LoginRequest,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Authenticate with email + password and set an HttpOnly JWT cookie.

    This endpoint is excluded from JWT middleware — no token required.
    Returns 401 on invalid credentials. Rate-limited to 5 requests per minute per IP.
    """
    token, token_exp, role = auth_service.authenticate(data.email, data.password, session)
    user_id = decode_jwt(token)["sub"]
    response = JSONResponse(
        content={
            "user_id": str(user_id),
            "role": role,
            "token_exp": token_exp,
            "token_type": "cookie",
            "access_token": token,
        }
    )
    response.set_cookie(
        key="ht_access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/api",
        max_age=settings.jwt_expire_hours * 3600,
    )
    return response


@router.post("/auth/logout", dependencies=[Depends(require_role(Role.Reader))])
def logout(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Revoke the current session server-side and clear the HttpOnly cookie.

    Requires a valid token with at least Reader role.
    Increments the user's token_version so all issued tokens are invalidated.
    """
    user_id = uuid.UUID(request.state.user_id)
    auth_service.revoke_tokens(user_id, session)
    response = JSONResponse({"detail": "Logged out"})
    response.delete_cookie(key="ht_access_token", path="/api")
    return response


@router.patch(
    "/auth/me/password",
    status_code=204,
    dependencies=[Depends(require_role(Role.Reader))],
)
def change_own_password(
    request: Request,
    data: ChangePasswordRequest,
    session: Session = Depends(get_session),
) -> None:
    """Change the authenticated user's own password.

    Requires any authenticated role.  Returns 204 No Content on success.
    Raises 401 if the current password is wrong; 422 if the new password
    fails strength rules or equals the current password.
    All existing tokens for this user are invalidated after a successful change.
    """
    user_id = uuid.UUID(request.state.user_id)
    auth_service.change_own_password(user_id, data.current_password, data.new_password, session)
