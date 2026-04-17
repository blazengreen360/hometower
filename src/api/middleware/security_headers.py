"""Security headers middleware — adds CSP and other protective HTTP headers."""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; "
            "img-src 'self' data: cdnjs.cloudflare.com *.tile.openstreetmap.org *.basemaps.cartocdn.com; "
            "connect-src 'self' ws: wss:; "
            "font-src 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
