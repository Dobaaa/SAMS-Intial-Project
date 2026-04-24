import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRES_HOURS = 8
REFRESH_TOKEN_EXPIRES_DAYS = 30
REVOKED_REFRESH_KEY_PREFIX = "sams:auth:revoked_refresh:"

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _revoked_refresh_key(jti: str) -> str:
    return f"{REVOKED_REFRESH_KEY_PREFIX}{jti}"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject: str) -> str:
    return _create_token(subject, "access", timedelta(hours=ACCESS_TOKEN_EXPIRES_HOURS))


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, "refresh", timedelta(days=REFRESH_TOKEN_EXPIRES_DAYS))


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])


async def invalidate_refresh_token(token: str) -> None:
    try:
        payload = decode_token(token)
    except JWTError:
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not isinstance(jti, str):
        return

    # Store the revocation marker in Redis until the token would have
    # expired on its own; after that the jti can never be reused anyway.
    if isinstance(exp, int):
        ttl = exp - int(datetime.now(UTC).timestamp())
    else:
        ttl = 0
    if ttl <= 0:
        return
    await redis_client.setex(_revoked_refresh_key(jti), ttl, "1")


async def is_refresh_token_revoked(payload: dict) -> bool:
    jti = payload.get("jti")
    if not isinstance(jti, str):
        return False
    return bool(await redis_client.exists(_revoked_refresh_key(jti)))


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return user
