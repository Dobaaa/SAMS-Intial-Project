"""One-shot: convert the client SCA PDFs into seed HTML.

Reads the three reference PDFs in ``contract Pdfs/`` and emits clean
HTML into ``backend/seeds/form_master.html`` and
``conditions_master.html``. Page running-headers and page-N-of-M
footers are stripped, paragraphs are reflowed, numbered clause
headings are wrapped in semantic ``<h2>``/``<h3>`` tags, and the
"(……Insert…..)" placeholders the client used are converted into the
``{{FIELD_ID}}`` tokens the PDF render engine substitutes at PDF time.

Run once when the source PDFs change; commit the resulting HTML.
``seed_master_content.py`` then loads it into the DB on deploy.
"""
from __future__ import annotations

import re
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[2]
SEEDS_DIR = ROOT / "backend" / "seeds"
PDFS_DIR = ROOT / "contract Pdfs"

# Single consolidated source dropped by BGCC: 42 pages comprising
#   - p1   cover
#   - p2-4 Form of Subcontract Agreement
#   - p5-7 Appendix (rendered separately by templates/appendix.html, skip)
#   - p8-42 Conditions of the Subcontract Agreement (body)
# The earlier 01/02/03_*_03MAR2026.pdf split is superseded; keep this single
# file as the source of truth so future BGCC revisions only land in one place.
SOURCE_PDF = PDFS_DIR / "Full Set of Subcontract Agreement_05MAR2026.pdf"
FORM_PAGE_RANGE = range(2, 5)        # pages 2..4 inclusive (Form body)
# Conditions body starts at p12 of the Full Set — p8 is the section title,
# p9-11 are the TOC. Both are reconstructed elsewhere (section-title page
# is rendered by conditions.html, the TOC is implicit via h2/h3 headings).
CONDITIONS_PAGE_RANGE = range(12, 43)


# Heuristics --------------------------------------------------------------

PAGE_HEADER_PATTERNS = [
    re.compile(r"^Bhatia General Contracting Co\. L\.L\.C\. \(BGCC.*$", re.IGNORECASE),
    re.compile(r"^BGCC\s+P[- ]\S+\s*/\s*SCA#?-\S+\s+Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^Conditions of the Subcontract Agreement\s*$", re.IGNORECASE),
    re.compile(r"^Form of Subcontract Agreement\s*$", re.IGNORECASE),
    re.compile(r"^Appendix to the Subcontract Agreement\s*$", re.IGNORECASE),
]


HEADING_TOP_RE = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*\.{2,}\s*\d+\s*$")  # TOC line "1. General Provisions ....11"
TOC_SUB_RE = re.compile(r"^\s*\d+(\.\d+)+\.?\s+.+\.{2,}\s*\d+\s*$")  # TOC sub-line "1.1 Definitions ....11"
# Catch-all: any line that ends with a long dot-leader run followed by a
# page number (e.g. "10 Insurance, Indemnity, and Liability ....32"). This
# covers the top-level entries the two regexes above miss because they
# require an explicit "1." dot after the leading digit.
TOC_ANY_RE = re.compile(r".+\.{3,}\s*\d+\s*$")

# Top-level section headings come in two variants:
#   (a) Conditions PDF: ``1 General Provisions:`` (no period after the digit,
#       ends with ``:`` or just the title)
#   (b) Form PDF:       ``1. The Subcontract Agreement;`` (period after digit,
#       ends with ``;`` or ``:``)
# We do NOT promote ``1. The Form of Subcontract Agreement,`` (period +
# trailing comma) to h2 — those are sub-list items inside a body paragraph
# and should render at body weight.
H2_NODOT_RE = re.compile(r"^\s*(\d{1,2})\s+([A-Z][^\n]+?:?)\s*$")
H2_DOT_RE = re.compile(r"^\s*(\d{1,2})\.\s+([A-Z][^\n]+?[;:])\s*$")
H3_RE = re.compile(r"^\s*(\d+\.\d+)\.?\s+(.+?)\s*$")
H4_RE = re.compile(r"^\s*(\d+\.\d+\.\d+)\.?\s+(.+?)\s*$")

