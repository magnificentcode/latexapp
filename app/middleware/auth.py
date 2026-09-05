# app/middleware/auth.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.core.security import JWTError, decode_access_token

# Paths that get a hard redirect-on-no-auth. Every other route (JSON APIs
# included) is responsible for its own auth response — an API endpoint
# should return a 401 JSON body, not an HTML redirect, or a fetch() caller
# following the redirect ends up parsing a login page as if it were a
# successful response.
REDIRECT_GATED_PATHS = {
    "/dashboard": "/login",
    "/dashboard.html": "/login",
    "/editor": "/login",
    "/editor.html": "/login",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Opportunistically decode the session cookie and populate
        # request.state.user for any request that has one — routes read
        # this via get_current_user without needing to redirect themselves.
        token = request.cookies.get("access_token")
        if token:
            try:
                request.state.user = decode_access_token(token)
            except JWTError:
                pass  # No valid session; state.user stays unset.

        if path in REDIRECT_GATED_PATHS and not getattr(request.state, "user", None):
            return RedirectResponse(url=REDIRECT_GATED_PATHS[path], status_code=302)

        return await call_next(request)
