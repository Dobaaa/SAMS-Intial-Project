from __future__ import annotations

from datetime import UTC, datetime
from html import escape as html_escape
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


def _format_money(value: object) -> str:
    """Render a numeric value with thousand separators (and 2-dp decimals).

    Free-form text (e.g. ``60 days PDC``) is returned verbatim so this filter
    is safe to chain everywhere in the templates. The filter NEVER raises;
    unparseable input round-trips as-is.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    cleaned = text.replace(",", "").replace(" ", "")
    try:
        n = float(cleaned)
    except ValueError:
        return text
    if n.is_integer():
        return f"{int(n):,}"
    return f"{n:,.2f}"


jinja_env.filters["money"] = _format_money


# Legacy phrasings from the first batch of client master templates, before the
# {{FIELD_ID}} convention. Keep mapping up-to-date as long as any master
# template in the DB still uses these strings; delete once migrated.
LEGACY_TOKEN_MAP: dict[str, str] = {
    "[Insert Name]": "F02",
    "[Insert PO]": "F03",
    "[TL Nr.]": "F04",
    "[Insert Employer Name]": "F05",
    "[Insert Project Name / Details]": "F06",
    "[Insert Project Location]": "F07",
    "[Insert Amount]": "F08",
    "(……Insert…..) Scope to be detailed here": "C01",
    "(……Insert…..) To Insert the Quantities Type": "C02",
    "(……Insert…..) UAE Dirhams": "C03",
}


def _render_master_with_values(
    content_html: str,
    values: dict[str, str],
    master_fields: dict[str, MasterField],
) -> str:
    """Replace placeholders in master-template HTML with entered values.

    Two substitution passes, in order:

    1. **Generic token pass** — for every field in the master_fields
       catalog, replace ``{{FIELD_ID}}`` (e.g. ``{{F02}}``, ``{{C03}}``,
       or any future ``{{X42}}`` Admin adds) with the agreement's entered
       value, HTML-escaped. This is the authoritative, schema-driven
       mechanism: new admin-added fields render automatically with no
       code change.

    2. **Legacy phrase bridge** — replaces known hardcoded phrases from
       the initial client documents (``[Insert Name]`` etc.) with the
       same HTML-escaped values, driven by ``LEGACY_TOKEN_MAP``. This is
       a migration aid; once all master templates have been re-authored
       to use ``{{FIELD_ID}}`` tokens, this block can be removed.

    No sequential "pop the next value" fallback: that corrupted output
    silently when the legal text reordered. Missing tokens are left
    visible in the rendered PDF so Admin knows to fix the template.
    """
    rendered = content_html

    def _display_value(fid: str) -> str:
        raw = values.get(fid, "") or ""
        mf = master_fields.get(fid)
        if mf is not None and mf.input_type.value == "number":
            return _format_money(raw)
        return raw

    for field_id in master_fields:
        token = f"{{{{{field_id}}}}}"  # literal: {{F02}}
        if token in rendered:
            rendered = rendered.replace(token, html_escape(_display_value(field_id)))

    for phrase, field_id in LEGACY_TOKEN_MAP.items():
        if phrase in rendered:
            rendered = rendered.replace(phrase, html_escape(_display_value(field_id)))

    return rendered


def _status_watermark(status: AgreementStatusEnum) -> str:
    """Return the watermark text to overlay on every PDF page.

    Empty string means "no watermark" — once an agreement is fully executed
    (status = completed) the PDF is the final document and no overlay should
    bleed through. The Jinja shells skip rendering the .watermark div when
    this is empty, so the regenerated post-signature PDF is fully clean.
    """
    if status == AgreementStatusEnum.completed:
        return ""
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


def _appendix_overrides(
    appendix_config: list[AppendixConfig],
) -> tuple[dict[str, bool], dict[str, str]]:
    visible: dict[str, bool] = {}
    notes: dict[str, str] = {}
    for row in appendix_config:
        visible[row.field_id] = row.show_in_appendix
        if row.admin_extra_note:
            notes[row.field_id] = row.admin_extra_note
    return visible, notes


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
    appendix_visible, appendix_notes = _appendix_overrides(agreement.appendix_rows)

    context: dict[str, Any] = {
        "agreement": agreement,
        "project": agreement.project,
        "subcontractor": agreement.subcontractor,
        "values": value_map,
        "appendix_rows": appendix_rows,
        "appendix_visible": appendix_visible,
        "appendix_notes": appendix_notes,
        "status_watermark": _status_watermark(agreement.current_status),
        "generated_date": datetime.now(UTC).date().isoformat(),
        "bgcc_logo_url": "",
    }

    cover_html = jinja_env.get_template("cover_page.html").render(**context)
    form_html = jinja_env.get_template("form_of_agreement.html").render(
        **context,
        form_content=_render_master_with_values(form_doc.content_html, value_map, master_fields),
    )
    conditions_html = jinja_env.get_template("conditions.html").render(
        **context,
        conditions_content=_render_master_with_values(conditions_doc.content_html, value_map, master_fields),
    )
    appendix_html = jinja_env.get_template("appendix.html").render(**context)

    reference_number = html_escape(agreement.reference_number or "")
    # Running header replicates the BGCC source: small BHATIA logo on the
    # left, italic blue gradient text "BHATIA GENERAL CONTRACTING CO. L.L.C.
    # (BGCC" on the right. The image path is relative to BASE_DIR (the
    # WeasyPrint base_url passed to write_pdf below).
    running_header = (
        '<div class="running-header">'
        '  <div class="rh-logo">'
        '    <img class="rh-logo-img" src="backend/templates/bhatia-logo.png" alt="BHATIA" />'
        '  </div>'
        '  <div class="rh-name">BHATIA GENERAL CONTRACTING CO. L.L.C. (BGCC</div>'
        '</div>'
        f'<span class="reference-anchor">{reference_number}</span>'
    )

    # Document order matches the cover-page list in the source PDF:
    #   Cover → Form → Appendix → Conditions
    # (the previous code rendered Form → Conditions → Appendix which
    # disagreed with the table-of-contents on the cover.) The running
    # header is declared once before the first body-page; WeasyPrint reuses
    # it via @top-left on every subsequent page. Each section template
    # starts with its own .section-title-page div, which carries
    # `page-break-after: always` to land the title on its own page.
    combined_html = f"""
    <html>
      <head><meta charset="utf-8"></head>
      <body>
        {cover_html}
        {running_header}
        {form_html}
        {appendix_html}
        {conditions_html}
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
