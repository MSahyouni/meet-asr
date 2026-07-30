"""Optional Arabic diacritization (تشكيل) before TTS."""

from __future__ import annotations

import logging
import re
from functools import lru_cache

log = logging.getLogger("tts.diacritize")

_ARABIC_LETTER_RE = re.compile(r"[\u0621-\u064A]")
_HARAKAT_RE = re.compile(r"[\u064B-\u0652\u0670]")
_WARNED_MISSING_BACKEND = False
# If at least this fraction of Arabic letters already carry a mark, trust the author.
_COVERAGE_TRUST = 0.45


@lru_cache(maxsize=1)
def _get_mishkal():
    from mishkal.tashkeel import TashkeelClass

    return TashkeelClass()


def _arabic_letter_count(text: str) -> int:
    return len(_ARABIC_LETTER_RE.findall(text or ""))


def diacritic_coverage(text: str) -> float:
    """Approximate share of Arabic letters that already have a following haraka."""
    raw = text or ""
    letters = _arabic_letter_count(raw)
    if letters <= 0:
        return 1.0
    # Count harakat; one letter may have shadda+vowel (2 marks) so cap at 1.0.
    marks = len(_HARAKAT_RE.findall(raw))
    return min(1.0, marks / float(letters))


def _needs_diacritics(text: str) -> bool:
    if _arabic_letter_count(text or "") <= 0:
        return False
    return diacritic_coverage(text) < _COVERAGE_TRUST


def add_diacritics(text: str) -> str:
    """
    Return diacritized Arabic text, or the original on failure / non-Arabic input.

    - If the author already provided rich tashkeel (e.g. story text), keep it.
    - Otherwise run mishkal sentence-by-sentence for stabler voweling than one huge pass.
    """
    global _WARNED_MISSING_BACKEND

    raw = (text or "").strip()
    if not raw or not _needs_diacritics(raw):
        if raw and diacritic_coverage(raw) >= _COVERAGE_TRUST:
            log.info("TTS diacritize: keeping author tashkeel (coverage=%.2f)", diacritic_coverage(raw))
        return text

    try:
        engine = _get_mishkal()
    except ImportError:
        if not _WARNED_MISSING_BACKEND:
            log.warning(
                "TTS_DIACRITIZE=1 but mishkal is not installed. "
                "Install with: pip install mishkal"
            )
            _WARNED_MISSING_BACKEND = True
        return text

    try:
        # Sentence-wise: mishkal is more reliable on short spans than full essays.
        parts = re.split(r"(?<=[.!?؟\n])\s+", raw)
        out: list[str] = []
        for part in parts:
            piece = part.strip()
            if not piece:
                continue
            if not _needs_diacritics(piece):
                out.append(piece)
                continue
            vocalized = engine.tashkeel(piece)
            out.append(vocalized if isinstance(vocalized, str) and vocalized.strip() else piece)
        result = " ".join(out).strip() or raw
        log.info(
            "TTS diacritize: mishkal applied (coverage %.2f → %.2f)",
            diacritic_coverage(raw),
            diacritic_coverage(result),
        )
        return result
    except Exception as exc:
        log.warning("Arabic diacritization failed: %s", exc)
        return text
