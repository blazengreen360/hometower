"""JWT authentication middleware.

Decodes the Bearer token on every request that is not on an excluded path.
Attaches user_id and role to request.state for downstream handlers.
"""
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.utils.auth import decode_jwt

# /api/ paths that bypass JWT authentication entirely
EXCLUDED_API_PATHS: frozenset[str] = frozenset(
    {
        "/api/auth/login",
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

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        token = auth_header.removeprefix("Bearer ")
        try:
            payload = decode_jwt(token)
        except JWTError as exc:
            detail = "Token expired" if "expired" in str(exc).lower() else "Invalid token"
            return JSONResponse({"detail": detail}, status_code=401)

        request.state.user_id = payload["sub"]
        request.state.role = payload["role"]
        return await call_next(request)
