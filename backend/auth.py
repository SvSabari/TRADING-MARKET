"""JWT authentication helpers."""
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from db import db
from models import User, UserPublic
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


async def ensure_demo_user() -> None:
    demo_email = "demo@trader.io"
    if await db.users.find_one({"email": demo_email}):
        return
    user = User(
        email=demo_email,
        name="Demo Trader",
        password_hash=hash_password("demo123"),
        tv_webhook_secret=f"tv_{uuid.uuid4().hex}",
    )
    await db.users.insert_one(user.to_mongo())


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id, "email": email,
        "iat": int(now.timestamp()),
        "jti": uuid.uuid4().hex,  # ensures every token is unique even within the same second
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    # check the blacklist first (rejected after logout)
    if await db.token_blacklist.find_one({"token": token}):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
    payload = decode_token(token)
    user_id = payload.get("sub")
    doc = await db.users.find_one({"_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return User.from_mongo(doc)


async def blacklist_token(token: str) -> None:
    """Insert the bearer into a TTL-backed blacklist so subsequent requests are rejected."""
    if not token:
        return
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
                             options={"verify_exp": False})
        exp = payload.get("exp")
    except Exception:
        exp = None
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc) + timedelta(days=7)
    await db.token_blacklist.update_one(
        {"token": token},
        {"$set": {"token": token, "expires_at": expires_at}},
        upsert=True,
    )


def to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id, email=user.email, name=user.name, role=user.role,
        tv_webhook_secret=user.tv_webhook_secret or "",
        created_at=user.created_at,
    )
