"""Suggest Habibi dialect from Arabic text (lightweight heuristics)."""
from __future__ import annotations

import re
from typing import Optional

# Common Levantine / Egyptian dialect markers (space-bounded-ish).
_LEV_MARKERS = re.compile(
    r"(?:\s|^)(شو|هلق|هلأ|يلا|بدي|بدك|يعني\s+هلأ|منيح|كتير|لسا|لسه|هيك|هون|يعني\s+شو)(?:\s|$|[،,.!?؟])",
    re.IGNORECASE,
)
_EGY_MARKERS = re.compile(
    r"(?:\s|^)(ازاي|إزاي|كده|كدا|عايز|عاوز|مش|دلوقتي|النهاردة|فين|يعني\s+كده)(?:\s|$|[،,.!?؟])",
    re.IGNORECASE,
)
_GULF_MARKERS = re.compile(
    r"(?:\s|^)(وش|ليش|حيل|زين|مب|أبيه|ابيه|يبي)(?:\s|$|[،,.!?؟])",
    re.IGNORECASE,
)
_HARAKAT = re.compile(r"[\u064B-\u0652\u0670]")
_ARABIC_LETTER = re.compile(r"[\u0621-\u064A]")

# MSA-leaning function words / particles common in formal prose.
_MSA_MARKERS = re.compile(
    r"(?:\s|^)(إنّ|أنّ|الذي|التي|اللذان|اللتان|الذين|اللواتي|كما|إذ|إذا|لقد|فإن|ذلك|تلك|هؤلاء|أولئك|حيث|بينما|غير أن|على الرغم)(?:\s|$|[،,.!?؟:])",
)


def _harakat_coverage(text: str) -> float:
    letters = _ARABIC_LETTER.findall(text or "")
    if not letters:
        return 0.0
    marks = len(_HARAKAT.findall(text or ""))
    return min(1.0, marks / float(len(letters)))


def suggest_habibi_dialect(text: str, current: Optional[str] = None) -> dict:
    """
    Return suggested dialect id + reason.

    Does not force a change when current is an explicit dialect the user chose
    (unless current is UNK/empty); callers decide whether to apply.
    """
    raw = re.sub(r"\s+", " ", (text or "").strip())
    current_norm = (current or "UNK").strip().upper() or "UNK"

    if not raw or not _ARABIC_LETTER.search(raw):
        return {
            "suggested": current_norm if current_norm != "UNK" else "UNK",
            "confidence": "low",
            "reason": "لا يوجد نص عربي كافٍ لاقتراح لهجة",
            "apply_recommended": False,
        }

    if _EGY_MARKERS.search(raw):
        return {
            "suggested": "EGY",
            "confidence": "medium",
            "reason": "مؤشرات لهجة مصرية في النص",
            "apply_recommended": current_norm in ("", "UNK"),
        }
    if _LEV_MARKERS.search(raw):
        return {
            "suggested": "LEV",
            "confidence": "medium",
            "reason": "مؤشرات لهجة شامية في النص",
            "apply_recommended": current_norm in ("", "UNK"),
        }
    if _GULF_MARKERS.search(raw):
        return {
            "suggested": "SAU",
            "confidence": "low",
            "reason": "مؤشرات لهجة خليجية تقريبية → SAU",
            "apply_recommended": current_norm in ("", "UNK"),
        }

    coverage = _harakat_coverage(raw)
    msa_hits = len(_MSA_MARKERS.findall(raw))
    if coverage >= 0.25 or msa_hits >= 2:
        return {
            "suggested": "MSA",
            "confidence": "high" if coverage >= 0.35 or msa_hits >= 3 else "medium",
            "reason": "نص يميل إلى الفصحى (تشكيل و/أو تراكيب فصيحة) → MSA",
            "apply_recommended": current_norm in ("", "UNK"),
        }

    # Default literary Arabic without strong dialect markers → MSA suggestion (soft).
    if len(raw) >= 80:
        return {
            "suggested": "MSA",
            "confidence": "low",
            "reason": "نص طويل بلا مؤشرات لهجة واضحة — MSA أنسب عادةً",
            "apply_recommended": current_norm in ("", "UNK"),
        }

    return {
        "suggested": current_norm if current_norm != "UNK" else "UNK",
        "confidence": "low",
        "reason": "لم يُحسم اقتراح لهجة — أبقِ الاختيار الحالي",
        "apply_recommended": False,
    }
