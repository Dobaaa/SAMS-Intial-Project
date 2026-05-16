"""DOCX-based PDF rendering for SCA agreements.

Uses the BGCC source `.docx` as the master template, substitutes the
agreement's field values directly into the document, and renders to PDF
via `libreoffice --headless --convert-to pdf`. This replaces the
WeasyPrint+HTML/CSS pipeline so the generated PDF is a near-pixel
replica of the BGCC source PDF (which was authored as a Word doc and
printed-to-PDF).

Why this exists: WeasyPrint and Microsoft Word are different layout
engines. Reproducing the source PDF's exact pagination, font metrics,
table styling, headers, footers, and list markers from HTML/CSS is
fundamentally not possible — the only way to a true replica is to feed
the source document itself to a Word-compatible renderer. LibreOffice
is the closest free option.

Substitution covers:
  - Cover page x-placeholders (Project / Subcontractor Name / Scope
    Title) — replaced positionally in document order.
  - "Day of 2026" date phrase in the Form preamble — F01.
  - 7 `[Insert X]` tokens in the Form section — F02..F08.
  - Appendix table cells (column 3) for ~20 A-field rows — looked up by
    the row's "Item Description" column matching SAMS' appendix_row_label.
  - Three legacy `(……Insert…..)` placeholders in Conditions — C01..C03.

Fields without a placeholder in the source docx (F09 Scope Title for
the form body, C04–C14 inline numbers, etc.) are silently skipped here;
they are still available via the Appendix table where they appear as
A-field row values.
"""
from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.table import _Cell
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
MASTERS_DIR = BACKEND_DIR / "masters"
MASTER_DOCX = MASTERS_DIR / "sca_master_v1.docx"

# Form-section [Insert ...] placeholders -> SAMS field IDs.
FORM_PLACEHOLDERS: dict[str, str] = {
    "[Insert Name]": "F02",
    "[Insert PO]": "F03",
    "[TL Nr.]": "F04",
    "[Insert Employer Name]": "F05",
    "[Insert Project Name / Details]": "F06",
    "[Insert Project Location]": "F07",
    "[Insert Amount]": "F08",
}

# Conditions-section legacy phrasings -> SAMS field IDs.
CONDITIONS_PLACEHOLDERS: dict[str, str] = {
    "(……Insert…..) Scope to be detailed here": "C01",
    "(……Insert…..) To Insert the Quantities Type": "C02",
    "(……Insert…..) UAE Dirhams": "C03",
}

# Cover-page xxxxxxx placeholders are positional. The first three
# occurrences in document order are Project / Subcontractor / Scope.
COVER_PLACEHOLDER = "x" * 39  # 39 x's exactly in the source
COVER_FIELD_ORDER: tuple[str, ...] = ("F06", "F02", "F09")

# Appendix table "Item Description" column -> SAMS A-field ID. The
# Information & Data column (column 3) for each matching row is rewritten
# to the SAMS-stored value. Rows not in this map keep whatever default
# text the source docx had (e.g. "Bhatia General Contracting Co. (L.L.C.)"
# for The Main Contractor, which is constant across all agreements).
APPENDIX_ROW_FIELD: dict[str, str] = {
    "The Subcontractor": "A01",
    "The Employer": "A02",
    "The Engineer/ Consultant/ Subconsultant": "A03",
    "The Project": "A04",
    "The Subcontract Price": "A07",
    "The Subcontract Quantities (Lump Sum or Re-measurable)": "A08",
    "Advance Payment Amount": "A09",
    "Advance Payment to be released by the Main Contractor": "A11",
    "Interim Payment to be paid by the Main Contractor": "A12",
    "1st Half of retention Money to be released by the Main Contractor": "A13",
    "2nd Half of retention Money to be released by the Main Contractor": "A14",
    "Commencement Date": "A15",
    "Time for Completion of the Project": "A16",
    "Time for Completion of the Subcontract Works": "A17",
    "Defects Liability Period": "A19",
    "Rate Of Liquidated Damages": "A20",
    "Time to submit the Copies of the required Insurance Policies": "A22",
    "Dispute Resolution (Jurisdiction)": "A23",
}

# F01 day-of-signing lives in the prose "made on the Day of 2026."
# Match flexibly so admin's edits to the master don't accidentally desync.
F01_DATE_RE = re.compile(r"made on\s+the\s+Day of\s+\d{4}\.")


def _ordinal_suffix(day: int) -> str:
    if 10 <= (day % 100) <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _format_longdate(value: object) -> str:
    """Render a date as ``05th May 2026`` (mirror of pdf_service helper)."""
    if value is None:
        return ""
    d: date | None = None
    if isinstance(value, datetime):
        d = value
    elif isinstance(value, date):
        d = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    return f"{d.day:02d}{_ordinal_suffix(d.day)} {d.strftime('%B')} {d.year}"


