# tts/lang_detect.py — كشف اللغة للنص (لتفريق مسار Kokoro vs XTTS)
"""Lightweight language detection for TTS routing."""

# نطاق الحروف العربية (بما فيها الأرقام العربية، التشكيل، علامات الترقيم العربية)
_ARABIC_RANGES = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
)


def is_arabic(text: str) -> bool:
    """
    Return True if the text is predominantly Arabic.
    Uses Unicode block check; fast, no external deps.
    """
    if not text or not text.strip():
        return False
    t = text.strip()
    ar_count = 0
    letter_count = 0
    for c in t:
        cp = ord(c)
        if c.isspace() or not c.strip():
            continue
        letter_count += 1
        for lo, hi in _ARABIC_RANGES:
            if lo <= cp <= hi:
                ar_count += 1
                break
    if letter_count == 0:
        return False
    return ar_count / letter_count >= 0.3