LIST_LETTER_RE = re.compile(r"^\s*([a-z])\)\s+(.*)$")  # a) ...
LIST_ROMAN_RE = re.compile(r"^\s*([ivx]+)\.\s+(.*)$", re.IGNORECASE)  # i. ...

# The source PDF uses ``(……Insert…..)`` (sometimes with a stray space inside
# the ellipsis run) as an inline blank. We first normalize all variants to a
# single canonical ``__INS__`` sentinel, then walk a list of context-anchored
# substitutions to map each blank to the right ``{{Cxx}}`` token. This is
# brittle by nature — every BGCC template revision needs the anchor strings
# re-checked. Run the script, eyeball remaining ``(……Insert…..)`` in the
# output, and patch CONTEXT_SUBS until it's empty.
# The source PDF mixes the horizontal-ellipsis character (U+2026) with plain
# ASCII dots inside the same blank — e.g. "(…… Insert…..)" is two U+2026,
# then "Insert", then one U+2026 + two ``.``. Match any combination of dots
# and ellipses.
INS_NORMALIZE = re.compile(r"\(\s*[…\.]+\s*Insert\s*[…\.]+\s*\)", re.UNICODE)


# (search_re, replacement_template) — replacements in document order. The
# search regex is matched against the joined paragraph; the matched text is
# replaced verbatim, so the ``__INS__`` sentinel inside it disappears.
CONTEXT_SUBS: list[tuple[re.Pattern[str], str]] = [
    # Scope of Works detail (C01) — phrase is ``__INS__ Scope to be detailed here``.
    (re.compile(r"__INS__\s*Scope to be detailed here", re.UNICODE), "{{C01}}"),
    # Quantities type (C02).
    (re.compile(r"__INS__\s*To Insert the Quantities Type", re.UNICODE), "{{C02}}"),
    # Advance Payment Amount (C03) — "advance payment equal to __INS__ UAE Dirhams".
    (re.compile(r"equal to __INS__ UAE Dirhams", re.UNICODE), "equal to {{C03}} UAE Dirhams"),
    # Advance Payment release condition (C04) — first "released ... within __INS__"
    # under 3.4.1. The Conditions PDF separates this with extra text.
    (re.compile(r"and within __INS__\b", re.UNICODE), "and within {{C04}}"),
    # Interim Payment days (C05) — "within __INS__ days from the date of actual receipt".
    (re.compile(r"within __INS__ days from the date of actual receipt", re.UNICODE), "within {{C05}} days from the date of actual receipt"),
    # 1st Half retention (C06).
    (re.compile(r"First instalment \(5%\) to be released within __INS__ days", re.UNICODE), "First instalment (5%) to be released within {{C06}} days"),
    # 2nd Half retention (C07).
    (re.compile(r"Second instalment \(5%\) to be released __INS__ days", re.UNICODE), "Second instalment (5%) to be released {{C07}} days"),
    # Time for Completion (C08).
    (re.compile(r"__INS__ from the Commencement Date or by __INS__", re.UNICODE), "{{C08}} from the Commencement Date or by [Date]"),
    # Defects Liability Period (C10) — "__INS__ Months".
    (re.compile(r"__INS__\s*Months", re.UNICODE), "{{C10}} Months"),
    # Liquidated Damages rate (C11).
    (re.compile(r"the rate of __INS__ UAE per calendar day", re.UNICODE), "the rate of {{C11}} UAE per calendar day"),
    # Insurance submission deadline (C12).
    (re.compile(r"within __INS__ from the Commencement Date submit", re.UNICODE), "within {{C12}} from the Commencement Date submit"),
    # Dispute Resolution Jurisdiction (C13).
    (re.compile(r"finally and exclusively settled by __INS__", re.UNICODE), "finally and exclusively settled by {{C13}}"),
]


