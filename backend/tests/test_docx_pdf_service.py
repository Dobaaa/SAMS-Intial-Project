"""Unit tests for the docx substitution pipeline — no DB/HTTP/LibreOffice
needed, these exercise the OOXML manipulation directly."""

from __future__ import annotations

from docx import Document
from docx.oxml.ns import qn

from services.docx_pdf_service import _substitute_in_paragraph


def _run_colors(paragraph) -> list[str | None]:
    """The w:color val (if any) of each run in a paragraph, in order."""
    colors = []
    for run in paragraph.runs:
        rpr = run._r.find(qn("w:rPr"))
        color_el = rpr.find(qn("w:color")) if rpr is not None else None
        colors.append(color_el.get(qn("w:val")) if color_el is not None else None)
    return colors


def _make_paragraph(text: str):
    doc = Document()
    p = doc.add_paragraph(text)
    return doc, p


def test_highlight_off_by_default_no_color_added():
    doc, p = _make_paragraph("Boilerplate before {{X}} boilerplate after.")
    changed = _substitute_in_paragraph(p, {"X": "ADMIN VALUE"})
    assert changed is True
    assert p.text == "Boilerplate before ADMIN VALUE boilerplate after."
    assert all(c is None for c in _run_colors(p))


def test_highlight_on_colors_only_the_substituted_value():
    doc, p = _make_paragraph("Boilerplate before {{X}} boilerplate after.")
    changed = _substitute_in_paragraph(p, {"X": "ADMIN VALUE"}, highlight_admin_content=True)
    assert changed is True
    assert p.text == "Boilerplate before ADMIN VALUE boilerplate after."

    # Exactly one run should carry the red color — the substituted value —
    # and it must be the "ADMIN VALUE" run, not the boilerplate around it.
    runs_and_colors = list(zip((r.text for r in p.runs), _run_colors(p)))
    colored = [text for text, color in runs_and_colors if color == "FF0000"]
    assert colored == ["ADMIN VALUE"]
    for text, color in runs_and_colors:
        if text != "ADMIN VALUE":
            assert color is None, f"boilerplate run {text!r} should not be colored"


def test_highlight_on_empty_value_no_visible_colored_text():
    """A blank field value substitutes to empty text. An empty run may still
    carry the color attribute internally, but nothing visible renders red."""
    doc, p = _make_paragraph("Before {{X}} after.")
    _substitute_in_paragraph(p, {}, highlight_admin_content=True)
    assert p.text == "Before  after."
    for text, color in zip((r.text for r in p.runs), _run_colors(p)):
        if text:
            assert color is None, f"non-empty run {text!r} should not be colored when value is blank"
