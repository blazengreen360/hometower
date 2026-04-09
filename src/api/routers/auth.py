"""Auth router — login and logout endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from src.services.auth_service import authenticate
from src.utils.db import get_session

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Authenticate with email + password and receive a JWT.

    This endpoint is excluded from JWT middleware — no token required.
    Returns 401 on invalid credentials.
    """
    token = authenticate(data.email, data.password, session)
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/auth/logout")
async def logout() -> dict[str, str]:
    """Stateless logout — instructs the client to clear the stored JWT.

    Requires a valid Bearer token (enforced by AuthMiddleware).
    The server does not maintain a token blocklist in v1.
    """
    return {"detail": "Logged out"}
