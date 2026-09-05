# app/core/deps.py

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import JWTError, decode_access_token
from app.db.models import User
from app.db.session import get_db


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """Resolves the authenticated user from the access_token cookie.

    Checks request.state.user first (populated opportunistically by
    AuthMiddleware for every request), falling back to decoding the cookie
    directly in case the middleware didn't run. Always 401s on failure —
    API routes never redirect (see app/middleware/auth.py).
    """
    payload = getattr(request.state, "user", None)
    if payload is None:
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = decode_access_token(token)
        except JWTError:
            raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
