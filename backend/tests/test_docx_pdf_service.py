"""Unit tests for the docx substitution pipeline — no DB/HTTP/LibreOffice
needed, these exercise the OOXML manipulation directly."""

from __future__ import annotations

from docx import Document
from docx.oxml.ns import qn

from services.docx_pdf_service import _substitute_in_paragraph


def _run_highlights(paragraph) -> list[str | None]:
    """The w:highlight val (if any) of each run in a paragraph, in order."""
    highlights = []
    for run in paragraph.runs:
        rpr = run._r.find(qn("w:rPr"))
        highlight_el = rpr.find(qn("w:highlight")) if rpr is not None else None
        highlights.append(highlight_el.get(qn("w:val")) if highlight_el is not None else None)
    return highlights


def _make_paragraph(text: str):
    doc = Document()
    p = doc.add_paragraph(text)
    return doc, p


def test_highlight_off_by_default_no_highlight_added():
    doc, p = _make_paragraph("Boilerplate before {{X}} boilerplate after.")
    changed = _substitute_in_paragraph(p, {"X": "ADMIN VALUE"})
    assert changed is True
    assert p.text == "Boilerplate before ADMIN VALUE boilerplate after."
    assert all(h is None for h in _run_highlights(p))


def test_highlight_on_highlights_only_the_substituted_value():
    doc, p = _make_paragraph("Boilerplate before {{X}} boilerplate after.")
    changed = _substitute_in_paragraph(p, {"X": "ADMIN VALUE"}, highlight_admin_content=True)
    assert changed is True
    assert p.text == "Boilerplate before ADMIN VALUE boilerplate after."

    # Exactly one run should carry the red highlight background — the
    # substituted value — and it must be the "ADMIN VALUE" run, not the
    # boilerplate around it. Text color is untouched (stays black).
    runs_and_highlights = list(zip((r.text for r in p.runs), _run_highlights(p)))
    highlighted = [text for text, highlight in runs_and_highlights if highlight == "red"]
    assert highlighted == ["ADMIN VALUE"]
    for text, highlight in runs_and_highlights:
        if text != "ADMIN VALUE":
            assert highlight is None, f"boilerplate run {text!r} should not be highlighted"


def test_highlight_on_empty_value_no_visible_highlighted_text():
    """A blank field value substitutes to empty text. An empty run may still
    carry the highlight attribute internally, but nothing visible renders
    highlighted."""
    doc, p = _make_paragraph("Before {{X}} after.")
    _substitute_in_paragraph(p, {}, highlight_admin_content=True)
    assert p.text == "Before  after."
    for text, highlight in zip((r.text for r in p.runs), _run_highlights(p)):
        if text:
            assert highlight is None, f"non-empty run {text!r} should not be highlighted when value is blank"
