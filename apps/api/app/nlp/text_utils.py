# nlp/text_utils.py — تنظيف وتطبيع عربي، مصدر التلخيص
import re
from collections import Counter
from contextvars import ContextVar

from transformers import __version__ as transformers_version

_AR_STOP = set(
    (
        "في على الى إلى مع عن من ما هذا هذه ذلك تلك هناك هنا ثم حيث لقد قد "
        "كان كانت يكون كانوا كنت إن أن لكن لأن لو إذا إذ كما ربما حتى بين لدى "
        "لديهم لدي إليها فيها منه منها فيه بها بنا لكم لنا فقط جدا جدًا حقا حقيقة "
        "أيضًا أيضاً قبل بعد خلال أثناء ضد عبر نحو فوق تحت إلا بأن وإن أنّ لا لم لن "
        "ليس بدون غير كافة جميع بعض أي أحد نعم مثل ايضا ايضاً جداً جدا حقاً حقا "
        "هو هي هم هن انت انتي انا نحن ال و ف ب ك ل "
        "بانه بإن بان انه إنها انها اللي الي يلي شو هون هيك "
        "اليوم امبارح مبارح بكرا بعدين هلأ هلا هلق "
        "كلام شيء شي اشياء موضوع موضوعنا مواضيع "
        "رح راح عم قاعد قاعدين بدنا بدي بدك "
        "يعني ايه اه آه اوكي أوكي طيب تمام مزبوط "
        "نبدا نبدأ بسم الله الرحمن الرحيم الاساسي الاساس ان"
    ).split()
)

_SUMMARY_SOURCE: ContextVar[str] = ContextVar("summary_source", default="local")

# كلمات شائعة من تفريغ العامية/الإنجليزية قبل التلخيص (وأن يظهر النص أنظف للمستخدم)
_ASR_LOAN_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"س[ُو]?م[اا]?رايز(?:ينج|ينغ)?", re.IGNORECASE), "تلخيص"),
    (re.compile(r"سيمرايز(?:ينج)?", re.IGNORECASE), "تلخيص"),
    (re.compile(r"\bsummariz(?:e|ing|ation)?\b", re.IGNORECASE), "تلخيص"),
    (re.compile(r"\bsummary\b", re.IGNORECASE), "ملخص"),
    (re.compile(r"\boff[\s\-]?line\b", re.IGNORECASE), "دون اتصال بالإنترنت"),
    (re.compile(r"[أا]?وف[\s\-]?لاين", re.IGNORECASE), "دون اتصال بالإنترنت"),
    (re.compile(r"\bon[\s\-]?line\b", re.IGNORECASE), "متصل بالإنترنت"),
    (re.compile(r"[أا]?ون[\s\-]?لاين", re.IGNORECASE), "متصل بالإنترنت"),
    (re.compile(r"\bASR\b", re.IGNORECASE), "تفريغ صوتي"),
    (re.compile(r"\bTTS\b", re.IGNORECASE), "تحويل النص إلى صوت"),
    (re.compile(r"\bNLP\b", re.IGNORECASE), "معالجة لغة"),
    (re.compile(r"\bAI\b"), "ذكاء اصطناعي"),
    (re.compile(r"ال\s*AI\b", re.IGNORECASE), "الذكاء الاصطناعي"),
    (re.compile(r"لبلخص"), "للتلخيص"),
    (re.compile(r"نبلش"), "نبدأ"),
    (re.compile(r"موضوعة"), "موضوعه"),
    (re.compile(r"مدلفون"), "مايكروفون"),
    (re.compile(r"مايك[ـ\-]?روفون"), "مايكروفون"),
    (re.compile(r"اختبار\s*سموك"), "اختبار دخان"),
    (re.compile(r"\bsmoke\s*test\b", re.IGNORECASE), "اختبار دخان"),
    (re.compile(r"سكريب?تات"), "سكربتات"),
    (re.compile(r"سكريبتات"), "سكربتات"),
    (re.compile(r"الفلاتر"), "فلاتر"),
    (re.compile(r"تفريغ الناس"), "تفريغ النص"),
    (re.compile(r"تلخيص الناس"), "تلخيص النص"),
    (re.compile(r"شنو[ةه]?"), "شيء"),
    (re.compile(r"عم بحكي"), "أتحدث"),
    (re.compile(r"كنت عم"), "كنت"),
    (re.compile(r"بعدين"), "بعد ذلك"),
    (re.compile(r"تفريغه كلام(?!ي)"), "تفريغه كلامياً"),
)


