"""Optional Arabic diacritization (تشكيل) before TTS."""

from __future__ import annotations

import logging
import re
from functools import lru_cache

log = logging.getLogger("tts.diacritize")

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_WARNED_MISSING_BACKEND = False


@lru_cache(maxsize=1)
def _get_mishkal():
    from mishkal.tashkeel import TashkeelClass

    return TashkeelClass()


def _needs_diacritics(text: str) -> bool:
    if not _ARABIC_RE.search(text or ""):
        return False
    # Skip if text already has common diacritic marks.
    return not re.search(r"[\u064B-\u0652\u0670]", text)


def add_diacritics(text: str) -> str:
    """Return diacritized Arabic text, or the original on failure / non-Arabic input."""
    global _WARNED_MISSING_BACKEND

    raw = (text or "").strip()
    if not raw or not _needs_diacritics(raw):
        return text

    try:
        engine = _get_mishkal()
        return engine.tashkeel(raw)
    except ImportError:
        if not _WARNED_MISSING_BACKEND:
            log.warning(
                "TTS_DIACRITIZE=1 but mishkal is not installed. "
                "Install with: pip install mishkal"
            )
            _WARNED_MISSING_BACKEND = True
        return text
    except Exception as exc:
        log.warning("Arabic diacritization failed: %s", exc)
        return text
