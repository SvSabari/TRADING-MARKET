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
from models import User, UserPublic, ManagedUser
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
    user_doc = await db.users.find_one({"email": demo_email})
    if not user_doc:
        user = User(
            email=demo_email,
            name="Demo Trader",
            password_hash=hash_password("demo123"),
            tv_webhook_secret=f"tv_{uuid.uuid4().hex}",
        )
        await db.users.insert_one(user.to_mongo())
        user_id = user.id
        
        # Ensure demo managed user exists for testing User Login only on fresh DB
        from models import ManagedUserBroker
        demo_mu = ManagedUser(
            trader_id=user_id,
            name="Demo Sub User",
            phone="9876543210",
            password_hash=hash_password("user123"),
            brokers=[
                ManagedUserBroker(
                    broker="alice_blue",
                    api_key="DEMO_API_KEY_123",
                    api_secret="DEMO_API_SECRET_123",
                    account_number="DEMO_ACC_1001",
                    account_password="demo_acc_pass",
                    session_generated=False,
                ),
                ManagedUserBroker(
                    broker="zerodha",
                    api_key="DEMO_KITE_KEY",
                    api_secret="DEMO_KITE_SECRET",
                    account_number="ZK1234",
                    account_password="demo_zk_pass",
                    session_generated=False,
                )
            ],
            place_order=True,
            profit_pct=5.0,
            account_status="active",
        )
        await db.managed_users.insert_one(demo_mu.to_mongo())
    else:
        user_id = str(user_doc["_id"])


def create_access_token(user_id: str, email: str, role: str = "trader") -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id, "email": email, "role": role,
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
    role = payload.get("role", "trader")
    if role == "managed_user":
        doc = await db.managed_users.find_one({"_id": user_id})
        if not doc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        mu = ManagedUser.from_mongo(doc)
        # Return a User-compatible stub so all existing guards work
        return User(
            _id=mu.id, email=f"{mu.phone}@user.com",
            name=mu.name, password_hash=mu.password_hash, role="managed_user",
        )
    doc = await db.users.find_one({"_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return User.from_mongo(doc)


async def get_current_trader(user: User = Depends(get_current_user)) -> User:
    """Dependency — only allows traders; 403 for managed users."""
    if user.role != "trader":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trader access required")
    return user


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
