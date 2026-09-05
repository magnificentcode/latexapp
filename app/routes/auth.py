# app/routes/auth.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.models.user import UserCredentials, UserOut

logger = logging.getLogger("latexapp.auth")
router = APIRouter(prefix="/api", tags=["auth"])


def _set_auth_cookie(response: Response, request: Request, token: str, max_age: int) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        # TLS terminates at Railway's edge (request.url.scheme is plain
        # http there), so the real scheme comes from the forwarded-proto
        # header. False locally, where there's no proxy in front.
        secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https",
        max_age=max_age,
    )


@router.post("/signup", status_code=201, response_model=UserOut)
async def signup(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        credentials = UserCredentials(**await request.json())
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user = User(email=credentials.email, password_hash=hash_password(credentials.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    await db.refresh(user)

    token, max_age = create_access_token(str(user.id), user.email)
    _set_auth_cookie(response, request, token, max_age)
    logger.info("New signup: %s", user.email)
    return UserOut(id=user.id, email=user.email)


@router.post("/login", response_model=UserOut)
async def login(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        credentials = UserCredentials(**await request.json())
    except (ValidationError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token, max_age = create_access_token(str(user.id), user.email)
    _set_auth_cookie(response, request, token, max_age)
    return UserOut(id=user.id, email=user.email)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie("access_token")


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return UserOut(id=current_user.id, email=current_user.email)
