from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from weasyprint import CSS, HTML

from models.agreement import Agreement, AgreementFieldValue
from models.ai_review import DeviationReport
from models.master import MasterField
from models.user import User

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"
UPLOADS_DIR = BASE_DIR / "uploads" / "agreements"

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _change_type(default_value: str | None, entered_value: str | None) -> str:
    default_norm = (default_value or "").strip()
    entered_norm = (entered_value or "").strip()
    if entered_norm == default_norm:
        return "Unchanged"
    if not default_norm and entered_norm:
        return "Filled"
    if default_norm and entered_norm and entered_norm != default_norm:
        return "Modified"
    return "Unchanged"


async def _load_agreement(db: AsyncSession, agreement_id: str) -> Agreement | None:
    result = await db.execute(
        select(Agreement)
        .where(Agreement.id == agreement_id)
        .options(selectinload(Agreement.field_values))
    )
    return result.scalar_one_or_none()


async def _load_master_fields(db: AsyncSession) -> dict[str, MasterField]:
    res = await db.execute(select(MasterField))
    return {field.field_id: field for field in res.scalars().all()}


async def generate_deviation_report(
    db: AsyncSession,
    agreement_id: str,
    generated_by: User | None,
    force_regenerate: bool = False,
) -> DeviationReport:
    agreement = await _load_agreement(db, agreement_id)
    if not agreement:
        raise ValueError("Agreement not found")

    if not force_regenerate:
        existing = await db.execute(
            select(DeviationReport)
            .where(DeviationReport.agreement_id == agreement.id)
            .order_by(DeviationReport.generated_at.desc())
            .limit(1)
        )
        report = existing.scalar_one_or_none()
        if report:
            return report

    master_fields = await _load_master_fields(db)
    rows: list[dict[str, Any]] = []
    modified = 0
    filled = 0
    unchanged = 0

    for value_row in agreement.field_values:
        mf = master_fields.get(value_row.field_id)
        if not mf:
            continue
        change = _change_type(mf.default_value, value_row.entered_value)
        if change == "Modified":
            modified += 1
        elif change == "Filled":
            filled += 1
        else:
            unchanged += 1

        rows.append(
            {
                "clause_number": mf.clause_number,
                "clause_title": mf.field_label,
                "default_value": mf.default_value or "",
                "entered_value": value_row.entered_value or "",
                "change_type": change,
                "risk": "Pending AI",
            }
        )

    rows.sort(key=lambda r: (r["clause_number"], r["clause_title"]))

    context = {
        "agreement": agreement,
        "rows": rows,
        "summary": {
            "modified": modified,
            "filled": filled,
            "unchanged": unchanged,
        },
        "generated_date": datetime.now(UTC).date().isoformat(),
    }

    report_html = jinja_env.get_template("deviation_report.html").render(**context)
    wrapped_html = f"""
    <html>
      <head><meta charset="utf-8"></head>
      <body>{report_html}</body>
    </html>
    """
    css = CSS(filename=str(TEMPLATES_DIR / "base_pdf.css"))
    pdf_bytes = HTML(string=wrapped_html, base_url=str(BASE_DIR)).write_pdf(stylesheets=[css])

    agreement_dir = UPLOADS_DIR / agreement.reference_number
    agreement_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    pdf_path = agreement_dir / f"deviation_{timestamp}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    report = DeviationReport(
        agreement_id=agreement.id,
        generated_by=generated_by.id if generated_by else None,
        report_data_json=rows,
        pdf_path=str(pdf_path),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report
