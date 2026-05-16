"""Render a layout-preview PDF with dummy data — DB-free.

Builds a realistic BGCC subcontract scenario directly from the seed HTML files
and the runtime Jinja templates, then writes the combined PDF to disk so you
can eyeball the layout without needing Postgres / Redis / the API.

Run from the backend/ directory:
    .venv/bin/python -m scripts.preview_sample_pdf
The PDF lands at /tmp/sams_preview.pdf (override via SAMS_PREVIEW_OUT env var).
"""
from __future__ import annotations

import os
import subprocess
from html import escape as html_escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML


BACKEND_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BACKEND_DIR / "templates"
SEEDS_DIR = BACKEND_DIR / "seeds"
OUT_PATH = Path(os.environ.get("SAMS_PREVIEW_OUT", "/tmp/sams_preview.pdf"))


# Dummy agreement data — pretend Marina Tower Phase II steel package.
DUMMY_VALUES: dict[str, str] = {
    # Form
    "F01": "5th day of May, 2026",
    "F02": "ABC Steel Works LLC",
    "F03": "12345",
    "F04": "TL-987654",
    "F05": "Dubai Holding LLC",
    "F06": "Marina Tower Phase II",
    "F07": "Plot 27, Dubai Marina, UAE",
    "F08": "5,000,000.00",
    "F09": "Structural Steel Fabrication & Erection",
    # Conditions
    "C01": (
        "Supply, fabrication, surface treatment, transportation, and erection of "
        "all structural steel members forming the tower's central core, including "
        "all fasteners, base plates, anchor bolts, fireproofing primer, shop "
        "drawings preparation, and as-built documentation, in accordance with the "
        "approved IFC drawings, the technical specifications, and applicable UAE "
        "structural codes."
    ),
    "C02": "Lump Sum",
    "C03": "500,000.00",
    "C04": "fourteen (14) days from receipt of the Advance Payment Guarantee",
    "C05": "30",
    "C06": "60",
    "C07": "60",
    "C08": "twelve (12) months from the Commencement Date or by 31 December 2027 (whichever is earlier)",
    "C09": "Three milestones (refer to Appendix item 4.3(b))",
    "C10": "12",
    "C11": "5,000",
    "C12": "fifteen (15) days",
    "C13": "the competent courts of Dubai",
    # Appendix overrides
    "A05": (
        "Mr. John Smith — Project Director<br>"
        "Office 14, BGCC Tower, P.O. Box 6007, Dubai<br>"
        "Tel: +971 4 123 4567 — john.smith@bgcc.ae"
    ),
    "A06": (
        "Mr. Ahmed Ali — Operations Manager<br>"
        "Plot 27, Al Quoz Industrial 4, P.O. Box 12345, Dubai<br>"
        "Tel: +971 4 765 4321 — ahmed.ali@abcsteel.ae"
    ),
    "A10": "500,000.00",
    "A15": "1 June 2026",
    "A17": "ten (10) months from the Commencement Date",
    "A18_MS1": "Start of Material Submission — within fourteen (14) days from Commencement Date",
    "A18_MS2": "Completion of Material Submission — within forty-five (45) days from Commencement Date",
}


def render_master(content_html: str, values: dict[str, str]) -> str:
    out = content_html
    for fid, val in values.items():
        out = out.replace("{{" + fid + "}}", html_escape(val))
    return out


class _Stub:
    pass


def main() -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    # Mirror the filters registered by services.pdf_service so the preview
    # exercises the same Jinja runtime as the production renderer.
    from services.pdf_service import _format_longdate, _format_money

    env.filters["money"] = _format_money
    env.filters["longdate"] = _format_longdate

    form_src = (SEEDS_DIR / "form_master.html").read_text(encoding="utf-8")
    cond_src = (SEEDS_DIR / "conditions_master.html").read_text(encoding="utf-8")

    agreement = _Stub()
    agreement.reference_number = "SAG-DXBT-2026-001"
    agreement.current_status = type("_S", (), {"value": "under_drafting"})()

    project = _Stub()
    project.project_name = DUMMY_VALUES["F06"]
    subcontractor = _Stub()
    subcontractor.company_name = DUMMY_VALUES["F02"]

    ctx = {
        "agreement": agreement,
        "project": project,
        "subcontractor": subcontractor,
        "values": DUMMY_VALUES,
        "appendix_rows": [],
        "appendix_visible": {},  # default-True everywhere
        "appendix_notes": {},
        "status_watermark": "DRAFT",
        "generated_date": "2026-04-25",
        "bgcc_logo_url": "",
    }

    cover = env.get_template("cover_page.html").render(**ctx)
    form = env.get_template("form_of_agreement.html").render(
        **ctx, form_content=render_master(form_src, DUMMY_VALUES)
    )
    cond = env.get_template("conditions.html").render(
        **ctx, conditions_content=render_master(cond_src, DUMMY_VALUES)
    )
    appx = env.get_template("appendix.html").render(**ctx)

    ref = html_escape(agreement.reference_number)
    running = (
        '<div class="running-header">'
        "<em>Bhatia General Contracting Co. L.L.C. (BGCC)</em>"
        "</div>"
        f'<span class="reference-anchor">{ref}</span>'
    )

    # Production assembly order (pdf_service.generate_agreement_pdf):
    # Cover -> Form -> Appendix -> Conditions. Match it so the preview is
    # representative of what BGCC reviewers actually see.
    combined = (
        '<html><head><meta charset="utf-8"></head><body>'
        f"{cover}{running}{form}"
        '<div class="page-break"></div>'
        f"{appx}"
        '<div class="page-break"></div>'
        f"{cond}"
        "</body></html>"
    )

    css = CSS(filename=str(TEMPLATES_DIR / "base_pdf.css"))
    # base_url so relative image refs (backend/templates/bhatia-logo.png)
    # resolve against the repo root the same way services.pdf_service does.
    pdf_bytes = HTML(string=combined, base_url=str(BACKEND_DIR.parent)).write_pdf(stylesheets=[css])
    OUT_PATH.write_bytes(pdf_bytes)

    pages = "?"
    info = subprocess.run(["pdfinfo", str(OUT_PATH)], capture_output=True, text=True)
    for line in info.stdout.splitlines():
        if line.startswith("Pages:"):
            pages = line.split(":", 1)[1].strip()
            break

    print(f"Wrote preview to {OUT_PATH} ({len(pdf_bytes):,} bytes, {pages} pages).")
    print("Open it with:")
    print(f"  xdg-open {OUT_PATH}")


if __name__ == "__main__":
    main()
