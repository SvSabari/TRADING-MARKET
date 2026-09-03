from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from auth import (
    blacklist_token, create_access_token, get_current_user, hash_password,
    to_public, verify_password,
)
from db import db
from models import LoginRequest, RegisterRequest, TokenResponse, User, UserPublic, ManagedUser, UserLoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _gen_webhook_secret() -> str:
    return "tv_" + token_urlsafe(24)


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest):
    exists = await db.users.find_one({"email": body.email})
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=body.email, name=body.name,
        password_hash=hash_password(body.password),
        tv_webhook_secret=_gen_webhook_secret(),
    )
    await db.users.insert_one(user.to_mongo())
    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=to_public(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    doc = await db.users.find_one({"email": body.email})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user = User.from_mongo(doc)
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # backfill missing webhook secret for legacy accounts
    if not user.tv_webhook_secret:
        user.tv_webhook_secret = _gen_webhook_secret()
        await db.users.update_one({"_id": user.id}, {"$set": {"tv_webhook_secret": user.tv_webhook_secret}})
    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=to_public(user))


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    if user.role == "managed_user":
        # Managed users — return minimal public info
        return UserPublic(
            id=user.id, email=user.email, name=user.name,
            role="managed_user", tv_webhook_secret="", created_at=user.created_at,
        )
    if not user.tv_webhook_secret:
        user.tv_webhook_secret = _gen_webhook_secret()
        await db.users.update_one({"_id": user.id}, {"$set": {"tv_webhook_secret": user.tv_webhook_secret}})
    return to_public(user)


@router.post("/user-login", response_model=TokenResponse)
async def user_login(body: UserLoginRequest):
    """Login for managed users (sub-accounts) using phone + password."""
    doc = await db.managed_users.find_one({"phone": body.phone})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    mu = ManagedUser.from_mongo(doc)
    if not verify_password(body.password, mu.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if mu.account_status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    token = create_access_token(mu.id, f"{mu.phone}@user.com", role="managed_user")
    user_public = UserPublic(
        id=mu.id, email=f"{mu.phone}@user.com", name=mu.name,
        role="managed_user", tv_webhook_secret="", created_at=mu.created_at,
    )
    return TokenResponse(access_token=token, user=user_public)


@router.post("/webhook-secret/rotate", response_model=UserPublic)
async def rotate_webhook_secret(user: User = Depends(get_current_user)):
    new_secret = _gen_webhook_secret()
    await db.users.update_one({"_id": user.id}, {"$set": {"tv_webhook_secret": new_secret}})
    user.tv_webhook_secret = new_secret
    return to_public(user)


@router.post("/logout")
async def logout(token: str = Depends(_bearer)):
    """Server-side logout: blacklists the bearer so subsequent requests with it 401."""
    if token:
        await blacklist_token(token)
    return {"ok": True}
