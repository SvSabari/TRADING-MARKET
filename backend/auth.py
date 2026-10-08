"""JWT authentication helpers."""
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models import User, ManagedUser

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))  # 1 day

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


async def ensure_demo_user(session: AsyncSession) -> None:
    demo_email = "demo@trader.io"
    result = await session.execute(select(User).where(User.email == demo_email))
    user_doc = result.scalar_one_or_none()
    
    if not user_doc:
        user = User(
            id=uuid.uuid4().hex,
            email=demo_email,
            password_hash=hash_password("demo123"),
            role="trader",
        )
        session.add(user)
        await session.commit()
        
        # Ensure demo managed user exists for testing
        demo_mu = ManagedUser(
            id=uuid.uuid4().hex,
            trader_id=user.id,
            name="Demo Sub User",
            email="9876543210@user.com",
            brokers=[],
            created_at=datetime.utcnow(),
        )
        session.add(demo_mu)
        await session.commit()


def create_access_token(user_id: str, email: str, role: str = "trader") -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id, "email": email, "role": role,
        "iat": int(now.timestamp()),
        "jti": uuid.uuid4().hex,
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme), session: AsyncSession = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    payload = decode_token(token)
    user_id = payload.get("sub")
    role = payload.get("role", "trader")
    
    if role == "managed_user":
        doc = await session.execute(select(ManagedUser).where(ManagedUser.id == user_id))
        mu = doc.scalar_one_or_none()
        if not mu:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return User(
            id=mu.id, email=mu.email,
            password_hash="", role="managed_user",
        )
        
    doc = await session.execute(select(User).where(User.id == user_id))
    user = doc.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_trader(user: User = Depends(get_current_user)) -> User:
    """Dependency - only allows traders; 403 for managed users."""
    if user.role != "trader":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trader access required")
    return user


async def blacklist_token(token: str, session: AsyncSession = Depends(get_db)) -> None:
    pass


def to_public(user: User):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
    }
