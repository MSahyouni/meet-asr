# nlp/keywords.py — استخراج كلمات مفتاحية مفيدة (بدون حشو)
import sys
import types
from collections import Counter
from typing import List, Tuple

import joblib
import numpy as np

from ..config import settings
from .text_utils import _AR_STOP, normalize_ar, tokenize_ar

_TFIDF = {"vec": None, "vocab": None}

# كلمات عامة / أفعال حوار لا تفيد كـ keywords لاجتماع
_KW_EXTRA_STOP = {
    "نبدا", "نبدأ", "سنبدا", "سنبدأ", "بسم", "الله", "الرحمن", "الرحيم",
    "الاساسي", "الاساس", "بتحويل", "تفريغه", "البرنامج", "برنامج",
    "اليوم", "الان", "الآن", "بعد", "قبل", "خلال", "عند", "عندما", "حيث",
    "يكون", "تكون", "كانت", "عمل", "عملنا", "سنقوم", "نقوم", "يعني",
    "ايضا", "أيضا", "فقط", "نريد", "يجب", "جميع", "اي", "أي",
    "شيء", "اشياء", "ناس", "الناس", "اختبار", "نختبر", "نتاكد", "نتأكد",
    "ننظف", "تنظيف", "ملفات", "ملف", "غير", "لازمه", "لازمة", "موقتة",
    "مؤقتة", "بداية", "ايضاً", "أيضاً", "هناك", "هنا", "ذلك", "هذه",
    "هذا", "الان", "الآن", "تم", "كان", "يكون", "بدون", "بلا", "مشاكل",
    "مشكلة", "جيدا", "جيداً", "جدا", "جداً", "ايضا", "ايضاً",
    "تسجيل", "بالتسجيل", "تفريغ", "تلخيص", "النص", "محضر", "تحميل",
    "كلمات", "التحقق", "اجراء", "إجراء", "نجح", "نجاح", "سموك", "دخان",
    "فلتر", "فلاتر", "موبايل", "الفلاتر", "سكربتات", "سكريبتات",
    "اخري", "اخرى", "أخرى", "والاخري", "والاخرى", "ادخال", "إدخال",
    "سيرفر", "السيرفر", "واختبار", "وادخال", "والاخري",
    "يعمل", "ازمه", "لازمه", "لازم", "غير",
    # حشو حواري شائع يخرج كـ keywords ضعيفة
    "وهذا", "فهذا", "فذلك", "احيانا", "أحيانا", "أحياناً", "احياناً",
    "يوميا", "يومياً", "فبداية", "فبدايه", "بداية", "ياتي", "يأتي",
    "كيفك", "صحتك", "اهلا", "أهلا",
}


def _split_tokens(s: str) -> List[str]:
    return s.split()


def _strip_clitics(token: str) -> str:
    """أزل و/ال/بال… دون تكسير جذور مثل برنامج."""
    n = normalize_ar((token or "").strip())
    if not n:
        return ""
    if n.startswith("و") and len(n) > 4:
        n = n[1:]
    for pref in ("بال", "كال", "لال", "فال", "لل"):
        if n.startswith(pref) and len(n) > len(pref) + 2:
            return n[len(pref) :]
    if n.startswith("ال") and len(n) > 4:
        n = n[2:]
    # سين المستقبل: سنبدا → نبدا
    if n.startswith("س") and len(n) > 4:
        rest = n[1:]
        if rest in _AR_STOP or rest in _KW_EXTRA_STOP or normalize_ar(rest) in _KW_EXTRA_STOP:
            return rest
    return n


def _ensure_tfidf() -> bool:
    if _TFIDF.get("vec") is not None:
        return True
    if settings.TFIDF_PATH.exists():
        try:
            if "asr_core" not in sys.modules:
                shim = types.ModuleType("asr_core")
                shim._split_tokens = lambda s: s.split()
                sys.modules["asr_core"] = shim
            vec = joblib.load(settings.TFIDF_PATH)
            _TFIDF["vec"] = vec
            _TFIDF["vocab"] = vec.get_feature_names_out()
            print(f"[TFIDF] Loaded from {settings.TFIDF_PATH}")
            return True
        except Exception as e:
            print(f"[TFIDF] Failed to load from disk: {e}")
    import logging
    logging.getLogger(__name__).debug("[TFIDF] Model file not found. Using fallback keyword extraction method.")
    return False


def score_sentences_by_tfidf(sentences: List[str]) -> List[Tuple[str, float]]:
    if not _ensure_tfidf() or not sentences:
        return [(s, 0.0) for s in sentences]
    vec = _TFIDF["vec"]
    tokenized_sentences = [" ".join(tokenize_ar(s)) for s in sentences]
    try:
        tfidf_matrix = vec.transform(tokenized_sentences)
        scores = np.asarray(tfidf_matrix.mean(axis=1)).ravel()
        return list(zip(sentences, scores))
    except Exception as e:
        print(f"[TFIDF_SCORE] Failed to score sentences: {e}")
        return [(s, 0.0) for s in sentences]


def _useful_keyword(token: str) -> bool:
    t = (token or "").strip()
    if len(t) < 4:
        return False
    n = _strip_clitics(t)
    if len(n) < 4:
        return False
    if n in _AR_STOP or t in _AR_STOP:
        return False
    if n in _KW_EXTRA_STOP or t in _KW_EXTRA_STOP or normalize_ar(t) in _KW_EXTRA_STOP:
        return False
    if not any("\u0621" <= c <= "\u064A" for c in n):
        return False
    return True


def extract_keywords(text: str, top_k: int = 8) -> str:
    """أرجع كلمات مفتاحية مفيدة فقط؛ فارغ إذا الجودة ضعيفة."""
    if not text:
        return ""

    top_k = max(3, min(int(top_k or 8), 10))
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        core = _strip_clitics(raw)
        if not _useful_keyword(raw) and not _useful_keyword(core):
            return
        key = core or normalize_ar(raw)
        if key in seen:
            return
        if not _useful_keyword(key):
            return
        seen.add(key)
        candidates.append(key)

    if _ensure_tfidf() and _TFIDF["vec"] is not None:
        try:
            vec = _TFIDF["vec"]
            toks = " ".join(tokenize_ar(text))
            X = vec.transform([toks])
            feats = getattr(vec, "get_feature_names_out", lambda: [])()
            row = X.toarray()[0] if hasattr(X, "toarray") else np.array([])
            if row.size and len(feats):
                order = row.argsort()[::-1]
                for i in order:
                    feat = feats[i]
                    if float(row[i]) <= 0:
                        break
                    _add(feat)
                    if len(candidates) >= top_k:
                        break
        except Exception as e:
            print(f"[TFIDF_KW] failed: {e}")

    if len(candidates) < 3:
        counted = Counter(tokenize_ar(text))
        for w, _n in counted.most_common(50):
            _add(w)
            if len(candidates) >= top_k:
                break

    if len(candidates) < 3:
        return ""
    return ", ".join(candidates[:top_k])