# Form-cover placeholders (separate map because the Form PDF uses ``[Insert X]``
# brackets rather than the ``(……Insert…..)`` blanks).
FORM_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"the____________Day of 2026", re.UNICODE), "{{F01}}"),
    (re.compile(r"\[Insert Name\]", re.UNICODE), "{{F02}}"),
    (re.compile(r"P\.O\.\s*Box\s+\[Insert PO\]", re.UNICODE), "P.O. Box {{F03}}"),
    (re.compile(r"\[TL Nr\.\]", re.UNICODE), "{{F04}}"),
    (re.compile(r"\[Insert Employer Name\]", re.UNICODE), "{{F05}}"),
    (re.compile(r"\[Insert Project Name / Details\]", re.UNICODE), "{{F06}}"),
    (re.compile(r"\[Insert Project Location\]", re.UNICODE), "{{F07}}"),
    (re.compile(r"\[Insert Amount\]", re.UNICODE), "{{F08}}"),
]


def _strip_page_headers(raw_lines: list[str]) -> list[str]:
    kept: list[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            kept.append("")  # blank-line marker
            continue
        if any(pat.match(stripped) for pat in PAGE_HEADER_PATTERNS):
            continue
        kept.append(stripped)
    return kept


def _drop_toc(lines: list[str]) -> list[str]:
    """Drop the table-of-contents lines (anything with ``....`` dots)."""
    return [
        ln
        for ln in lines
        if not (TOC_SUB_RE.match(ln) or HEADING_TOP_RE.match(ln) or TOC_ANY_RE.match(ln))
    ]


def _apply_placeholder_subs(text: str) -> str:
    """Normalize ``(……Insert…..)`` variants then run context-anchored subs.

    Form-cover ``[Insert X]`` substitutions also run here so a single helper
    handles both PDFs.
    """
    # 1. Normalize every "(……Insert…..)" variant to a single sentinel so the
    #    context regexes below don't need to enumerate spacing/ellipsis runs.
    text = INS_NORMALIZE.sub("__INS__", text)

    # 2. Context-anchored substitutions (Conditions PDF inline blanks).
    for pat, repl in CONTEXT_SUBS:
        text = pat.sub(repl, text)

    # 3. Form-cover brackets.
    for pat, repl in FORM_SUBS:
        text = pat.sub(repl, text)

    # 4. Leftover sentinels stay as visible "(……Insert…..)" so admin can
    #    spot un-mapped blanks in the rendered PDF and tell us about them.
    text = text.replace("__INS__", "(……Insert…..)")
    return text


def _classify_line(line: str) -> tuple[str, str]:
    """Classify a logical line as ('h2'/'h3'/'h4'/'a)'/'i.'/'standalone'/'p', payload)."""
    if not line.strip():
        return "blank", ""
    if _is_standalone_heading(line):
        return "standalone", line.strip()
    m = H4_RE.match(line)
    if m:
        num, title = m.group(1), m.group(2).strip()
        if 2 <= len(num.split(".")) <= 3 and title and title[0].isalpha() and len(title) < 60:
            return "h4", f"{num} {title}"
    m = H3_RE.match(line)
    if m:
        num, title = m.group(1), m.group(2).strip()
        # Only treat as h3 if the title is short (real heading, not a
        # wrapping list item like "3.7 Annexures for any addendums...").
        if num.count(".") == 1 and title and title[0].isupper() and len(title) < 60:
            return "h3", f"{num} {title}"
    m = H2_NODOT_RE.match(line)
    if m:
        num, title = m.group(1), m.group(2).strip()
        if title and title[0].isupper() and len(title) < 80:
            return "h2", f"{num} {title}"
    m = H2_DOT_RE.match(line)
    if m:
        num, title = m.group(1), m.group(2).strip()
        if title and title[0].isupper() and len(title) < 80:
            return "h2", f"{num}. {title}"
    if LIST_LETTER_RE.match(line):
        return "a", line.strip()
    if LIST_ROMAN_RE.match(line):
        return "i", line.strip()
    return "p", line.strip()


def _html_escape(text: str) -> str:
    # Minimal — preserve our {{FIELD}} tokens through escaping.
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _is_standalone_heading(line: str) -> bool:
    """Short all-caps lines (e.g. ``PREAMBLE``) are standalone headings.

    They get a paragraph-break before *and* after themselves so the
    rendered PDF gives them their own line in the body.
    """
    stripped = line.strip()
    if not stripped:
        return False
    # Allow at most 3 words and at most 22 chars.
    if len(stripped) > 22 or len(stripped.split()) > 3:
        return False
    return stripped.isupper() and any(c.isalpha() for c in stripped)


def _is_paragraph_terminator(line: str) -> bool:
    """Heuristic: does this line plausibly end a paragraph?

    Source PDF wraps long paragraphs across multiple visual lines but the
    text extractor doesn't insert blank-line markers between paragraphs.
    We need to infer them. A line terminates a paragraph when it ends
    with a sentence-final punctuation mark *and* it's a "short" line
    (i.e., the legal text concluded before the right margin). Lines that
    end with a comma or a wrap-mid-word never terminate a paragraph.

    We treat ``)``, ``."``, ``.``, ``;`` and ``:`` as sentence-final.
    """
    stripped = line.rstrip()
    if not stripped:
        return False
    # Long lines (close to right margin) are almost always wrap-of-paragraph,
    # never paragraph-final. The Form/Conditions PDF wraps around char 95-100.
    if len(stripped) > 95:
        return False
    last = stripped[-1]
    return last in {".", ";", ":", ")", "”", '"', "”", "?", "!"}


def _starts_new_paragraph(line: str) -> bool:
    """Heuristic: does this line plausibly start a new paragraph?

    A line that begins with a capital letter and isn't continuing a list
    item is a fresh paragraph if the previous line terminated. We also
    treat lines starting with "(", "[", or "{{" (placeholders) as fresh
    paragraphs because admin-inserted fields tend to lead a sentence.
    """
    stripped = line.lstrip()
    if not stripped:
        return False
    first = stripped[0]
    if first.isupper():
        return True
    if first in {"(", "[", "{"}:
        return True
    return False


def _build_html(lines: list[str]) -> str:
    """Walk classified lines and emit semantic HTML.

    Continuation lines (plain paragraph text following an ``a)`` / ``i.``
    item with no intervening blank line) are appended to the current list
    item rather than spawning a separate paragraph. A blank line closes
    the current list item; a fresh ``a)`` / ``i.`` / heading also closes
    it. This keeps multi-line list items legally coherent.

    Paragraph breaks WITHIN body text are inferred via
    ``_is_paragraph_terminator`` + ``_starts_new_paragraph`` since the
    source PDF doesn't emit blank lines between paragraphs.
    """
    out: list[str] = []
    paragraph_buf: list[str] = []
    pending_li_buf: list[str] = []
    pending_li_kind: str = ""  # "" | "letter" | "roman"
    in_letter_list = False
    in_roman_list = False

    def flush_paragraph() -> None:
        nonlocal paragraph_buf
        if paragraph_buf:
            joined = " ".join(paragraph_buf).strip()
            if joined:
                out.append(f"<p>{_html_escape(_apply_placeholder_subs(joined))}</p>")
            paragraph_buf = []

    def flush_li() -> None:
        nonlocal pending_li_buf, pending_li_kind
        if pending_li_buf:
            joined = " ".join(pending_li_buf).strip()
            if joined:
                out.append(f"<li>{_html_escape(_apply_placeholder_subs(joined))}</li>")
            pending_li_buf = []
            pending_li_kind = ""

    def close_letter_list() -> None:
        nonlocal in_letter_list
        flush_li()
        if in_letter_list:
            out.append("</ol>")
            in_letter_list = False

    def close_roman_list() -> None:
        nonlocal in_roman_list
        flush_li()
        if in_roman_list:
            out.append("</ol>")
            in_roman_list = False

    for raw in lines:
        kind, payload = _classify_line(raw)

        if kind == "blank":
            flush_paragraph()
            flush_li()
            continue

        if kind == "standalone":
            flush_paragraph()
            close_letter_list()
            close_roman_list()
            out.append(
                f"<p class=\"standalone-heading\">{_html_escape(payload)}</p>"
            )
            continue

        if kind in ("h2", "h3", "h4"):
            flush_paragraph()
            close_letter_list()
            close_roman_list()
            tag = kind
            out.append(f"<{tag} class=\"clause-{tag}\">{_html_escape(payload)}</{tag}>")
            continue

        if kind == "a":
            flush_paragraph()
            flush_li()  # close previous letter-item if any
            close_roman_list()
            if not in_letter_list:
                out.append('<ol class="letter-list" type="a">')
                in_letter_list = True
            body = LIST_LETTER_RE.match(payload).group(2)
            pending_li_buf = [body]
            pending_li_kind = "letter"
            continue

        if kind == "i":
            flush_paragraph()
            flush_li()  # close previous roman-item if any
            close_letter_list()
            if not in_roman_list:
                out.append('<ol class="roman-list" type="i">')
                in_roman_list = True
            body = LIST_ROMAN_RE.match(payload).group(2)
            pending_li_buf = [body]
            pending_li_kind = "roman"
            continue

        # Plain paragraph line. If we're mid-list-item, this is a continuation
        # of that item (PDF wrapped it across visual lines). Otherwise it
        # belongs to the running paragraph. Within a running paragraph we
        # infer paragraph breaks via terminator+starter heuristics because
        # the source PDF doesn't emit blank lines between paragraphs.
        if pending_li_buf:
            prev = pending_li_buf[-1] if pending_li_buf else ""
            if _is_paragraph_terminator(prev) and _starts_new_paragraph(payload):
                # End the list item here and start a new paragraph beneath it.
                flush_li()
                close_letter_list()
                close_roman_list()
                paragraph_buf.append(payload)
            else:
                pending_li_buf.append(payload)
        else:
            close_letter_list()
            close_roman_list()
            prev = paragraph_buf[-1] if paragraph_buf else ""
            if _is_paragraph_terminator(prev) and _starts_new_paragraph(payload):
                flush_paragraph()
            paragraph_buf.append(payload)

    flush_paragraph()
    close_letter_list()
    close_roman_list()
    return "\n".join(out)


def _extract_pdf(pdf_path: Path, page_range: range) -> list[str]:
    """Return the cleaned-up logical lines from ``pdf_path`` for the given
    1-based page range (inclusive on both ends).

    Uses pypdfium2 (the official PDFium binding) because the source PDFs
    rely on font ligatures (``ti`` → glyph) that pdfplumber and
    pdfminer.six mis-decode as the literal capital ``E`` — producing
    nonsense like ``execuEon`` / ``Emely`` / ``compleEon``. pypdfium2
    walks the proper ToUnicode tables and decodes the ligatures back to
    ``ti``, yielding clean ``execution`` / ``timely`` / ``completion``.
    """
    raw_lines: list[str] = []
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        for one_based in page_range:
            idx = one_based - 1
            if idx < 0 or idx >= len(doc):
                continue
            page = doc[idx]
            textpage = page.get_textpage()
            text = textpage.get_text_range() or ""
            textpage.close()
            page.close()
            raw_lines.extend(text.splitlines())
            raw_lines.append("")  # page break is a paragraph break
    finally:
        doc.close()
    cleaned = _strip_page_headers(raw_lines)
    cleaned = _drop_toc(cleaned)
    return cleaned


# Signature + witness block that follows the "IN WITNESS WHEREOF" line in
# the Form. The source PDF renders this as a 2-column table with labelled
# signature lines and a stamp box per side, then a separate Witnesses
# table with two BGCC witnesses. Drop in verbatim after the extracted
# Form text replaces the merged-prose version pypdfium2 produces.
SIGNATURE_BLOCK_HTML = """
<table class="signature-block">
  <thead>
    <tr>
      <th>For and on behalf of the Main Contractor (BGCC)</th>
      <th>For and on behalf of the Sub-Contractor</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <p>Name: ________________________________</p>
        <p>Designation: ___________________________</p>
        <p>Date: _________________________________</p>
        <p class="stamp-box">Main Contractor Company Stamp</p>
      </td>
      <td>
        <p>Name: ________________________________</p>
        <p>Designation: ___________________________</p>
        <p>Date: _________________________________</p>
        <p class="stamp-box">Subcontractor Company Stamp</p>
      </td>
    </tr>
  </tbody>
</table>

<p class="witness-label">Witnesses:</p>
<table class="witness-block">
  <tbody>
    <tr>
      <td>
        <p>(&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;.)<br>Operation Manager - BGCC</p>
        <p>Date: _____________________</p>
      </td>
      <td>
        <p>(&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;.)<br>Estimation Manager - BGCC</p>
        <p>Date: _____________________</p>
      </td>
    </tr>
  </tbody>
</table>
"""


def _inject_form_signature_block(html: str) -> str:
    """Replace everything after the IN WITNESS WHEREOF paragraph with the
    hardcoded signature block (since pypdfium2 collapses the source's
    visual 2-col table into mashed inline prose).

    Safe no-op if the marker isn't found (e.g. once admin edits the Form
    via the Masters UI and rewords the witness paragraph).
    """
    marker = "IN WITNESS WHEREOF"
    idx = html.find(marker)
    if idx == -1:
        return html
    # Keep everything up to AND INCLUDING the </p> of the IN WITNESS paragraph.
    end_p = html.find("</p>", idx)
    if end_p == -1:
        return html
    head = html[: end_p + len("</p>")]
    return head + "\n" + SIGNATURE_BLOCK_HTML.strip() + "\n"


def main() -> None:
    SEEDS_DIR.mkdir(exist_ok=True)

    if not SOURCE_PDF.exists():
        raise FileNotFoundError(
            f"Source PDF not found: {SOURCE_PDF}. Place the BGCC 'Full Set' PDF "
            "(p1 cover / p2-4 Form / p5-7 Appendix / p8-42 Conditions) there."
        )

    # ===== Conditions (pages 8-42 of the Full Set) =====
    # Cover (p1) is rebuilt by templates/cover_page.html. Form (p2-4) is
    # emitted to form_master.html. Appendix (p5-7) is rendered server-side
    # by templates/appendix.html from agreement field values, so we skip
    # extracting it here — extracting risks divergence between the seeded
    # snapshot and the live per-agreement appendix render.
    print(f"→ extracting Conditions (pages {CONDITIONS_PAGE_RANGE.start}-{CONDITIONS_PAGE_RANGE.stop - 1} of Full Set)")
    cond_lines = _extract_pdf(SOURCE_PDF, CONDITIONS_PAGE_RANGE)
    cond_html_body = _build_html(cond_lines)
    cond_html = (
        '<h1 class="doc-title">CONDITIONS OF THE SUBCONTRACT AGREEMENT</h1>\n'
        + cond_html_body
        + "\n"
    )
    (SEEDS_DIR / "conditions_master.html").write_text(cond_html, encoding="utf-8")
    print(f"  wrote {len(cond_html)} chars → {SEEDS_DIR / 'conditions_master.html'}")

    # ===== Form (pages 2-4 of the Full Set) =====
    # Entire Form is rendered legal text. Signature/witness block at the
    # bottom of the Form is kept as static furniture; only {{F01}} signing
    # date on the cover page is dynamic, and that's substituted by the
    # placeholder map below.
    print(f"→ extracting Form (pages {FORM_PAGE_RANGE.start}-{FORM_PAGE_RANGE.stop - 1} of Full Set)")
    form_lines = _extract_pdf(SOURCE_PDF, FORM_PAGE_RANGE)
    form_html_body = _build_html(form_lines)
    form_html = (
        '<h1 class="doc-title">FORM OF SUBCONTRACT AGREEMENT</h1>\n'
        + form_html_body
        + "\n"
    )
    form_html = _inject_form_signature_block(form_html)
    (SEEDS_DIR / "form_master.html").write_text(form_html, encoding="utf-8")
    print(f"  wrote {len(form_html)} chars → {SEEDS_DIR / 'form_master.html'}")

    print("\nDone. Review the generated HTML, commit it, then re-deploy.")
    print("seed_master_content.py will overwrite the active master_templates rows.")


if __name__ == "__main__":
    main()
