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
    FieldSeed(TemplateTypeEnum.form, "F09", "Cover", "Scope Title", InputTypeEnum.text, is_required=True, show_in_appendix=False, sort_order=9),
    # Conditions (C01-C13)
    FieldSeed(TemplateTypeEnum.conditions, "C01", "2.2", "Scope of Works details", InputTypeEnum.textarea, is_required=True, sort_order=1),
    FieldSeed(TemplateTypeEnum.conditions, "C02", "3.3", "Contract Type", InputTypeEnum.dropdown, is_required=True, sort_order=2),
    FieldSeed(TemplateTypeEnum.conditions, "C03", "3.4.1", "Advance Payment Amount (AED)", InputTypeEnum.number, sort_order=3),
    FieldSeed(TemplateTypeEnum.conditions, "C03_PCT", "3.4.1", "Advance Payment (%)", InputTypeEnum.number, default_value="10", sort_order=3),
    FieldSeed(TemplateTypeEnum.conditions, "C04", "3.4.1", "Advance Payment release condition", InputTypeEnum.text, sort_order=4),
    # Number-only (2026-08-26 client feedback item 1) — the docx wraps the
    # entered day count in fixed "X days PDC within 15 days from the
    # invoice date" wording itself, so free text is no longer needed here.
    FieldSeed(TemplateTypeEnum.conditions, "C05", "3.4.6", "Interim Payment days", InputTypeEnum.number, is_required=True, sort_order=5),
    FieldSeed(TemplateTypeEnum.conditions, "C06", "3.4.7", "1st Half Retention release days", InputTypeEnum.number, sort_order=6),
    FieldSeed(TemplateTypeEnum.conditions, "C07", "3.4.7", "2nd Half Retention release days", InputTypeEnum.number, sort_order=7),
    # No longer required (2026-08-24 client feedback): orphaned from the
    # master docx alongside A16, per the removal of clause 4.3(a)'s
    # project-level Time for Completion line. Hidden from the wizard's
    # Conditions step (frontend filter) but left in the data model.
    FieldSeed(TemplateTypeEnum.conditions, "C08", "4.3", "Time for Completion (Project) in days", InputTypeEnum.text, is_required=False, sort_order=8),
    FieldSeed(TemplateTypeEnum.conditions, "C09", "4.3", "Milestones table", InputTypeEnum.table, sort_order=9),
    # Number-only (2026-08-26 client feedback item 5, reverses the 2026-06-02
    # text change) — the docx now appends "Months" itself, both in the body
    # clause (already did) and the Appendix DLP row (fixed this round), so
    # free-form unit text ("12 months"/"365 days") would double up the unit.
    FieldSeed(TemplateTypeEnum.conditions, "C10", "5", "Defects Liability Period (months)", InputTypeEnum.number, sort_order=10),
    FieldSeed(TemplateTypeEnum.conditions, "C11", "6.2", "Rate of Liquidated Damages (AED/day)", InputTypeEnum.number, is_required=True, sort_order=11),
    FieldSeed(TemplateTypeEnum.conditions, "C12", "10.1", "Insurance submission deadline (days)", InputTypeEnum.number, sort_order=12),
    FieldSeed(TemplateTypeEnum.conditions, "C13", "13.3", "Dispute Resolution Jurisdiction", InputTypeEnum.text, is_required=True, sort_order=13),
    # Performance Security Type: admin picks Bank Guarantee Cheque vs
    # Company Security Cheque. Cascades into the appendix beneath
    # A10 (Performance Security amount) for the executed agreement.
    FieldSeed(TemplateTypeEnum.conditions, "C14", "3.4.2", "Performance Security Type", InputTypeEnum.dropdown, is_required=True, appendix_row_label="Performance Security Type", appendix_clause_ref="3.4.2", sort_order=14),
    # Free-text "Important Notes & Special Conditions" clause. Renders as the last row of the
    # APPENDIX continuation table on page 7 (the {{C15}} token, added by
    # scripts/apply_master_c15_patch.py). No spec clause number — clause_number
    # left blank so the UI doesn't print a "· clause" label.
    FieldSeed(TemplateTypeEnum.conditions, "C15", "", "Important Notes & Special Conditions", InputTypeEnum.textarea, appendix_row_label="Important Notes & Special Conditions", sort_order=15),
    # Appendix (A01-A23)
    FieldSeed(TemplateTypeEnum.appendix, "A01", "1.1", "The Subcontractor", InputTypeEnum.text, auto_source_field_id="F02", appendix_row_label="The Subcontractor", appendix_clause_ref="1.1", sort_order=1),
    FieldSeed(TemplateTypeEnum.appendix, "A02", "1.1", "The Employer", InputTypeEnum.text, auto_source_field_id="F05", appendix_row_label="The Employer", appendix_clause_ref="1.1", sort_order=2),
    FieldSeed(TemplateTypeEnum.appendix, "A03", "1.1", "Engineer/Consultant/Subconsultant", InputTypeEnum.text, appendix_row_label="The Engineer/Consultant/Subconsultant", appendix_clause_ref="1.1", sort_order=3),
    FieldSeed(TemplateTypeEnum.appendix, "A04", "1.1", "The Project", InputTypeEnum.textarea, auto_source_field_id="F06", appendix_row_label="The Project", appendix_clause_ref="1.1", sort_order=4),
    FieldSeed(TemplateTypeEnum.appendix, "A05", "1.6", "Main Contractor communications address", InputTypeEnum.multifield, appendix_row_label="Main Contractor Address", appendix_clause_ref="1.6", show_in_appendix=False, sort_order=5),
    FieldSeed(TemplateTypeEnum.appendix, "A06", "1.6", "Subcontractor communications address", InputTypeEnum.multifield, auto_source_field_id="F03", appendix_row_label="Subcontractor Address", appendix_clause_ref="1.6", sort_order=6),
    FieldSeed(TemplateTypeEnum.appendix, "A07", "3.1", "Subcontract Price (AED)", InputTypeEnum.number, auto_source_field_id="F08", appendix_row_label="The Subcontract Price", appendix_clause_ref="3.1", sort_order=7),
    FieldSeed(TemplateTypeEnum.appendix, "A08", "3.3", "Contract Type", InputTypeEnum.dropdown, auto_source_field_id="C02", appendix_row_label="The Subcontract Quantities (Lump Sum or Re-measurable)", appendix_clause_ref="3.3", sort_order=8),
    FieldSeed(TemplateTypeEnum.appendix, "A09", "3.4.1", "Advance Payment Amount (AED)", InputTypeEnum.number, auto_source_field_id="C03", appendix_row_label="Advance Payment Amount", appendix_clause_ref="3.4.1", sort_order=9),
    FieldSeed(TemplateTypeEnum.appendix, "A10", "3.4.2", "Performance Security (%)", InputTypeEnum.number, default_value="10", appendix_row_label="Performance Security", appendix_clause_ref="3.4.2", sort_order=10),
    FieldSeed(TemplateTypeEnum.appendix, "A11", "3.4.1", "Advance Payment release condition", InputTypeEnum.text, auto_source_field_id="C04", appendix_row_label="Advance Payment to be released by the Main Contractor", appendix_clause_ref="3.4.1", sort_order=11),
    FieldSeed(TemplateTypeEnum.appendix, "A12", "3.4.6", "Interim Payment days", InputTypeEnum.number, auto_source_field_id="C05", appendix_row_label="Interim Payment to be paid by the Main Contractor", appendix_clause_ref="3.4.6", sort_order=12),
    FieldSeed(TemplateTypeEnum.appendix, "A13", "3.4.7", "1st Half Retention release", InputTypeEnum.text, auto_source_field_id="C06", appendix_row_label="1st Half of retention Money to be released by the Main Contractor", appendix_clause_ref="3.4.7", sort_order=13),
    FieldSeed(TemplateTypeEnum.appendix, "A14", "3.4.7", "2nd Half Retention release", InputTypeEnum.text, auto_source_field_id="C07", appendix_row_label="2nd Half of retention Money to be released by the Main Contractor", appendix_clause_ref="3.4.7", sort_order=14),
    # A15 (Commencement Date / clause 4.1) removed entirely per 2026-08-24
    # client feedback -- clause 4.1 itself is deleted from the master docx
    # (see apply_master_remove_commencement_time_pdc_patch.py), so this row
    # is hidden rather than deleted from the data model.
    FieldSeed(TemplateTypeEnum.appendix, "A15", "4.1", "Commencement Date", InputTypeEnum.date, appendix_row_label="Commencement Date", appendix_clause_ref="4.1", show_in_appendix=False, sort_order=15),
    # A16 (Time for Completion - Project) removed per the same feedback --
    # only the Subcontract Works line (A17) remains in the appendix. Clauses
    # renumbered 4.3->4.2 after clause 4.1's removal.
    FieldSeed(TemplateTypeEnum.appendix, "A16", "4.3(a)", "Time for Completion - Project", InputTypeEnum.text, auto_source_field_id="C08", appendix_row_label="Time for Completion of the Project", appendix_clause_ref="4.3(a)", show_in_appendix=False, sort_order=16),
    # Number-only (2026-08-26 client feedback item 2) — "days" is already
    # appended by the docx itself, both in clause 4.2(a) and the Appendix
    # row, so admin only ever needs to enter the bare day count.
    FieldSeed(TemplateTypeEnum.appendix, "A17", "4.2(a)", "Time for Completion - Subcontract Works in days", InputTypeEnum.number, appendix_row_label="Time for Completion of the Subcontract Works", appendix_clause_ref="4.2(a)", sort_order=17),
    FieldSeed(TemplateTypeEnum.appendix, "A18", "4.2(b)", "Milestones", InputTypeEnum.table, auto_source_field_id="C09", appendix_row_label="Time for Completion of the Sections (Milestones)", appendix_clause_ref="4.2(b)", sort_order=18),
    FieldSeed(TemplateTypeEnum.appendix, "A24", "4.2(b)", "Start of Material Submission", InputTypeEnum.text, appendix_row_label="Start of Material Submission", appendix_clause_ref="4.2(b)", show_in_appendix=False, sort_order=19),
    FieldSeed(TemplateTypeEnum.appendix, "A25", "4.2(b)", "Complete all Material Submission", InputTypeEnum.text, appendix_row_label="Complete all Material Submission", appendix_clause_ref="4.2(b)", show_in_appendix=False, sort_order=20),
    FieldSeed(TemplateTypeEnum.appendix, "A26", "4.2(b)", "Start of Submission of Shop Drawings", InputTypeEnum.text, appendix_row_label="Start of Submission of Shop Drawings", appendix_clause_ref="4.2(b)", show_in_appendix=False, sort_order=21),
    FieldSeed(TemplateTypeEnum.appendix, "A19", "5", "Defects Liability Period (months)", InputTypeEnum.number, auto_source_field_id="C10", appendix_row_label="Defects Liability Period", appendix_clause_ref="5", sort_order=22),
    FieldSeed(TemplateTypeEnum.appendix, "A20", "6.2", "Rate of Liquidated Damages (AED/day)", InputTypeEnum.number, auto_source_field_id="C11", appendix_row_label="Rate Of Liquidated Damages", appendix_clause_ref="6.2", sort_order=23),
    FieldSeed(TemplateTypeEnum.appendix, "A21", "6.2", "Maximum Liquidated Damages in AED", InputTypeEnum.number, default_value="10", appendix_row_label="Maximum Liquidated Damages", appendix_clause_ref="6.2", show_in_appendix=False, sort_order=24),
    FieldSeed(TemplateTypeEnum.appendix, "A22", "10.1", "Insurance submission deadline (days)", InputTypeEnum.number, auto_source_field_id="C12", appendix_row_label="Time to submit the Copies of the required Insurance Policies", appendix_clause_ref="10.1", sort_order=25),
    FieldSeed(TemplateTypeEnum.appendix, "A23", "13.3", "Dispute Resolution Jurisdiction", InputTypeEnum.text, auto_source_field_id="C13", appendix_row_label="Dispute Resolution (Jurisdiction)", appendix_clause_ref="13.3", sort_order=26),
]


async def _seed_into(session) -> None:
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


async def seed_master_fields(session=None) -> None:
    """Seed the 44 master_fields rows.

    When ``session`` is None (CLI use) we open a session via
    ``AsyncSessionLocal``. Tests pass a session bound to the per-test
    engine so the seed lands in the test DB.
    """
    if session is not None:
        await _seed_into(session)
        return
    async with AsyncSessionLocal() as own_session:
        await _seed_into(own_session)
    print(f"Seeded {len(FIELDS)} master_fields rows.")


if __name__ == "__main__":
    asyncio.run(seed_master_fields())
