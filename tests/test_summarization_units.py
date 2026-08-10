# tests/test_summarization_units.py — unit tests for chunking / prompts (no GPU)
from app.nlp.prompts import build_ultra_prompt, normalize_prompt_mode
from app.nlp.summarization import _estimate_tokens, _split_into_chunks
from app.nlp.text_utils import advanced_clean_text, get_summary_source, set_summary_source


def test_normalize_prompt_mode_aliases():
    assert normalize_prompt_mode("auto") == "meeting"
    assert normalize_prompt_mode("manual") == "concise"
    assert normalize_prompt_mode("MEETING") == "meeting"


def test_meeting_prompt_has_structure():
    prompt = build_ultra_prompt("نص تجريبي للاجتماع.", prompt_mode="meeting", stage="final")
    assert "بنود العمل" in prompt
    assert "القرارات" in prompt
    assert "نص تجريبي" in prompt
    assert "لا تختلق" in prompt or "دون اختلاق" in prompt or "صراحة" in prompt


def test_meeting_prompt_anti_hallucination():
    prompt = build_ultra_prompt("شرح تجريبي عن البرنامج.", prompt_mode="meeting", stage="final")
    assert "صراحة" in prompt
    assert "الملخص التنفيذي وحده" in prompt
    assert "مشاركين" in prompt or "خطوات مستقبلية" in prompt


def test_meeting_messages_roles():
    from app.nlp.prompts import build_ultra_messages

    msgs = build_ultra_messages("نص تجريبي.", prompt_mode="meeting", stage="final")
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "نص تجريبي" in msgs[1]["content"]


def test_partial_prompt_is_shorter_guidance():
    prompt = build_ultra_prompt("جزء.", prompt_mode="meeting", stage="partial")
    assert "جزء من محضر" in prompt


def test_split_into_chunks_respects_max_parts():
    # جمل قصيرة كثيرة → عدة أجزاء محدودة
    sentences = [f"هذه جملة رقم {i} في النص الطويل جداً للاختبار." for i in range(40)]
    text = " ".join(sentences)
    chunks = _split_into_chunks(text, max_tokens=40, max_parts=3)
    assert 1 <= len(chunks) <= 3
    assert "".join(c.replace(" ", "") for c in chunks)  # غير فارغ
    # كل الكلمات تقريباً محفوظة
    joined_words = " ".join(chunks).split()
    assert len(joined_words) >= len(text.split()) - 5


def test_split_short_text_single_chunk():
    text = "ملخص قصير جداً."
    assert _split_into_chunks(text, max_tokens=800, max_parts=8) == [text]


def test_estimate_tokens_positive():
    assert _estimate_tokens("مرحبا بالعالم العربي") >= 3


def test_preserve_speakers_in_clean():
    raw = "المدة: 00:10\n(متكلم 1) مرحبا يعني بالاجتماع (ملاحظة جانبية) طيب"
    cleaned = advanced_clean_text(raw, preserve_speakers=True)
    assert "متكلم 1" in cleaned
    assert "يعني" not in cleaned
    assert "ملاحظة" not in cleaned


def test_asr_loanword_normalization():
    from app.nlp.text_utils import normalize_asr_loanwords, polish_summary_ar, polish_transcript_ar

    raw = "سنجري سمرايز ونختبر offline وموضوعة الأساسي"
    cleaned = normalize_asr_loanwords(raw)
    assert "سمرايز" not in cleaned
    assert "تلخيص" in cleaned
    assert "دون اتصال" in cleaned
    assert "موضوعه" in cleaned
    assert "سمرايز" not in polish_summary_ar("بعد سمرايز offline")
    assert "تلخيص" in polish_transcript_ar("نبلش سمرايز offline")
    assert "دون اتصال" in normalize_asr_loanwords("نشتغل أوفلاين")


def test_extract_keywords_hides_weak():
    from app.nlp.keywords import extract_keywords

    weak = "نبدا بسم الله اليوم كلام موضوعنا هو في على من"
    assert extract_keywords(weak) == ""
    strong = (
        "مناقشة ميزانية المشروع والجدول الزمني للتطوير "
        "مع اعتماد خطة التسليم والمراجعة الفنية للمنتج"
    )
    kws = extract_keywords(strong)
    assert kws
    assert len([p for p in kws.split(",") if p.strip()]) >= 3


def test_summary_source_contextvar():
    set_summary_source("ultra:test")
    assert get_summary_source() == "ultra:test"
    set_summary_source("off")
    assert get_summary_source() == "off"


def test_normalize_summary_mode_ultra_only():
    from app.nlp.summarization import _normalize_summary_mode
    from fastapi import HTTPException
    import pytest

    assert _normalize_summary_mode("ultra") == "ultra"
    assert _normalize_summary_mode("lite") == "ultra"
    assert _normalize_summary_mode("light") == "ultra"
    assert _normalize_summary_mode("off") == "off"
    with pytest.raises(HTTPException):
        _normalize_summary_mode("garbage")
