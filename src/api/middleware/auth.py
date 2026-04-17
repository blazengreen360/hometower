"""JWT authentication middleware.

Token extraction order:
1. Cookie ``ht_access_token`` (set by login endpoint)
2. Fallback to ``Authorization: Bearer`` header (for programmatic API clients)

After decoding, the token version is verified against the value stored in the
database (Decision B from RFC-SEC-1.1-4.4 — middleware owns revocation).
"""
import uuid as _uuid

from jose import JWTError
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.models.user import User
from src.utils.auth import decode_jwt
from src.utils.db import engine

# /api/ paths that bypass JWT authentication entirely
EXCLUDED_API_PATHS: frozenset[str] = frozenset(
    {
        "/api/auth/login",
        "/api/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Only /api/ paths require JWT; NiceGUI pages and static assets pass through
        if (
            not path.startswith("/api/")
            or path in EXCLUDED_API_PATHS
            or path.startswith("/_nicegui")
        ):
            return await call_next(request)

        # --- token extraction: cookie first, Bearer header fallback ---
        token = request.cookies.get("ht_access_token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            token = auth_header.removeprefix("Bearer ")

        try:
            payload = decode_jwt(token)
        except JWTError as exc:
            detail = "Token expired" if "expired" in str(exc).lower() else "Invalid token"
            return JSONResponse({"detail": detail}, status_code=401)

        # --- verify token version against DB (revocation check) ---
        try:
            user_id = _uuid.UUID(str(payload["sub"]))
            token_version = int(payload["version"])
        except (KeyError, ValueError, TypeError):
            return JSONResponse({"detail": "Invalid token"}, status_code=401)
        with Session(engine) as db_session:
            user = db_session.get(User, user_id)
        if user is None or user.token_version != token_version:
            return JSONResponse({"detail": "Token revoked"}, status_code=401)
        if not user.is_active:
            return JSONResponse({"detail": "Account disabled"}, status_code=401)

        request.state.user_id = str(user.id)
        request.state.role = user.role.value
        return await call_next(request)