def get_transformers_version() -> str:
    return transformers_version


def normalize_asr_loanwords(text: str) -> str:
    """حوّل كلمات التفريغ الإنجليزية/المكسّرة إلى عربية أوضح قبل التلخيص."""
    out = text or ""
    for pattern, repl in _ASR_LOAN_FIXES:
        out = pattern.sub(repl, out)
    return out


def polish_transcript_ar(text: str) -> str:
    """تنظيف خفيف لنص التفريغ المعروض وللتلخيص اللاحق."""
    out = (text or "").strip()
    if not out:
        return ""
    out = normalize_asr_loanwords(out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def polish_summary_ar(text: str) -> str:
    """تنظيف خفيف لمخرج التلخيص (أخطاء شائعة من الموديل/التفريغ)."""
    out = (text or "").strip()
    if not out:
        return ""
    out = normalize_asr_loanwords(out)
    # احذف أسطر الأقسام السلبية التي يملأها الموديل بدل الحذف
    neg_section = re.compile(
        r"(?im)^\s*(?:\*+\s*)?(?:\*\*)?(?:ملخص تنفيذي|المشاركون|المتكلمون|القرارات|بنود العمل|نقاط مفتوحة|مؤجّ?لة)"
        r"[^\n]*?(?:لم يتم|لا يوجد|لم يُ|لم تصدر|لم تُ|لم يُذكر|لم يتم ذكر)[^\n]*$"
    )
    out = "\n".join(line for line in out.splitlines() if not neg_section.search(line))
    # أزل تكرار نفس الفقرة حرفياً
    parts = [p.strip() for p in re.split(r"\n{2,}", out) if p.strip()]
    deduped: list[str] = []
    for p in parts:
        if not deduped or deduped[-1] != p:
            deduped.append(p)
    out = "\n\n".join(deduped)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def advanced_clean_text(text: str, preserve_speakers: bool = False) -> str:
    """
    تنظيف نص التفريغ قبل التلخيص/الكلمات المفتاحية.

    preserve_speakers=True يبقي علامات المتكلم (مهم لمحاضر الاجتماعات).
    """
    text = re.sub(r"(?m)^\s*المدة\s*:\s*.*", " ", text)
    text = re.sub(r"(?m)^\s*#{2,}\s*ملف:.*", " ", text)
    # طوابع زمنية مثل [12.3s] أو [00:01:02]
    text = re.sub(r"\[\d+(?:[.:]\d+)+[^\]]*\]", " ", text)

    if preserve_speakers:
        # أزل الأقواس العامة مع الإبقاء على (متكلم N) / (Speaker N)
        text = re.sub(r"\((?!متكلم\b|speaker\b)[^)]*\)", " ", text, flags=re.IGNORECASE)
    else:
        text = re.sub(r"\(متكلم\s*\d+\)|\([^)]*\)", " ", text)

    fillers = r"\b(يعني|هيك|تمام|مزبوط|اوكي|أوكي|طيب|مم|اها|ايه|اه|آه)\b"
    text = re.sub(fillers, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\w+)(?:\s+\1)+\b", r"\1", text)
    text = normalize_asr_loanwords(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_ar(s: str) -> str:
    s = s.replace("\u0640", "")
    trans_map = {
        "آ": "ا", "أ": "ا", "إ": "ا",
        "ى": "ي", "ئ": "ي",
        "ؤ": "و",
    }
    s = s.translate(str.maketrans(trans_map))
    s = s.replace("ة", "ه")
    return s


def tokenize_ar(s: str) -> list:
    return [t for t in re.findall(r"[\u0621-\u064A]+", normalize_ar(s)) if t not in _AR_STOP]


def keywords_ar(text: str, k: int = 10) -> str:
    return ", ".join(w for w, _ in Counter(tokenize_ar(text)).most_common(k))


def set_summary_source(s: str) -> None:
    _SUMMARY_SOURCE.set(s)


def get_summary_source() -> str:
    return _SUMMARY_SOURCE.get()
