# nlp/keywords.py — TF-IDF واستخراج الكلمات المفتاحية
import sys
import types
from typing import List, Tuple

import joblib
import numpy as np

from ..config import settings
from .text_utils import tokenize_ar, keywords_ar

_TFIDF = {"vec": None, "vocab": None}


def _split_tokens(s: str) -> List[str]:
    return s.split()


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


def extract_keywords(text: str, top_k: int = 10) -> str:
    if not text:
        return ""
    if _ensure_tfidf() and _TFIDF["vec"] is not None:
        try:
            vec = _TFIDF["vec"]
            toks = " ".join(tokenize_ar(text))
            X = vec.transform([toks])
            feats = getattr(vec, "get_feature_names_out", lambda: [])()
            row = X.toarray()[0] if hasattr(X, "toarray") else np.array([])
            if row.size and len(feats):
                order = row.argsort()[::-1]
                kws = [feats[i] for i in order if len(feats[i]) >= 3][: max(1, top_k)]
                if kws:
                    return ", ".join(kws)
        except Exception as e:
            print(f"[TFIDF_KW] failed: {e}")
    return keywords_ar(text, k=top_k)
