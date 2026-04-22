import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from database import AsyncSessionLocal
from models.master import InputTypeEnum, MasterField, MasterTemplate, TemplateTypeEnum


@dataclass(frozen=True)
class FieldSeed:
    template_type: TemplateTypeEnum
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


FIELDS: list[FieldSeed] = [
    # Form (F01-F08)
    FieldSeed(TemplateTypeEnum.form, "F01", "Cover", "Day of signing", InputTypeEnum.date, is_required=True, sort_order=1),
    FieldSeed(TemplateTypeEnum.form, "F02", "Between", "Subcontractor company name", InputTypeEnum.text, is_required=True, appendix_row_label="The Subcontractor", appendix_clause_ref="1.1", sort_order=2),
    FieldSeed(TemplateTypeEnum.form, "F03", "Between", "Subcontractor PO Box", InputTypeEnum.text, sort_order=3),
    FieldSeed(TemplateTypeEnum.form, "F04", "Between", "Trade Licence Number", InputTypeEnum.text, sort_order=4),
    FieldSeed(TemplateTypeEnum.form, "F05", "Preamble", "Employer entity name", InputTypeEnum.text, is_required=True, appendix_row_label="The Employer", appendix_clause_ref="1.1", sort_order=5),
    FieldSeed(TemplateTypeEnum.form, "F06", "Preamble", "Project name/details", InputTypeEnum.textarea, is_required=True, sort_order=6),
    FieldSeed(TemplateTypeEnum.form, "F07", "Preamble", "Project location", InputTypeEnum.text, is_required=True, sort_order=7),
    FieldSeed(TemplateTypeEnum.form, "F08", "2", "Subcontract Price (AED)", InputTypeEnum.number, is_required=True, appendix_row_label="The Subcontract Price", appendix_clause_ref="3.1", sort_order=8),
    # Conditions (C01-C13)
    FieldSeed(TemplateTypeEnum.conditions, "C01", "2.2", "Scope of Works details", InputTypeEnum.textarea, is_required=True, sort_order=1),
    FieldSeed(TemplateTypeEnum.conditions, "C02", "3.3", "Subcontract Quantities Type", InputTypeEnum.dropdown, is_required=True, sort_order=2),
    FieldSeed(TemplateTypeEnum.conditions, "C03", "3.4.1", "Advance Payment Amount (AED)", InputTypeEnum.number, default_value="10% of F08", sort_order=3),
    FieldSeed(TemplateTypeEnum.conditions, "C04", "3.4.1", "Advance Payment release condition", InputTypeEnum.text, sort_order=4),
    FieldSeed(TemplateTypeEnum.conditions, "C05", "3.4.6", "Interim Payment days", InputTypeEnum.number, is_required=True, sort_order=5),
    FieldSeed(TemplateTypeEnum.conditions, "C06", "3.4.7", "1st Half Retention release days", InputTypeEnum.number, sort_order=6),
    FieldSeed(TemplateTypeEnum.conditions, "C07", "3.4.7", "2nd Half Retention release days", InputTypeEnum.number, sort_order=7),
    FieldSeed(TemplateTypeEnum.conditions, "C08", "4.3", "Time for Completion (Project)", InputTypeEnum.text, is_required=True, sort_order=8),
    FieldSeed(TemplateTypeEnum.conditions, "C09", "4.3", "Milestones table", InputTypeEnum.table, sort_order=9),
    FieldSeed(TemplateTypeEnum.conditions, "C10", "5", "Defects Liability Period (months)", InputTypeEnum.number, default_value="12", sort_order=10),
    FieldSeed(TemplateTypeEnum.conditions, "C11", "6.2", "Rate of Liquidated Damages (AED/day)", InputTypeEnum.number, is_required=True, sort_order=11),
    FieldSeed(TemplateTypeEnum.conditions, "C12", "10.1", "Insurance submission deadline (days)", InputTypeEnum.number, sort_order=12),
    FieldSeed(TemplateTypeEnum.conditions, "C13", "13.3", "Dispute Resolution Jurisdiction", InputTypeEnum.text, is_required=True, sort_order=13),
    # Appendix (A01-A06) to complete 27 initial insert fields
    FieldSeed(TemplateTypeEnum.appendix, "A01", "1.1", "The Subcontractor", InputTypeEnum.text, auto_source_field_id="F02", appendix_row_label="The Subcontractor", appendix_clause_ref="1.1", sort_order=1),
    FieldSeed(TemplateTypeEnum.appendix, "A02", "1.1", "The Employer", InputTypeEnum.text, auto_source_field_id="F05", appendix_row_label="The Employer", appendix_clause_ref="1.1", sort_order=2),
    FieldSeed(TemplateTypeEnum.appendix, "A03", "1.1", "Engineer/Consultant/Subconsultant", InputTypeEnum.text, appendix_row_label="The Engineer/Consultant/Subconsultant", appendix_clause_ref="1.1", sort_order=3),
    FieldSeed(TemplateTypeEnum.appendix, "A04", "1.1", "The Project", InputTypeEnum.textarea, auto_source_field_id="F06", appendix_row_label="The Project", appendix_clause_ref="1.1", sort_order=4),
    FieldSeed(TemplateTypeEnum.appendix, "A05", "1.6", "Main Contractor communications address", InputTypeEnum.multifield, appendix_row_label="Main Contractor Address", appendix_clause_ref="1.6", sort_order=5),
    FieldSeed(TemplateTypeEnum.appendix, "A06", "1.6", "Subcontractor communications address", InputTypeEnum.multifield, auto_source_field_id="F03", appendix_row_label="Subcontractor Address", appendix_clause_ref="1.6", sort_order=6),
]


async def seed_master_fields() -> None:
    async with AsyncSessionLocal() as session:
        templates_by_type: dict[TemplateTypeEnum, MasterTemplate] = {}
        for template_type in TemplateTypeEnum:
            stmt = (
                select(MasterTemplate)
                .where(MasterTemplate.type == template_type)
                .order_by(MasterTemplate.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            template = result.scalar_one_or_none()
            if template is None:
                raise RuntimeError(f"Missing master template for type '{template_type.value}'. Seed templates first.")
            templates_by_type[template_type] = template

        for field in FIELDS:
            template = templates_by_type[field.template_type]
            exists_stmt = select(MasterField.id).where(
                MasterField.template_id == template.id,
                MasterField.field_id == field.field_id,
            )
            exists = (await session.execute(exists_stmt)).scalar_one_or_none()
            if exists:
                continue

            session.add(
                MasterField(
                    template_id=template.id,
                    field_id=field.field_id,
                    clause_number=field.clause_number,
                    field_label=field.field_label,
                    input_type=field.input_type,
                    default_value=field.default_value,
                    is_required=field.is_required,
                    auto_source_field_id=field.auto_source_field_id,
                    appendix_row_label=field.appendix_row_label,
                    appendix_clause_ref=field.appendix_clause_ref,
                    show_in_appendix=field.show_in_appendix,
                    sort_order=field.sort_order,
                )
            )

        await session.commit()
    print(f"Seeded {len(FIELDS)} master_fields rows.")


if __name__ == "__main__":
    asyncio.run(seed_master_fields())
