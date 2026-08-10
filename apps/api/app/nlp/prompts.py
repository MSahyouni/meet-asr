# nlp/prompts.py — قوالب برومبت التلخيص (محاضر اجتماعات)
"""Arabic summarization prompts for ultra (causal LM) mode."""

from typing import Literal

PromptMode = Literal["auto", "meeting", "balanced", "concise", "manual"]

_ANTI_HALLUCINATION = (
    "قواعد صارمة: "
    "1) اعتمد فقط على ما ورد صراحة في النص؛ لا تختلق قرارات أو مهام أو أسماء أو مواعيد. "
    "2) إذا لم يُذكر قرار صريح فلا تكتب قسم القرارات أصلاً. "
    "3) إذا لم تُسند مهمة لمسؤول فلا تكتب بنود عمل ولا تخترع «لا يوجد محدد». "
    "4) لا تكرر النص حرفياً؛ لخّص المعنى باقتضاب. "
    "5) إذا كان النص مونولوجاً أو شرحاً تجريبياً بلا اجتماع رسمي، "
    "اكتفِ بملخص تنفيذي عن الموضوع الأساسي دون أقسام قرارات/مهام وهمية. "
    "6) لا تضف أي جملة عن مشاركين أو خطوات مستقبلية أو نوايا لم تُذكر حرفياً في النص. "
    "7) كل جملة في مخرجك يجب أن تكون قابلة للتحقق من جملة في النص؛ وإلا احذفها. "
    "8) اكتب بالعربية الفصحى فقط؛ استبدل أي كلمة إنجليزية مفرَّغة (مثل summarize/offline) بمرادف عربي سليم. "
    "9) ممنوع كتابة أقسام سلبية مثل «لم يتم ذكر» أو «لا يوجد مشاركون» أو «لم تصدر قرارات» — "
    "احذف القسم بالكامل بدل ملئه بالنفي."
)

_MEETING_SYSTEM = (
    "أنت مساعد محاضر اجتماعات عربي محترف. "
    "اكتب بالعربية الفصحى الواضحة، وبدون حشو. "
    + _ANTI_HALLUCINATION
)

_MEETING_STRUCTURE = """استخدم فقط الأقسام التي لها محتوى صريح في النص (احذف أي قسم بلا دليل):
1) ملخص تنفيذي (2–4 أسطر): الموضوع الأساسي وما جرى فعلاً
2) المشاركون / المتكلمون — فقط إن وُجدت تسميات متكلمين أو أسماء
3) القرارات — فقط قرارات مُعلنة بوضوح (مثل: اعتمدنا / قررنا / تمت الموافقة)
4) بنود العمل — فقط إن ذُكر مسؤول ومهمة (الصيغة: المسؤول — المهمة — الموعد إن وُجد)
5) نقاط مفتوحة / مؤجّلة — فقط إن ذُكر تأجيل أو موضوع معلّق صراحةً

 ممنوع: ملء الأقسام بتخمينات، أو إعادة صياغة كل الجملة كـ«قرار»، أو اختراع مواعيد."""

_PARTIAL_HINT = (
    "هذا جزء من محضر أطول. استخرج من هذا الجزء فقط الحقائق الصريحة "
    "(موضوع، قرارات مذكورة، مهام مسندة، أسماء/تواريخ) دون اختلاق."
)

_FINAL_MERGE_HINT = (
    "أمامك ملخصات أجزاء من نفس الاجتماع. وحّدها في محضر واحد متسق دون تكرار، "
    "وادمج فقط القرارات وبنود العمل الواردة فعلاً؛ احذف أي بند بلا سند."
)


def normalize_prompt_mode(mode: str | None) -> str:
    m = (mode or "auto").strip().lower()
    aliases = {
        "auto": "meeting",
        "meeting": "meeting",
        "minutes": "meeting",
        "محضر": "meeting",
        "balanced": "balanced",
        "concise": "concise",
        "manual": "concise",
        "factual": "concise",
        "short": "concise",
    }
    return aliases.get(m, "meeting")


def build_ultra_messages(text: str, prompt_mode: str = "auto", stage: str = "final") -> list[dict[str, str]]:
    """Chat messages for models that need apply_chat_template (e.g. Jais-2)."""
    mode = normalize_prompt_mode(prompt_mode)
    stage = (stage or "final").lower()

    if mode == "concise":
        system = (
            "أنت مساعد تلخيص عربي احترافي. "
            "اكتب ملخصاً عربيًا فصيحًا، دقيقًا، ومركّزًا على الحقائق فقط. "
            "بدون حشو، وبدون تكرار، ويفضّل شكل نقاط قصيرة. "
            "لا تضف قرارات أو مهام غير مذكورة."
        )
        if stage == "partial":
            system += " " + _PARTIAL_HINT
        user = f"النص:\n{text}\n\nاكتب الملخص فقط."
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    if mode == "balanced":
        system = (
            "أنت مساعد تلخيص عربي. "
            "قدّم ملخصاً مركّزاً يتضمن: الفكرة العامة، أهم النقاط، "
            "وأي قرارات أو مهام فقط إن وُجدت صراحةً في النص. "
            "لا تختلق محتوى."
        )
        if stage == "partial":
            system += " " + _PARTIAL_HINT
        elif stage == "final" and "ملخص الجزء" in text:
            system += " " + _FINAL_MERGE_HINT
        user = f"النص:\n{text}\n\nاكتب الملخص فقط."
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    system = _MEETING_SYSTEM
    if stage == "partial":
        system += " " + _PARTIAL_HINT
        structure = (
            "اكتب نقاطاً قصيرة للحقائق الصريحة فقط: الموضوع، "
            "ثم قرارات/مهام/أسماء/تواريخ إن وُجدت فعلاً. لا تختلق أقساماً فارغة."
        )
    elif stage == "final" and "ملخص الجزء" in text:
        system += " " + _FINAL_MERGE_HINT
        structure = _MEETING_STRUCTURE
    else:
        structure = _MEETING_STRUCTURE

    user = (
        f"{structure}\n\nالنص:\n{text}\n\n"
        "اكتب المحضر النهائي فقط. إن لم توجد قرارات أو مهام صريحة، "
        "اكتب الملخص التنفيذي وحده دون أقسام إضافية. "
        "ممنوع اختراع مشاركين أو خطط مستقبلية غير مذكورة."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_ultra_prompt(text: str, prompt_mode: str = "auto", stage: str = "final") -> str:
    """
    stage:
      - partial: تلخيص جزء من نص طويل
      - final: محضر نهائي أو دمج ملخصات الأجزاء
    """
    messages = build_ultra_messages(text, prompt_mode=prompt_mode, stage=stage)
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in messages if m["role"] == "user"), text)
    # Plain completion fallback (non-chat models)
    if "المحضر" in user or "الملخص" in user:
        return f"{system}\n\n{user}"
    return f"{system}\n\nالنص:\n{text}\n\nالمحضر:"
