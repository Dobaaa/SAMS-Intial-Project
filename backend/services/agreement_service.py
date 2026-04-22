import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agreement import (
    Agreement,
    AgreementFieldValue,
    AgreementStatusEnum,
    AppendixConfig,
    Project,
    Subcontractor,
)
from models.master import MasterField, MasterTemplate, TemplateTypeEnum
from models.user import RoleEnum, User
from models.workflow import WorkflowStep, WorkflowStepStatusEnum


async def _get_active_template(db: AsyncSession, template_type: TemplateTypeEnum) -> MasterTemplate | None:
    res = await db.execute(
        select(MasterTemplate)
        .where(and_(MasterTemplate.type == template_type, MasterTemplate.is_active.is_(True)))
        .order_by(MasterTemplate.version_date.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _build_reference_number(db: AsyncSession, project_code: str) -> str:
    year = datetime.now(UTC).year
    prefix = f"SAG-{project_code}-{year}-"
    res = await db.execute(
        select(func.count(Agreement.id)).where(Agreement.reference_number.like(f"{prefix}%"))
    )
    seq = (res.scalar_one() or 0) + 1
    return f"{prefix}{seq:03d}"


async def create_draft_agreement(
    db: AsyncSession,
    user: User,
    project_payload: dict,
    subcontractor_payload: dict,
    reference_number: str | None = None,
) -> Agreement:
    project = Project(**project_payload, created_by=user.id)
    subcontractor = Subcontractor(**subcontractor_payload)
    db.add_all([project, subcontractor])
    await db.flush()

    form_template = await _get_active_template(db, TemplateTypeEnum.form)
    conditions_template = await _get_active_template(db, TemplateTypeEnum.conditions)
    appendix_template = await _get_active_template(db, TemplateTypeEnum.appendix)
    if not form_template or not conditions_template or not appendix_template:
        raise ValueError("Active templates are required for form, conditions, and appendix")

    ref = reference_number or await _build_reference_number(db, project.project_code)
    agreement = Agreement(
        reference_number=ref,
        project_id=project.id,
        subcontractor_id=subcontractor.id,
        form_version_id=form_template.id,
        conditions_version_id=conditions_template.id,
        appendix_version_id=appendix_template.id,
        current_status=AgreementStatusEnum.under_drafting,
        status_updated_on=datetime.now(UTC),
        created_by=user.id,
    )
    db.add(agreement)
    await db.flush()

    fields_res = await db.execute(
        select(MasterField).where(
            MasterField.template_id.in_([form_template.id, conditions_template.id, appendix_template.id])
        )
    )
    for field in fields_res.scalars().all():
        db.add(
            AgreementFieldValue(
                agreement_id=agreement.id,
                field_id=field.field_id,
                entered_value=field.default_value,
                is_modified_from_default=False,
                entered_by=user.id,
            )
        )
        if field.field_id.startswith("A"):
            db.add(
                AppendixConfig(
                    agreement_id=agreement.id,
                    field_id=field.field_id,
                    show_in_appendix=field.show_in_appendix,
                    sort_order=field.sort_order,
                    last_modified_by=user.id,
                )
            )

    await db.commit()
    await db.refresh(agreement)
    return agreement


async def update_agreement_fields(db: AsyncSession, agreement: Agreement, user: User, values: dict[str, str]) -> None:
    master_res = await db.execute(select(MasterField))
    master_map = {mf.field_id: mf for mf in master_res.scalars().all()}

    current_res = await db.execute(
        select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agreement.id)
    )
    current_map = {row.field_id: row for row in current_res.scalars().all()}

    for field_id, entered in values.items():
        row = current_map.get(field_id)
        if not row:
            row = AgreementFieldValue(
                agreement_id=agreement.id,
                field_id=field_id,
                entered_by=user.id,
            )
            db.add(row)
        default_value = master_map.get(field_id).default_value if master_map.get(field_id) else None
        row.entered_value = entered
        row.is_modified_from_default = (entered or "") != (default_value or "")
        row.entered_by = user.id

    # Required auto-population rules
    if "F02" in values:
        values["A01"] = values["F02"]
    if "F05" in values:
        values["A02"] = values["F05"]
    if "F08" in values:
        values["A07"] = values["F08"]
        values["C03"] = values["F08"]

    for auto_key in ("A01", "A02", "A07", "C03"):
        if auto_key in values:
            row = current_map.get(auto_key)
            if not row:
                row = AgreementFieldValue(
                    agreement_id=agreement.id,
                    field_id=auto_key,
                    entered_by=user.id,
                )
                db.add(row)
            default_value = master_map.get(auto_key).default_value if master_map.get(auto_key) else None
            row.entered_value = values[auto_key]
            row.is_modified_from_default = (values[auto_key] or "") != (default_value or "")
            row.entered_by = user.id

    agreement.updated_at = datetime.now(UTC)
    await db.commit()


async def submit_for_review(db: AsyncSession, agreement: Agreement) -> None:
    existing = await db.execute(select(WorkflowStep).where(WorkflowStep.agreement_id == agreement.id))
    if existing.scalars().first():
        return

    chain = [
        ("Project Director", 1, RoleEnum.project_director),
        ("Accounts Department", 2, RoleEnum.accounts),
        ("Operation Manager", 3, RoleEnum.operation_manager),
        ("General Manager", 4, RoleEnum.gm),
    ]
    for name, order, role in chain:
        db.add(
            WorkflowStep(
                agreement_id=agreement.id,
                step_name=name,
                step_order=order,
                role_required=role,
                status=WorkflowStepStatusEnum.pending,
            )
        )

    agreement.current_status = AgreementStatusEnum.under_internal_review
    agreement.status_updated_on = datetime.now(UTC)
    agreement.updated_at = datetime.now(UTC)
    await db.commit()
