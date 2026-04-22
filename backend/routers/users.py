import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import require_role
from models.audit import AuditLog
from models.user import RoleEnum, User
from services.auth_service import hash_password

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: RoleEnum


class UserUpdateRequest(BaseModel):
    name: str
    email: EmailStr
    role: RoleEnum


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: RoleEnum
    is_active: bool
    last_login: str | None = None


async def _log_user_action(
    db: AsyncSession,
    actor_id: uuid.UUID,
    action: str,
    target_id: uuid.UUID,
    old_value: dict | None,
    new_value: dict | None,
    ip_address: str | None,
) -> None:
    db.add(
        AuditLog(
            user_id=actor_id,
            action=action,
            entity_type="user",
            entity_id=target_id,
            old_value_json=old_value,
            new_value_json=new_value,
            ip_address=ip_address,
        )
    )


@router.get("/", response_model=list[UserResponse], dependencies=[Depends(require_role(RoleEnum.admin))])
async def list_users(db: AsyncSession = Depends(get_db_session)) -> list[UserResponse]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        UserResponse(
            id=str(user.id),
            name=user.name,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            last_login=user.last_login.isoformat() if user.last_login else None,
        )
        for user in users
    ]


@router.post("/", response_model=UserResponse, dependencies=[Depends(require_role(RoleEnum.admin))])
async def create_user(
    payload: UserCreateRequest,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    await _log_user_action(
        db=db,
        actor_id=current_user.id,
        action="user_created",
        target_id=user.id,
        old_value=None,
        new_value={"name": user.name, "email": user.email, "role": user.role.value, "is_active": user.is_active},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.put("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_role(RoleEnum.admin))])
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_snapshot = {"name": user.name, "email": user.email, "role": user.role.value, "is_active": user.is_active}
    user.name = payload.name
    user.email = payload.email
    user.role = payload.role
    new_snapshot = {"name": user.name, "email": user.email, "role": user.role.value, "is_active": user.is_active}

    await _log_user_action(
        db=db,
        actor_id=current_user.id,
        action="user_edited",
        target_id=user.id,
        old_value=old_snapshot,
        new_value=new_snapshot,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.patch("/{user_id}/deactivate", response_model=UserResponse, dependencies=[Depends(require_role(RoleEnum.admin))])
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_snapshot = {"is_active": user.is_active}
    user.is_active = False

    await _log_user_action(
        db=db,
        actor_id=current_user.id,
        action="user_deactivated",
        target_id=user.id,
        old_value=old_snapshot,
        new_value={"is_active": user.is_active},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.patch("/{user_id}/activate", response_model=UserResponse, dependencies=[Depends(require_role(RoleEnum.admin))])
async def activate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_snapshot = {"is_active": user.is_active}
    user.is_active = True

    await _log_user_action(
        db=db,
        actor_id=current_user.id,
        action="user_activated",
        target_id=user.id,
        old_value=old_snapshot,
        new_value={"is_active": user.is_active},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
    )
