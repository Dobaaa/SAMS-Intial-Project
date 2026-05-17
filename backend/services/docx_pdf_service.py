"""DOCX-based PDF rendering for SCA agreements.

Uses the BGCC-tuned master docx (backend/masters/sca_master_v1.docx) as
the source template. The master is already arranged so LibreOffice
renders it to exactly 42 pages (matching the BGCC source PDF) on a
system with Tahoma + Times New Roman + Arial + Georgia + Caladea
installed. Each agreement-specific spot in the master carries a
``{{FIELD_ID}}`` token (``{{F02}}``, ``{{C03}}``, ``{{A07}}``, etc.) that
this service substitutes with the agreement's stored values at render
time, then hands the populated docx to ``libreoffice --headless --convert-to
pdf``.

Token rules
-----------
* ``{{FIELD_ID}}`` — substituted with the agreement's stored value for
  that field. HTML escaping is unnecessary inside a docx (Word handles
  the encoding internally).
* If the field's input type is ``date``, the value is reformatted via
  ``_format_longdate`` to match Rev 01 item 1 ("05th May 2026").
* Tokens whose field is empty or unknown are replaced with an empty
  string (the surrounding text stays — e.g. "AED" suffix in an appendix
  cell stays put).
* Tokens that DON'T appear in the master are silently ignored.

Adding a new field to the master
--------------------------------
Edit ``backend/masters/sca_master_v1.docx`` in Word/LibreOffice and type
``{{F99}}`` (or whichever ID) anywhere the value should appear. Save.
That's it — no code change needed here.
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
MASTERS_DIR = BACKEND_DIR / "masters"
MASTER_DOCX = MASTERS_DIR / "sca_master_v1.docx"

# Field IDs whose values should be reformatted as a long-form date
# ("05th May 2026") at substitution time. The DB stores them as ISO
# strings; the master's tokens don't know that.
DATE_FIELDS: set[str] = {"F01", "A15"}

# Field IDs whose values are stored as raw numbers but should render
# with thousands separators + 2-dp decimals per Rev 01 items 11/12
# (e.g. F08 "8500000" -> "8,500,000.00"). Free-text values for these
# fields pass through unchanged so admin can still type "10% of F08"
# or similar qualifiers when needed.
MONEY_FIELDS: set[str] = {
    "F08",  # Subcontract Price
    "C03",  # Advance Payment Amount
    "C11",  # Rate of Liquidated Damages (AED/day)
    "A07",  # Subcontract Price (mirror)
    "A09",  # Advance Payment (mirror)
    "A10",  # Performance Security amount (mirror)
    "A20",  # Rate of LDs (mirror)
    "A21",  # Maximum LDs (10% default)
}

TOKEN_RE = re.compile(r"\{\{\s*([A-Z][0-9]+)\s*\}\}")


def _ordinal_suffix(day: int) -> str:
    if 10 <= (day % 100) <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _format_money(value: object) -> str:
    """Render a numeric value with thousands separators (and 2-dp decimals).

    Free-form text ("60 days PDC", an empty string, etc.) round-trips
    verbatim — the filter NEVER raises and is safe to chain anywhere.
    Mirrors pdf_service._format_money so the docx and (legacy) WeasyPrint
    pipelines agree on formatting.
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
        return f"{int(n):,}.00"  # Currency context: always show 2dp
    return f"{n:,.2f}"


def _format_longdate(value: object) -> str:
    """Render a date as ``05th May 2026``. Mirrors pdf_service helper."""
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
    for p in doc.paragraphs:
        yield p
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def _substitute_in_paragraph(para: Paragraph, values: dict[str, str]) -> bool:
    """Replace every ``{{FIELD_ID}}`` token in `para` with its value.

    Collapses run text into the first run so the substitution works even
    when Word split the token across multiple runs (which happens often
    if anyone edited the token after typing it). Loses per-run inline
    formatting within the modified spans — acceptable because tokens are
    plain text and the surrounding paragraph styling stays on run 0.
    """
    if not para.runs:
        return False
    full = "".join(r.text or "" for r in para.runs)
    if "{{" not in full:
        return False

    def replace_one(match: re.Match) -> str:
        field_id = match.group(1)
        raw = values.get(field_id, "")
        if not raw:
            return ""
        if field_id in DATE_FIELDS:
            return _format_longdate(raw)
        if field_id in MONEY_FIELDS:
            return _format_money(raw)
        return str(raw)

    new_text = TOKEN_RE.sub(replace_one, full)
    if new_text == full:
        return False
    para.runs[0].text = new_text
    for run in para.runs[1:]:
        run.text = ""
    return True


def render_agreement_docx_to_pdf(
    values: dict[str, str],
    output_dir: Path | str,
    *,
    master_path: Path | None = None,
    libreoffice_bin: str = "libreoffice",
    timeout_seconds: int = 90,
    accepted_revisions: list[tuple[str, str]] | None = None,
) -> bytes:
    """Render the SCA PDF by substituting tokens in the master docx and
    converting via LibreOffice headless.

    Parameters
    ----------
    values:
        ``{field_id: entered_value}`` for the agreement. Missing keys cause
        the corresponding token to render empty.
    output_dir:
        Working directory for the intermediate docx + LibreOffice output.
        Caller is responsible for cleanup.
    master_path:
        Override for the master docx location (defaults to the bundled
        ``backend/masters/sca_master_v1.docx``).
    accepted_revisions:
        Phase 4 v2.0 — list of ``(clause_hash, modified_text)`` pairs that
        replace the matching paragraphs in the master before token
        substitution. The modified_text is then itself put through token
        substitution, so it can reference fields the master uses
        (``{{F02}}``, etc.). Pending revisions are NOT applied here; in
        v2.2 they render as Word track-changes (<w:ins>/<w:del>).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = master_path or MASTER_DOCX
    if not source.exists():
        raise FileNotFoundError(f"Master docx not found at {source}")

    doc = Document(str(source))

    # 1) Apply accepted clause revisions BEFORE token substitution so the
    # modified text can contain {{FIELD_ID}} tokens and they'll resolve.
    if accepted_revisions:
        # Local import to keep the docx_pdf_service module free of the
        # revisions-service dependency unless caller actually passes
        # revisions in.
        from services.clause_revision_service import apply_accepted_revisions_to_doc

        apply_accepted_revisions_to_doc(doc, accepted_revisions)

    # 2) Token substitution.
    for para in _iter_paragraphs(doc):
        _substitute_in_paragraph(para, values)

    intermediate_docx = output_dir / "rendered.docx"
    doc.save(str(intermediate_docx))

    # LibreOffice insists on a writable "user installation" profile dir.
    # Without -env:UserInstallation it tries to create one under $HOME,
    # which fails when the process runs as a service user with /var/www
    # as its home.
    lo_profile = output_dir / "_lo_profile"
    lo_profile.mkdir(exist_ok=True)
    cmd = [
        libreoffice_bin,
        f"-env:UserInstallation=file://{lo_profile}",
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
