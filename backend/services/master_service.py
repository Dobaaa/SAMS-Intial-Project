import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.master import InputTypeEnum, MasterField, MasterTemplate, TemplateTypeEnum
from models.user import User
from services.audit_service import record_audit


async def list_templates_grouped(db: AsyncSession) -> dict[str, list[MasterTemplate]]:
    result = await db.execute(
        select(MasterTemplate).order_by(MasterTemplate.type.asc(), MasterTemplate.version_date.desc())
    )
    templates = result.scalars().all()
    grouped: dict[str, list[MasterTemplate]] = {"form": [], "conditions": [], "appendix": []}
    for template in templates:
        grouped[template.type.value].append(template)
    return grouped


async def get_template_or_404(db: AsyncSession, template_id: uuid.UUID) -> MasterTemplate | None:
    result = await db.execute(select(MasterTemplate).where(MasterTemplate.id == template_id))
    return result.scalar_one_or_none()


async def create_template_version(
    db: AsyncSession,
    actor: User,
    template_type: TemplateTypeEnum,
    version_number: str,
    version_date: date,
    content_html: str,
    notes: str | None,
    ip_address: str | None,
) -> MasterTemplate:
    previous = await db.execute(select(MasterTemplate).where(MasterTemplate.type == template_type, MasterTemplate.is_active.is_(True)))
    for old in previous.scalars().all():
        old.is_active = False

    template = MasterTemplate(
        type=template_type,
        version_number=version_number,
        version_date=version_date,
        content_html=content_html,
        notes=notes,
        is_active=True,
        created_by=actor.id,
    )
    db.add(template)
    await db.flush()

    await record_audit(
        db,
        actor_id=actor.id,
        action="master_template_created",
        entity_type="master_template",
        entity_id=template.id,
        new_value={
            "type": template.type.value,
            "version_number": template.version_number,
            "version_date": str(template.version_date),
            "is_active": template.is_active,
        },
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(template)
    return template


async def list_fields_by_template(db: AsyncSession, template_id: uuid.UUID) -> list[MasterField]:
    result = await db.execute(
        select(MasterField).where(MasterField.template_id == template_id).order_by(MasterField.sort_order.asc())
    )
    return result.scalars().all()

