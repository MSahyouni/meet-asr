# asr/docx_export.py — تصدير التفريغ والتلخيص إلى Word عبر Word COM
from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple

_log = logging.getLogger("asr.docx_export")

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
_PS1_SCRIPT = _REPO_ROOT / "scripts" / "word_com_export.ps1"


def _to_windows_path(path: pathlib.Path) -> str:
    """حوّل مسار Linux/WSL إلى مسار Windows يفهمه Word COM."""
    resolved = path.expanduser().resolve()
    if sys.platform == "win32":
        return str(resolved)
    wslpath = shutil.which("wslpath")
    if wslpath:
        try:
            out = subprocess.check_output(
                [wslpath, "-w", str(resolved)],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if out:
                return out
        except Exception:
            pass
    # fallback شائع لـ \\wsl.localhost\...
    posix = resolved.as_posix()
    if posix.startswith("/mnt/") and len(posix) > 6 and posix[5] == "/":
        drive = posix[5].upper()
        rest = posix[6:].replace("/", "\\")
        return f"{drive}:\\{rest}"
    return r"\\wsl.localhost\Ubuntu" + posix.replace("/", "\\")


def _find_powershell() -> Optional[str]:
    if sys.platform == "win32":
        for name in ("powershell.exe", "pwsh.exe"):
            found = shutil.which(name)
            if found:
                return found
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidate = pathlib.Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if candidate.exists():
            return str(candidate)
        return None
    for name in ("powershell.exe", "pwsh.exe"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "/mnt/c/Program Files/PowerShell/7/pwsh.exe",
    ):
        if pathlib.Path(candidate).exists():
            return candidate
    return None


def _write_via_win32com(
    title: str,
    lines: List[str],
    out_path: pathlib.Path,
    keywords: str = "",
) -> str:
    """مسار مباشر على Windows عبر pywin32 (Word.Application)."""
    import win32com.client  # type: ignore

    wd_format_xml_document = 12
    wd_align_right = 2
    wd_align_center = 1
    wd_reading_order_rtl = 1
    wd_collapse_end = 0

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Add()

        def add_rtl(text: str, *, bold: bool = False, size_pt: float = 12, align: int = wd_align_right) -> None:
            rng = doc.Content
            rng.Collapse(wd_collapse_end)
            if doc.Content.End > 1:
                rng.InsertParagraphAfter()
                rng = doc.Content
                rng.Collapse(wd_collapse_end)
            rng.Text = text or ""
            rng.Font.Name = "Arial"
            rng.Font.Size = size_pt
            rng.Font.Bold = bold
            rng.ParagraphFormat.ReadingOrder = wd_reading_order_rtl
            rng.ParagraphFormat.Alignment = align
            rng.LanguageID = 1025  # Arabic

        add_rtl(title, bold=True, size_pt=16, align=wd_align_center)
        body_lines = lines if lines else ["—"]
        for line in body_lines:
            add_rtl(line, size_pt=12)
        kw = (keywords or "").strip()
        if kw:
            add_rtl("", size_pt=12)
            add_rtl("الكلمات المفتاحية:", bold=True, size_pt=12)
            add_rtl(kw, size_pt=12)

        win_out = _to_windows_path(out_path)
        doc.SaveAs2(win_out, FileFormat=wd_format_xml_document)
        return str(out_path)
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        try:
            word.Quit()
        except Exception:
            pass


def _write_via_powershell_com(
    title: str,
    lines: List[str],
    out_path: pathlib.Path,
    keywords: str = "",
) -> str:
    """استدعاء Word COM عبر PowerShell (يعمل من Windows أو WSL)."""
    ps = _find_powershell()
    if not ps:
        raise RuntimeError(
            "PowerShell غير متاح لاستدعاء Word COM. ثبّت Microsoft Word على Windows."
        )
    if not _PS1_SCRIPT.exists():
        raise RuntimeError(f"سكربت Word COM غير موجود: {_PS1_SCRIPT}")

    payload = {
        "title": title or "",
        "lines": list(lines or []),
        "keywords": keywords or "",
        "out_path": _to_windows_path(out_path),
    }
    with tempfile.TemporaryDirectory(prefix="nabra_word_") as tmp:
        payload_path = pathlib.Path(tmp) / "payload.json"
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        win_payload = _to_windows_path(payload_path)
        win_script = _to_windows_path(_PS1_SCRIPT)
        cmd = [
            ps,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            win_script,
            "-PayloadPath",
            win_payload,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"Word COM failed: {detail or f'exit {proc.returncode}'}")
        if not out_path.exists() or out_path.stat().st_size <= 0:
            raise RuntimeError("Word COM انتهى دون إنشاء ملف .docx صالح")
        return str(out_path)


def write_docx_via_word_com(
    title: str,
    text: str,
    out_path: str | pathlib.Path,
    keywords: str = "",
) -> str:
    """
    اكتب مستند Word عبر محرك Word COM فقط.
    يفضّل win32com على Windows، وإلا PowerShell COM.
    """
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = (text or "").splitlines()
    # حاول win32com أولاً على Windows
    if sys.platform == "win32":
        try:
            return _write_via_win32com(title, lines, p, keywords=keywords)
        except ImportError:
            _log.info("pywin32 غير مثبت؛ الانتقال إلى PowerShell Word COM")
        except Exception as e:
            _log.warning("win32com Word failed (%s); trying PowerShell COM", e)
    return _write_via_powershell_com(title, lines, p, keywords=keywords)


def write_transcript_docx(text: str, out_path: str | pathlib.Path) -> str:
    """اكتب تفريغًا نصيًا كملف Word عبر Word COM."""
    return write_docx_via_word_com("تفريغ الاجتماع", text or "", out_path)


def write_summary_docx(
    summary: str,
    keywords: str = "",
    out_path: str | pathlib.Path = "",
) -> str:
    """اكتب ملخصًا (ومفاتيح اختيارية) كملف Word عبر Word COM."""
    return write_docx_via_word_com(
        "محضر الاجتماع",
        summary or "",
        out_path,
        keywords=keywords or "",
    )


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
    except Exception as e:
        _log.warning("summary Word COM export failed: %s", e)
        sum_docx_path = None
    return sum_txt_path, sum_docx_path
