"""One-off: render a sample combined PDF using the latest templates.

Skips the DB; feeds the templates a minimal in-memory context so we can
iterate on cover / section-title / body styling without spinning up the
full app. Outputs to /tmp/sams_preview.pdf.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT / "backend" / "templates"
SEEDS_DIR = ROOT / "backend" / "seeds"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _money(value):
    if value in (None, ""):
        return ""
    try:
        n = float(str(value).replace(",", "").strip())
    except ValueError:
        return str(value)
    if n.is_integer():
        return f"{int(n):,}"
    return f"{n:,.2f}"


env.filters["money"] = _money


VALUES = {
    "F01": "10th day of June 2026",
    "F02": "Bhatia Power Electromechanical L.L.C.",
    "F03": "12345",
    "F04": "TL-987654",
    "F05": "Emaar Properties",
    "F06": "Downtown Tower B — Mechanical Works",
    "F07": "Business Bay, Dubai",
    "F08": "5000000",
    "F09": "MEP Subcontract",
    "C01": "Supply, install, test and commission HVAC systems for floors 1-25",
    "C02": "Lump Sum",
    "C03": "500000.00",
    "C04": "submission of the Advance Payment Guarantee",
    "C05": "60 days PDC",
    "C06": "30 days from TOC",
    "C07": "30 days from Final Acceptance",
    "C08": "365 days",
    "C10": "12",
    "C11": "2500",
    "C12": "14 days",
    "C13": "the Courts of Dubai, UAE",
    "C14": "Bank Guarantee Cheque",
    "A03": "Dar Al Handasah",
    "A05": "Operations Director — BGCC",
    "A07": "5000000",
    "A09": "500000",
    "A10": "500000",
    "A15": "1 July 2026",
    "A17": "300 days from Commencement Date",
}


class _Stub:
    pass


def _make_master_field(field_id: str, input_type: str = "text"):
    f = _Stub()
    f.field_id = field_id
    f.input_type = _Stub()
    f.input_type.value = input_type
    f.appendix_row_label = None
    f.appendix_clause_ref = None
    f.field_label = field_id
    f.clause_number = field_id
    return f


MASTER_FIELDS = {fid: _make_master_field(fid, "number" if fid in {"F08", "C03", "A07", "A09", "A10", "A21"} else "text") for fid in VALUES}


def _render_master_with_values(content_html: str, values: dict, master_fields: dict) -> str:
    rendered = content_html

    def _display(fid: str) -> str:
        raw = values.get(fid, "") or ""
        mf = master_fields.get(fid)
        if mf is not None and mf.input_type.value == "number":
            return _money(raw)
        return raw

    for field_id in master_fields:
        token = f"{{{{{field_id}}}}}"
        if token in rendered:
            rendered = rendered.replace(token, escape(_display(field_id)))
    return rendered


def main() -> None:
    form_content = _render_master_with_values(
        (SEEDS_DIR / "form_master.html").read_text(encoding="utf-8"),
        VALUES,
        MASTER_FIELDS,
    )
    conditions_content = _render_master_with_values(
        (SEEDS_DIR / "conditions_master.html").read_text(encoding="utf-8"),
        VALUES,
        MASTER_FIELDS,
    )

    project = _Stub()
    project.project_name = "Downtown Tower B"
    subcontractor = _Stub()
    subcontractor.company_name = "Bhatia Power Electromechanical L.L.C."

    appendix_visible = {f"A{i:02d}": True for i in range(1, 24)}
    appendix_notes: dict[str, str] = {}

    context = {
        "values": VALUES,
        "project": project,
        "subcontractor": subcontractor,
        "appendix_visible": appendix_visible,
        "appendix_notes": appendix_notes,
        "status_watermark": "DRAFT",
        "generated_date": "2026-05-11",
        "bgcc_logo_url": "",
    }

    cover_html = env.get_template("cover_page.html").render(**context)
    form_html = env.get_template("form_of_agreement.html").render(
        **context, form_content=form_content
    )
    conditions_html = env.get_template("conditions.html").render(
        **context, conditions_content=conditions_content
    )
    appendix_html = env.get_template("appendix.html").render(**context)

    running_header = (
        '<div class="running-header">'
        '  <div class="rh-logo">'
        '    <img class="rh-logo-img" src="backend/templates/bhatia-logo.png" alt="BHATIA" />'
        '  </div>'
        '  <div class="rh-name">BHATIA GENERAL CONTRACTING CO. L.L.C. (BGCC</div>'
        '</div>'
        '<span class="reference-anchor">SAG-PREVIEW-2026-001</span>'
    )

    combined = f"""
    <html><head><meta charset="utf-8"></head>
    <body>
      {cover_html}
      {running_header}
      {form_html}
      {appendix_html}
      {conditions_html}
    </body></html>
    """

    css = CSS(filename=str(TEMPLATES_DIR / "base_pdf.css"))
    out = Path("/tmp/sams_preview.pdf")
    HTML(string=combined, base_url=str(ROOT)).write_pdf(stylesheets=[css], target=str(out))
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
