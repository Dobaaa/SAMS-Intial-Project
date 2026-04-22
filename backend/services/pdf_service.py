from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from weasyprint import CSS, HTML

from models.agreement import Agreement, AgreementStatusEnum, AgreementFieldValue, AppendixConfig
from models.ai_review import PDFOutput, PDFTypeEnum
from models.master import MasterField
from models.user import User

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"
UPLOADS_DIR = BASE_DIR / "uploads" / "agreements"

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _render_master_with_values(content_html: str, values: dict[str, str]) -> str:
    replacements = {
        "[Insert Name]": values.get("F02", ""),
        "[Insert PO]": values.get("F03", ""),
        "[TL Nr.]": values.get("F04", ""),
        "[Insert Employer Name]": values.get("F05", ""),
        "[Insert Project Name / Details]": values.get("F06", ""),
        "[Insert Project Location]": values.get("F07", ""),
        "[Insert Amount]": values.get("F08", ""),
        "(……Insert…..) Scope to be detailed here": values.get("C01", ""),
        "(……Insert…..) To Insert the Quantities Type": values.get("C02", ""),
        "(……Insert…..) UAE Dirhams": values.get("C03", ""),
        "within (……Insert…..)": f"within {values.get('C04', '')}",
    }
    rendered = content_html
    for src, dst in replacements.items():
        rendered = rendered.replace(src, str(dst))
    return rendered


def _status_watermark(status: AgreementStatusEnum) -> str:
    if status == AgreementStatusEnum.completed:
        return "EXECUTED"
    if status in (AgreementStatusEnum.under_subcontractor_signature, AgreementStatusEnum.under_gm_signature):
        return "FINAL"
    return "DRAFT"


async def _load_agreement_bundle(db: AsyncSession, agreement_id: str) -> Agreement | None:
    query = (
        select(Agreement)
        .where(Agreement.id == agreement_id)
        .options(
            selectinload(Agreement.project),
            selectinload(Agreement.subcontractor),
            selectinload(Agreement.field_values),
            selectinload(Agreement.appendix_rows),
        )
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def _load_master_fields(db: AsyncSession) -> dict[str, MasterField]:
    result = await db.execute(select(MasterField))
    rows = result.scalars().all()
    return {row.field_id: row for row in rows}


def _collect_field_values(field_values: list[AgreementFieldValue]) -> dict[str, str]:
    return {item.field_id: item.entered_value or "" for item in field_values}


def _appendix_rows(
    appendix_config: list[AppendixConfig],
    field_values: dict[str, str],
    master_fields: dict[str, MasterField],
) -> list[dict[str, str]]:
    visible = [row for row in appendix_config if row.show_in_appendix]
    visible.sort(key=lambda x: x.sort_order)
    rows: list[dict[str, str]] = []
    for row in visible:
        mf = master_fields.get(row.field_id)
        if not mf:
            continue
        info = field_values.get(row.field_id, "")
        if row.admin_extra_note:
            info = f"{info}\n{row.admin_extra_note}" if info else row.admin_extra_note
        rows.append(
            {
                "item_description": mf.appendix_row_label or mf.field_label,
                "clause_no": mf.appendix_clause_ref or mf.clause_number,
                "information": info,
            }
        )
    return rows


async def generate_agreement_pdf(db: AsyncSession, agreement_id: str, generated_by: User | None) -> PDFOutput:
    agreement = await _load_agreement_bundle(db, agreement_id)
    if not agreement:
        raise ValueError("Agreement not found")

    if not agreement.form_version_id or not agreement.conditions_version_id:
        raise ValueError("Agreement templates are not configured")

    from models.master import MasterTemplate  # local import to avoid cycles in some environments

    form_doc = await db.get(MasterTemplate, agreement.form_version_id)
    conditions_doc = await db.get(MasterTemplate, agreement.conditions_version_id)
    if not form_doc or not conditions_doc:
        raise ValueError("Master template versions not found")

    value_map = _collect_field_values(agreement.field_values)
    master_fields = await _load_master_fields(db)
    appendix_rows = _appendix_rows(agreement.appendix_rows, value_map, master_fields)

    context: dict[str, Any] = {
        "agreement": agreement,
        "project": agreement.project,
        "subcontractor": agreement.subcontractor,
        "values": value_map,
        "appendix_rows": appendix_rows,
        "status_watermark": _status_watermark(agreement.current_status),
        "generated_date": datetime.now(UTC).date().isoformat(),
        "bgcc_logo_url": "",
    }

    cover_html = jinja_env.get_template("cover_page.html").render(**context)
    form_html = jinja_env.get_template("form_of_agreement.html").render(
        **context, form_content=_render_master_with_values(form_doc.content_html, value_map)
    )
    conditions_html = jinja_env.get_template("conditions.html").render(
        **context, conditions_content=_render_master_with_values(conditions_doc.content_html, value_map)
    )
    appendix_html = jinja_env.get_template("appendix.html").render(**context)

    combined_html = f"""
    <html>
      <head><meta charset="utf-8"></head>
      <body>
        {cover_html}
        <div class="page-break"></div>
        {form_html}
        <div class="page-break"></div>
        {conditions_html}
        <div class="page-break"></div>
        {appendix_html}
      </body>
    </html>
    """

    css = CSS(filename=str(TEMPLATES_DIR / "base_pdf.css"))
    pdf_bytes = HTML(string=combined_html, base_url=str(BASE_DIR)).write_pdf(stylesheets=[css])

    agreement_dir = UPLOADS_DIR / agreement.reference_number
    agreement_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    pdf_path = agreement_dir / f"draft_{timestamp}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    output = PDFOutput(
        agreement_id=agreement.id,
        pdf_type=PDFTypeEnum.draft,
        file_path=str(pdf_path),
        generated_by=generated_by.id if generated_by else None,
        watermark_type=context["status_watermark"],
    )
    db.add(output)
    await db.commit()
    await db.refresh(output)
    return output
