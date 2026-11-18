"""Admin(3) client comments (SAMS Rev 02---18.5.2026.xlsx), master docx part.

1. Form: Second Party block formatted like First Party (blue bold-italic
   name, plain "having its postal address at P.O.", bold remainder; all
   Tahoma 10pt). First Party name bold too, per the client's target layout.
2. Witnesses table: room for signatures (tall first row, bottom-aligned)
   and a signing line after "Date:".
3. Consistent fonts: stray Times New Roman / Arial body runs (<= 11pt) fall
   back to the document's Tahoma; Form section 9pt runs bumped to 10pt.
4. Comms Address: Subcontractor block mirrors the Main Contractor block
   (Attention / Position Title / Address / Facsimile Number / Email Address).
6. Opening sentence, "BETWEEN First Party;", "AND Second Party." not bold.
5. Clause 2.2 "Scope of Works Details": hardcoded sample text -> {{C01}}.

Idempotent; writes ``.pre-admin3.bak`` on first run.
Run from backend/:  venv/bin/python -m scripts.apply_master_admin3_patch
"""
from __future__ import annotations

import shutil
from copy import deepcopy

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from services.docx_pdf_service import MASTER_DOCX

DOTS = "……………………………"


def _set(rpr, tag: str, val: str | None = None, on: bool = True):
    for e in rpr.findall(qn(tag)):
        rpr.remove(e)
    if on:
        e = OxmlElement(tag)
        if val is not None:
            e.set(qn("w:val"), val)
        rpr.append(e)


def _rpr(*, bold=False, italic=False, blue=False):
    rpr = OxmlElement("w:rPr")
    _set(rpr, "w:b", on=bold)
    _set(rpr, "w:i", on=italic)
    _set(rpr, "w:color", "0000FF", on=blue)
    _set(rpr, "w:sz", "20")
    _set(rpr, "w:szCs", "20")
    return rpr


def _rewrite(p, parts):
    """Replace paragraph p's runs with [(text, rpr), ...]."""
    for r in list(p.runs):
        p._p.remove(r._r)
    for text, rpr in parts:
        r = OxmlElement("w:r")
        r.append(rpr)
        for i, chunk in enumerate(text.split("\n")):
            if i:
                r.append(OxmlElement("w:br"))
            t = OxmlElement("w:t")
            t.set(qn("xml:space"), "preserve")
            t.text = chunk
            r.append(t)
        p._p.append(r)


def _para(doc, startswith: str):
    return next(p for p in doc.paragraphs if p.text.strip().startswith(startswith))


def fix_parties(doc) -> None:
    first = _para(doc, "M/s. Bhatia General Contracting")
    second_hdr = _para(doc, "AND Second Party")
    second = _para(doc, "{{F02}}, having")
    _rewrite(first, [
        ("M/s. Bhatia General Contracting Co. (L.L.C.)", _rpr(bold=True, italic=True, blue=True)),
        (" having its postal address at P.O. ", _rpr()),
        ("Box 6007, Dubai, U. A.", _rpr(bold=True)),
    ])
    _rewrite(second_hdr, [("AND Second Party.", _rpr(bold=True))])
    _rewrite(second, [
        ("{{F02}}", _rpr(bold=True, italic=True, blue=True)),
        (", having its postal address at P.O. ", _rpr()),
        ("Box {{F03}}, Dubai, U. A. E., and Trade\nLicence No. {{F04}} "
         "(hereinafter referred to as the “Subcontractor\")", _rpr(bold=True)),
    ])


def fix_parties_second(doc) -> None:
    """Second Party: forced break after "Trade" (client follow-up)."""
    p = _para(doc, "{{F02}}, having")
    _rewrite(p, [
        ("{{F02}}", _rpr(bold=True, italic=True, blue=True)),
        (", having its postal address at P.O. ", _rpr()),
        ("Box {{F03}}, Dubai, U. A. E., and Trade\nLicence No. {{F04}} "
         "(hereinafter referred to as the “Subcontractor\")", _rpr(bold=True)),
    ])


def fix_fonts(doc) -> None:
    body = doc.element.body
    for r in body.iter(qn("w:r")):
        rpr = r.find(qn("w:rPr"))
        if rpr is None:
            continue
        rf = rpr.find(qn("w:rFonts"))
        sz = rpr.find(qn("w:sz"))
        size = int(sz.get(qn("w:val"))) if sz is not None else None
        if rf is not None and rf.get(qn("w:ascii")) in ("Times New Roman", "Arial") and (size is None or 18 <= size <= 22):
            rpr.remove(rf)
    # Form section (FORM OF SUBCONTRACT AGREEMENT .. IN WITNESS WHEREOF): 9pt -> 10pt
    ps = doc.paragraphs
    els = [p._p for p in ps]  # python-docx wrappers are fresh objects; compare elements
    a = els.index(_para(doc, "FORM OF SUBCONTRACT AGREEMENT")._p)
    b = els.index(_para(doc, "IN WITNESS WHEREOF")._p)
    for p in ps[a : b + 1]:
        for r in p.runs:
            sz = r._r.find(f"{qn('w:rPr')}/{qn('w:sz')}")
            if sz is not None and sz.get(qn("w:val")) == "18":
                sz.set(qn("w:val"), "20")


