from datetime import UTC, datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user
from middleware.security import SanitizedModel, limiter
from models.user import User
from services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    invalidate_refresh_token,
    is_refresh_token_revoked,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(SanitizedModel):
    email: EmailStr
    password: str


class RefreshRequest(SanitizedModel):
    refresh_token: str


class LogoutRequest(SanitizedModel):
    refresh_token: str


class UserInfo(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserInfo


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db_session)) -> LoginResponse:
    user = await authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo(id=str(user.id), name=user.name, email=user.email, role=user.role.value),
    )


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh_token(request: Request, payload: RefreshRequest) -> dict[str, str]:
    try:
        token_payload = decode_token(payload.refresh_token)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    if await is_refresh_token_revoked(token_payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    exp = token_payload.get("exp")
    if isinstance(exp, int) and datetime.fromtimestamp(exp, tz=UTC) < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token subject")

    return {"access_token": create_access_token(user_id)}


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, payload: LogoutRequest) -> dict[str, str]:
    await invalidate_refresh_token(payload.refresh_token)
    return {"status": "success"}


@router.get("/me", response_model=UserInfo)
async def me(current_user: User = Depends(get_current_user)) -> UserInfo:
    return UserInfo(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        role=current_user.role.value,
    )
