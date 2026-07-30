# tts/text_utils.py — Arabic text preprocessing for TTS (conservative, no heavy deps)
"""Minimal Arabic text preprocessing before TTS synthesis."""

import re

# Arabic number words 0-99
_ONES = ["صفر", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]
_TENS = ["", "عشرة", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون"]
_TEENS = ["عشرة", "إحدى عشرة", "اثنا عشر", "ثلاث عشرة", "أربع عشرة", "خمس عشرة", "ست عشرة", "سبع عشرة", "ثمان عشرة", "تسع عشرة"]
_HUNDREDS = ["", "مائة", "مائتان", "ثلاثمائة", "أربعمائة", "خمسمائة", "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]
_THOUSANDS = ["", "ألف", "ألفان", "ثلاثة آلاف", "أربعة آلاف", "خمسة آلاف", "ستة آلاف", "سبعة آلاف", "ثمانية آلاف", "تسعة آلاف"]


def normalize_arabic(text: str) -> str:
    """
    Minimal Arabic normalization for TTS.
    Keep alef maqsura (ى) as-is — converting it to ي makes TTS say /i/ instead of /a/
    (e.g. على → علي, موسى → موسي).
    Only strip tatweel (ـ) which has no phonetic value.
    """
    if not text:
        return text
    return text.replace("\u0640", "")  # tatweel


# Harakat / Quranic marks Habibi-F5 often treats as speakable tokens (not vowel hints).
_ARABIC_DIACRITICS_RE = re.compile(
    r"[\u064B-\u065F\u0670\u06D6-\u06ED\u08F0-\u08FF]"
)


def strip_arabic_diacritics(text: str) -> str:
    """Remove tashkeel so engines that can't use it don't read marks as letters."""
    if not text:
        return text
    return _ARABIC_DIACRITICS_RE.sub("", text)


def cleanup_punctuation(text: str) -> str:
    """Ensure pauses for Arabic punctuation: ، . ! ؟"""
    if not text:
        return text
    # Ensure space after common punctuation for natural pauses
    t = re.sub(r"([،.!؟])([^\s])", r"\1 \2", text)
    t = re.sub(r"([،.!؟])\s+", r"\1 ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def split_text_for_tts(text: str, max_chunk_chars: int = 220) -> list[str]:
    """
    Split long text into sentence-like chunks for better TTS quality.
    Designed for Arabic punctuation with conservative fallback.
    """
    if not text:
        return []
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= max_chunk_chars:
        return [text]

    pieces = re.split(r"(?<=[\.\!\?؟،؛:])\s+", text)
    chunks: list[str] = []
    current = ""

    for piece in pieces:
        sentence = piece.strip()
        if not sentence:
            continue
        if len(sentence) > max_chunk_chars:
            words = sentence.split(" ")
            part = ""
            for word in words:
                candidate = f"{part} {word}".strip()
                if len(candidate) <= max_chunk_chars:
                    part = candidate
                    continue
                if part:
                    chunks.append(part)
                part = word
            if part:
                chunks.append(part)
            continue

        candidate = f"{current} {sentence}".strip()
        if not current or len(candidate) <= max_chunk_chars:
            current = candidate
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def _num_to_ar_0_99(n: int) -> str:
    """Convert 0-99 to Arabic words."""
    if n < 0 or n > 99:
        return str(n)
    if n < 10:
        return _ONES[n]
    if n < 20:
        return _TEENS[n - 10]
    ones = n % 10
    tens = n // 10
    if ones == 0:
        return _TENS[tens]
    return _ONES[ones] + " و" + _TENS[tens]


def _num_to_ar_100_999(n: int) -> str:
    """Convert 100-999 to Arabic words."""
    if n < 100 or n > 999:
        return str(n)
    h = n // 100
    rest = n % 100
    if rest == 0:
        return _HUNDREDS[h]
    return _HUNDREDS[h] + " و" + _num_to_ar_0_99(rest)


def _num_to_ar_1000_9999(n: int) -> str:
    """Convert 1000-9999 to Arabic words."""
    if n < 1000 or n > 9999:
        return str(n)
    th = n // 1000
    rest = n % 1000
    if rest == 0:
        return _THOUSANDS[th]
    rest_str = _num_to_ar_100_999(rest) if rest >= 100 else _num_to_ar_0_99(rest)
    return _THOUSANDS[th] + " و" + rest_str


def convert_numbers_to_words_ar(text: str) -> str:
    """
    Convert integers 0-9999 to Arabic words. No external deps.
    """
    def repl(m):
        s = m.group(0)
        try:
            n = int(s)
            if 0 <= n <= 99:
                return _num_to_ar_0_99(n)
            if 100 <= n <= 999:
                return _num_to_ar_100_999(n)
            if 1000 <= n <= 9999:
                return _num_to_ar_1000_9999(n)
        except ValueError:
            pass
        return s

    return re.sub(r"\b\d{1,4}\b", repl, text)


def preprocess_for_tts(text: str, normalize: bool = True, numbers: bool = True, punctuation: bool = True) -> str:
    """Apply full TTS preprocessing pipeline."""
    if not text:
        return text
    t = text.strip()
    if normalize:
        t = normalize_arabic(t)
    if numbers:
        t = convert_numbers_to_words_ar(t)
    if punctuation:
        t = cleanup_punctuation(t)
    return t
