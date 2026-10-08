import uuid
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    blacklist_token, create_access_token, get_current_user, hash_password,
    to_public, verify_password,
)
from db import get_db
from models import User, ManagedUser
from schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic, UserLoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _gen_webhook_secret() -> str:
    return "tv_" + token_urlsafe(24)


@router.post("/register")
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(User).where(User.email == body.email))
    exists = result.scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    
    user = User(
        id=uuid.uuid4().hex,
        email=body.email, 
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    
    token = create_access_token(user.id, user.email)
    return {"access_token": token, "user": to_public(user)}


@router.post("/login")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    token = create_access_token(user.id, user.email)
    return {"access_token": token, "user": to_public(user)}


@router.get("/me")
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    if user.role == "managed_user":
        return {
            "id": user.id, "email": user.email, "name": getattr(user, "name", ""),
            "role": "managed_user", "tv_webhook_secret": "",
        }
    return to_public(user)


@router.post("/user-login")
async def user_login(body: UserLoginRequest, session: AsyncSession = Depends(get_db)):
    """Login for managed users (sub-accounts) using phone + password."""
    result = await session.execute(select(ManagedUser).where(ManagedUser.phone == body.phone))
    mu = result.scalar_one_or_none()
    
    if not mu:
        result2 = await session.execute(select(ManagedUser).where(ManagedUser.email == body.phone))
        mu = result2.scalar_one_or_none()

    if not mu:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if not mu.password_hash or not verify_password(body.password, mu.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
    if mu.is_active is False or getattr(mu, "account_status", "active") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
        
    token = create_access_token(mu.id, mu.email, role="managed_user")
    user_public = {
        "id": mu.id, "email": mu.email, "name": mu.name,
        "role": "managed_user", "tv_webhook_secret": "",
    }
    return {"access_token": token, "user": user_public}


@router.post("/webhook-secret/rotate")
async def rotate_webhook_secret(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return to_public(user)


@router.post("/logout")
async def logout(token: str = Depends(_bearer), session: AsyncSession = Depends(get_db)):
    """Server-side logout: blacklists the bearer so subsequent requests with it 401."""
    if token:
        await blacklist_token(token, session)
    return {"ok": True}
