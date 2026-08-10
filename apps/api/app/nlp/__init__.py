# nlp/__init__.py — نقطة دخول حزمة NLP
from .text_utils import (
    get_transformers_version,
    advanced_clean_text,
    polish_transcript_ar,
    polish_summary_ar,
    set_summary_source,
    get_summary_source,
)
from .keywords import score_sentences_by_tfidf, extract_keywords
from .punctuation_ner import restore_punct, extract_entities
from .summarization import (
    summarize,
    unload_summarizer_pipes,
    warm_ultra_in_background,
    schedule_warm_ultra_after_asr,
)
from .rag import rag_retrieve

# للتوافق مع من يستدعي nlp_core._FAISS_OK أو nlp_core.faiss
from . import rag as _rag_mod
_FAISS_OK = getattr(_rag_mod, "_FAISS_OK", False)
faiss = getattr(_rag_mod, "faiss", None)

__all__ = [
    "get_transformers_version",
    "advanced_clean_text",
    "polish_transcript_ar",
    "polish_summary_ar",
    "set_summary_source",
    "get_summary_source",
    "score_sentences_by_tfidf",
    "extract_keywords",
    "restore_punct",
    "extract_entities",
    "summarize",
    "unload_summarizer_pipes",
    "warm_ultra_in_background",
    "schedule_warm_ultra_after_asr",
    "rag_retrieve",
    "_FAISS_OK",
    "faiss",
]
