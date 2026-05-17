import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user, require_role
from models.master import InputTypeEnum, MasterField, MasterTemplate, TemplateTypeEnum
from models.user import RoleEnum, User
from services.audit_service import record_audit
from services.master_service import (
    create_template_version,
    get_template_or_404,
    list_fields_by_template,
    list_templates_grouped,
)

router = APIRouter(prefix="/masters", tags=["masters"])


class MasterTemplateCreate(BaseModel):
    type: TemplateTypeEnum
    version_number: str
    version_date: date
    content_html: str
    notes: str | None = None


class MasterFieldPayload(BaseModel):
    template_id: uuid.UUID
    field_id: str
    clause_number: str
    field_label: str
    input_type: InputTypeEnum
    default_value: str | None = None
    is_required: bool = False
    auto_source_field_id: str | None = None
    appendix_row_label: str | None = None
    appendix_clause_ref: str | None = None
    show_in_appendix: bool = True
    sort_order: int = 0


class MasterFieldReorderItem(BaseModel):
    id: uuid.UUID
    sort_order: int


class MasterFieldReorderPayload(BaseModel):
    items: list[MasterFieldReorderItem]


def _template_to_dict(template: MasterTemplate) -> dict:
    return {
        "id": str(template.id),
        "type": template.type.value,
        "version_number": template.version_number,
        "version_date": str(template.version_date),
        "is_active": template.is_active,
        "notes": template.notes,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }


def _field_to_dict(field: MasterField) -> dict:
    return {
        "id": str(field.id),
        "template_id": str(field.template_id),
        "field_id": field.field_id,
        "clause_number": field.clause_number,
        "field_label": field.field_label,
        "input_type": field.input_type.value,
        "default_value": field.default_value,
        "is_required": field.is_required,
        "auto_source_field_id": field.auto_source_field_id,
        "appendix_row_label": field.appendix_row_label,
        "appendix_clause_ref": field.appendix_clause_ref,
        "show_in_appendix": field.show_in_appendix,
        "sort_order": field.sort_order,
    }


@router.get("/", dependencies=[Depends(get_current_user)])
async def list_templates(db: AsyncSession = Depends(get_db_session)) -> dict:
    grouped = await list_templates_grouped(db)
    return {k: [_template_to_dict(t) for t in v] for k, v in grouped.items()}


@router.get("/{template_id}", dependencies=[Depends(require_role(RoleEnum.admin))])
async def get_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)) -> dict:
    template = await get_template_or_404(db, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    fields = await list_fields_by_template(db, template_id)
    return {"template": _template_to_dict(template), "fields": [_field_to_dict(f) for f in fields]}


@router.post("/", dependencies=[Depends(require_role(RoleEnum.admin))])
async def create_template(
    payload: MasterTemplateCreate,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    template = await create_template_version(
        db=db,
        actor=current_user,
        template_type=payload.type,
        version_number=payload.version_number,
        version_date=payload.version_date,
        content_html=payload.content_html,
        notes=payload.notes,
        ip_address=request.client.host if request.client else None,
    )
    return _template_to_dict(template)


@router.get("/fields/{template_id}", dependencies=[Depends(get_current_user)])
async def get_fields(template_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)) -> list[dict]:
    fields = await list_fields_by_template(db, template_id)
    return [_field_to_dict(field) for field in fields]


@router.post("/fields/", dependencies=[Depends(require_role(RoleEnum.admin))])
async def add_field(
    payload: MasterFieldPayload,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    field = MasterField(**payload.model_dump())
    db.add(field)
    await db.flush()
    await record_audit(
        db,
        actor_id=current_user.id,
        action="master_field_created",
        entity_type="master_field",
        entity_id=field.id,
        new_value=_field_to_dict(field),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(field)
    return _field_to_dict(field)


@router.put("/fields/reorder", dependencies=[Depends(require_role(RoleEnum.admin))])
async def reorder_fields(
    payload: MasterFieldReorderPayload,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    # Declared before /fields/{field_id} so FastAPI's UUID validation on
    # field_id doesn't reject the literal path "reorder" with a 422.
    for item in payload.items:
        result = await db.execute(select(MasterField).where(MasterField.id == item.id))
        field = result.scalar_one_or_none()
        if field:
            field.sort_order = item.sort_order
    await record_audit(
        db,
        actor_id=current_user.id,
        action="master_fields_reordered",
        entity_type="master_field",
        new_value={"items": [i.model_dump(mode="json") for i in payload.items]},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"status": "success"}


@router.put("/fields/{field_id}", dependencies=[Depends(require_role(RoleEnum.admin))])
async def update_field(
    field_id: uuid.UUID,
    payload: MasterFieldPayload,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    result = await db.execute(select(MasterField).where(MasterField.id == field_id))
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    old_value = _field_to_dict(field)
    for key, value in payload.model_dump().items():
        setattr(field, key, value)
    await record_audit(
        db,
        actor_id=current_user.id,
        action="master_field_updated",
        entity_type="master_field",
        entity_id=field.id,
        old_value=old_value,
        new_value=_field_to_dict(field),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(field)
    return _field_to_dict(field)


@router.delete("/fields/{field_id}", dependencies=[Depends(require_role(RoleEnum.admin))])
async def delete_field(
    field_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    result = await db.execute(select(MasterField).where(MasterField.id == field_id))
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    old_value = _field_to_dict(field)
    await db.delete(field)
    await record_audit(
        db,
        actor_id=current_user.id,
        action="master_field_deleted",
        entity_type="master_field",
        entity_id=field_id,
        old_value=old_value,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"status": "deleted"}