def _iter_paragraphs(doc) -> Iterable[Paragraph]:
    """Yield every paragraph in the document, including those nested in tables."""
    for p in doc.paragraphs:
        yield p
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def _replace_in_paragraph(para: Paragraph, old: str, new: str) -> bool:
    """Replace `old` with `new` inside a paragraph, even when the run boundaries
    split the placeholder. Returns True if a replacement happened."""
    if not para.runs:
        return False
    full = "".join(r.text or "" for r in para.runs)
    if old not in full:
        return False
    # Concatenate all run text into the first run, clear the rest. This loses
    # per-run formatting WITHIN the replaced spans but the source docx's
    # placeholders are plain text — there's no styled half to preserve.
    para.runs[0].text = full.replace(old, new)
    for run in para.runs[1:]:
        run.text = ""
    return True


def _replace_in_paragraph_regex(para: Paragraph, pattern: re.Pattern, replacement: str) -> bool:
    if not para.runs:
        return False
    full = "".join(r.text or "" for r in para.runs)
    if not pattern.search(full):
        return False
    para.runs[0].text = pattern.sub(replacement, full)
    for run in para.runs[1:]:
        run.text = ""
    return True


def _set_cell_text(cell: _Cell, text: str) -> None:
    """Rewrite a table cell's text, preserving the first paragraph's
    formatting (font, alignment) and dropping any extra paragraphs."""
    paragraphs = cell.paragraphs
    if not paragraphs:
        cell.add_paragraph(text)
        return
    first = paragraphs[0]
    # Drop subsequent paragraphs entirely.
    for extra in paragraphs[1:]:
        extra._element.getparent().remove(extra._element)
    if first.runs:
        first.runs[0].text = text
        for run in first.runs[1:]:
            run.text = ""
    else:
        first.add_run(text)


def render_agreement_docx_to_pdf(
    values: dict[str, str],
    output_dir: Path | str,
    *,
    master_path: Path | None = None,
    libreoffice_bin: str = "libreoffice",
    timeout_seconds: int = 90,
) -> bytes:
    """Render the SCA PDF by substituting values into the master docx and
    converting via LibreOffice headless.

    Parameters
    ----------
    values:
        ``{field_id: entered_value}`` for the agreement. Missing keys are
        treated as empty strings; the corresponding placeholders are left
        blank in the output.
    output_dir:
        Working directory for the intermediate docx + LibreOffice output.
        Caller is responsible for cleanup if they care.
    master_path:
        Override for the master docx location (defaults to the bundled
        ``backend/masters/sca_master_v1.docx``).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = master_path or MASTER_DOCX
    if not source.exists():
        raise FileNotFoundError(f"Master docx not found at {source}")

    doc = Document(str(source))

    # 1. Cover-page xxxxxxx placeholders, in document order.
    cover_idx = 0
    for para in _iter_paragraphs(doc):
        if cover_idx >= len(COVER_FIELD_ORDER):
            break
        fid = COVER_FIELD_ORDER[cover_idx]
        if _replace_in_paragraph(para, COVER_PLACEHOLDER, values.get(fid, "")):
            cover_idx += 1

    # 2. F01 ("the Day of 2026.") -> formatted long-date.
    f01_raw = values.get("F01", "")
    if f01_raw:
        replacement = f"made on {_format_longdate(f01_raw)}."
        for para in _iter_paragraphs(doc):
            if _replace_in_paragraph_regex(para, F01_DATE_RE, replacement):
                break  # only the first occurrence

    # 3. Form [Insert X] placeholders.
    for placeholder, fid in FORM_PLACEHOLDERS.items():
        value = values.get(fid, "")
        for para in _iter_paragraphs(doc):
            _replace_in_paragraph(para, placeholder, value)

    # 4. Conditions legacy (……Insert…..) phrasings.
    for placeholder, fid in CONDITIONS_PLACEHOLDERS.items():
        value = values.get(fid, "")
        for para in _iter_paragraphs(doc):
            _replace_in_paragraph(para, placeholder, value)

    # 5. Appendix tables — column 3 ("Information and Data") rewritten by
    #    row label lookup. Skip rows whose label isn't mapped (e.g. fixed
    #    rows like "The Main contractor").
    for tbl in doc.tables:
        for row in tbl.rows:
            if len(row.cells) < 3:
                continue
            label = row.cells[0].text.strip()
            fid = APPENDIX_ROW_FIELD.get(label)
            if not fid:
                continue
            value = values.get(fid, "").strip()
            if not value:
                continue
            _set_cell_text(row.cells[2], value)

    # 6. Save + convert via LibreOffice.
    intermediate_docx = output_dir / "rendered.docx"
    doc.save(str(intermediate_docx))

    cmd = [
        libreoffice_bin,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(intermediate_docx),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout_seconds)
    if proc.returncode != 0:
        raise RuntimeError(
            "LibreOffice conversion failed (rc=%d): %s"
            % (proc.returncode, proc.stderr.decode("utf-8", errors="replace"))
        )

    pdf_path = intermediate_docx.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError(
            f"LibreOffice reported success but no PDF at {pdf_path}; "
            f"stdout: {proc.stdout.decode('utf-8', errors='replace')[:500]}"
        )
    return pdf_path.read_bytes()