def fix_witnesses(doc) -> None:
    tbl = next(t for t in doc.tables if "Estimation" in t.rows[0].cells[1].text)
    sig, date = tbl.rows
    sig._tr.get_or_add_trPr()
    h = sig._tr.trPr.find(qn("w:trHeight"))
    h.set(qn("w:val"), "1600")
    for cell in sig.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        _set(tcPr, "w:vAlign", "bottom")
        cell.paragraphs[0].runs[0].text = "(" + DOTS * 2 + ")"
    date._tr.trPr.find(qn("w:trHeight")).set(qn("w:val"), "700")
    for cell in date.cells:
        _set(cell._tc.get_or_add_tcPr(), "w:vAlign", "center")
        r = cell.paragraphs[0].runs[0]
        r.text = "Date:   ______________________"


def fix_comms_address(doc) -> None:
    cell = next(
        c for t in doc.tables for row in t.rows for c in row.cells[-1:]
        if "The Main Contractor Address" in c.text
    )
    p = next(p for p in cell.paragraphs if "The Subcontractor Address" in p.text)
    runs = p.runs
    plain = deepcopy(next(r for r in runs if r.text.startswith("Attention"))._r.find(qn("w:rPr")))
    bold = deepcopy(next(r for r in runs if r.text.startswith("The Subcontractor Address"))._r.find(qn("w:rPr")))
    keep = []
    for r in runs:
        if r.text.startswith(("Contact Person", "The Subcontractor Address", "{{A06}}")):
            break
        keep.append((r.text, deepcopy(r._r.find(qn("w:rPr")))))
    lines = [
        ("The Subcontractor Address\n", bold),
        ("Attention: {{SUBCONTRACTOR_CONTACT_PERSON}}\n", plain),
        (f"Position Title: {DOTS}\n", plain),
        ("Address: {{A06}}\n", plain),
        (f"Facsimile Number: {DOTS}\n", plain),
        ("Email Address: {{SUBCONTRACTOR_EMAIL}}", plain),
    ]
    for r in list(runs):
        p._p.remove(r._r)
    for text, rpr in keep + [(t, deepcopy(rp)) for t, rp in lines]:
        r = OxmlElement("w:r")
        if rpr is not None:
            r.append(rpr)
        chunks = text.split("\n")
        for i, chunk in enumerate(chunks):
            if i:
                r.append(OxmlElement("w:br"))
            if chunk:
                t = OxmlElement("w:t")
                t.set(qn("xml:space"), "preserve")
                t.text = chunk
                r.append(t)
        p._p.append(r)


def fix_scope(doc) -> None:
    p = _para(doc, "Supply, fabrication, surface treatment")
    runs = p.runs
    runs[0].text = "{{C01}}"
    for r in runs[1:]:
        p._p.remove(r._r)


def unbold_opening(doc) -> None:
    """Follow-up: opening sentence + party headers not bold (title stays bold)."""
    title = _para(doc, "FORM OF SUBCONTRACT AGREEMENT")
    _rewrite(title, [
        ("FORM OF SUBCONTRACT AGREEMENT ", _rpr(bold=True)),
        ("THIS SUBCONTRACT AGREEMENT is made on {{F01}}.", _rpr()),
    ])
    _rewrite(_para(doc, "BETWEEN First Party"), [("BETWEEN First Party;", _rpr())])
    _rewrite(_para(doc, "AND Second Party"), [("AND Second Party.", _rpr())])
    # First Party line breaks after "Box 6007," (client follow-up).
    _rewrite(_para(doc, "M/s. Bhatia General Contracting"), [
        ("M/s. Bhatia General Contracting Co. (L.L.C.)", _rpr(bold=True, italic=True, blue=True)),
        (" having its postal address at P.O. ", _rpr()),
        ("Box 6007,", _rpr(bold=True)),
    ])
    fix_parties_second(doc)
    # Second Party paragraph had right indent 1350 the First Party one lacks.
    _para(doc, "{{F02}}, having")._p.pPr.find(qn("w:ind")).set(qn("w:right"), "0")
    cont = next(p for p in doc.paragraphs if p.text.strip().startswith(("E. (hereinafter", "Dubai, U. A. E. (hereinafter")))
    _rewrite(cont, [('Dubai, U. A. E. (hereinafter referred to as the "Main Contractor" or "BGCC")', _rpr(bold=True))])


def main() -> None:
    bak = MASTER_DOCX.with_suffix(".docx.pre-admin3.bak")
    doc = Document(str(MASTER_DOCX))
    text = "\n".join(p.text for p in doc.paragraphs)
    if not bak.exists():
        shutil.copy2(MASTER_DOCX, bak)
    if "{{C01}}" not in text:
        fix_parties(doc)
        fix_witnesses(doc)
        fix_comms_address(doc)
        fix_scope(doc)
        fix_fonts(doc)
    unbold_opening(doc)  # idempotent
    doc.save(str(MASTER_DOCX))

    doc = Document(str(MASTER_DOCX))
    text = "\n".join(p.text for p in doc.paragraphs)
    cells = "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    assert "{{C01}}" in text and "Supply, fabrication, surface treatment" not in text
    assert "{{SUBCONTRACTOR_EMAIL}}" in cells and "Contact Person" not in cells
    print("patched", MASTER_DOCX)


if __name__ == "__main__":
    main()
