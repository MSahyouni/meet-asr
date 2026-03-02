# nlp/text_utils.py — تنظيف وتطبيع عربي، مصدر التلخيص
import re
from collections import Counter

from transformers import __version__ as transformers_version

_AR_STOP = set(
    "في على الى إلى مع عن من ما هذا هذه ذلك تلك هناك هنا ثم حيث لقد قد كان كانت يكون كانوا كنت إن أن لكن لأن لو إذا إذ كما ربما حتى بين لدى لديهم لدي إليها فيها منه منها فيه بها بنا لكم لنا فقط جدا جدًا حقا حقيقة أيضًا أيضاً قبل بعد خلال أثناء ضد عبر نحو فوق تحت بين إلا بأن وإن أنّ لا لم لن ليس بدون غير كافة جميع بعض أي أحد نعم مثل ايضا ايضاً جداً جدا حقاً حقا".split()
)

_SUMMARY_SOURCE = "local"


def get_transformers_version() -> str:
    return transformers_version


def advanced_clean_text(text: str) -> str:
    text = re.sub(r"(?m)^\s*المدة\s*:\s*.*", " ", text)
    text = re.sub(r"\[\d+(?:\.\d+)?[^\]]*\]|\(متكلم\s*\d+\)|\(.*?\)|\###\s*ملف:.*", " ", text)
    fillers = r"\b(يعني|هيك|تمام|مزبوط|اوكي|أوكي|طيب|مم|اها|ايه|اه|آه)\b"
    text = re.sub(fillers, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\w+)(?:\s+\1)+\b", r"\1", text)
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
    global _SUMMARY_SOURCE
    _SUMMARY_SOURCE = s


def get_summary_source() -> str:
    return _SUMMARY_SOURCE
