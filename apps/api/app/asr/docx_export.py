# asr/docx_export.py — تصدير التفريغ والتلخيص إلى Word (.docx)
from __future__ import annotations

import pathlib
from typing import Optional, Tuple


def _docx_modules():
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt

    return Document, WD_ALIGN_PARAGRAPH, OxmlElement, qn, Pt


def _set_run_rtl(run, OxmlElement) -> None:
    rPr = run._r.get_or_add_rPr()
    rtl = OxmlElement("w:rtl")
    rPr.append(rtl)


def _set_paragraph_rtl(paragraph, WD_ALIGN_PARAGRAPH, OxmlElement, qn) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    pPr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    pPr.append(bidi)


def _add_rtl_paragraph(doc, text: str, mods, *, bold: bool = False, size_pt: float = 12) -> None:
    _Document, WD_ALIGN_PARAGRAPH, OxmlElement, qn, Pt = mods
    paragraph = doc.add_paragraph()
    _set_paragraph_rtl(paragraph, WD_ALIGN_PARAGRAPH, OxmlElement, qn)
    run = paragraph.add_run(text or "")
    run.bold = bold
    run.font.size = Pt(size_pt)
    run.font.name = "Arial"
    _set_run_rtl(run, OxmlElement)


def _new_rtl_document(title: str, mods):
    Document, _WD_ALIGN_PARAGRAPH, OxmlElement, qn, _Pt = mods
    doc = Document()
    section = doc.sections[0]
    sectPr = section._sectPr
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    sectPr.append(bidi)
    _add_rtl_paragraph(doc, title, mods, bold=True, size_pt=16)
    return doc


def write_transcript_docx(text: str, out_path: str | pathlib.Path) -> str:
    """اكتب تفريغًا نصيًا كملف Word بجانب مسار التفريغ."""
    mods = _docx_modules()
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = _new_rtl_document("تفريغ الاجتماع", mods)
    body = (text or "").strip()
    if body:
        for line in body.splitlines():
            _add_rtl_paragraph(doc, line, mods, size_pt=12)
    else:
        _add_rtl_paragraph(doc, "—", mods, size_pt=12)
    doc.save(p.as_posix())
    return str(p)


def write_summary_docx(
    summary: str,
    keywords: str = "",
    out_path: str | pathlib.Path = "",
) -> str:
    """اكتب ملخصًا (ومفاتيح اختيارية) كملف Word."""
    mods = _docx_modules()
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = _new_rtl_document("محضر الاجتماع", mods)
    body = (summary or "").strip()
    if body:
        for line in body.splitlines():
            _add_rtl_paragraph(doc, line, mods, size_pt=12)
    else:
        _add_rtl_paragraph(doc, "—", mods, size_pt=12)
    kw = (keywords or "").strip()
    if kw:
        doc.add_paragraph()
        _add_rtl_paragraph(doc, "الكلمات المفتاحية:", mods, bold=True, size_pt=12)
        _add_rtl_paragraph(doc, kw, mods, size_pt=12)
    doc.save(p.as_posix())
    return str(p)


def summary_docx_path_for(summary_txt_path: str | pathlib.Path) -> pathlib.Path:
    """transcript.summary.txt → transcript.summary.docx"""
    p = pathlib.Path(summary_txt_path)
    if p.name.endswith(".summary.txt"):
        return p.with_name(p.name[: -len(".summary.txt")] + ".summary.docx")
    return p.with_suffix(".docx")


def write_summary_artifacts(
    out_base_path: str | pathlib.Path,
    summary: str,
    keywords: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """
    اكتب .summary.txt و .summary.docx بجانب المسار الأساسي.
    يعيد (summary_txt_path, summary_docx_path).
    """
    base = pathlib.Path(out_base_path)
    sum_txt = base.with_suffix(".summary.txt")
    sum_docx = summary_docx_path_for(sum_txt)
    content = (summary or "").strip()
    if not content:
        return None, None
    kw = (keywords or "").strip()
    txt_body = content + (("\n\nالكلمات المفتاحية: " + kw) if kw else "")
    sum_txt_path: Optional[str] = None
    sum_docx_path: Optional[str] = None
    try:
        sum_txt.write_text(txt_body, encoding="utf-8")
        sum_txt_path = str(sum_txt)
    except Exception:
        sum_txt_path = None
    try:
        sum_docx_path = write_summary_docx(content, kw, sum_docx)
    except Exception:
        sum_docx_path = None
    return sum_txt_path, sum_docx_path
