# nlp_core.py — توافق خلفي: إعادة تصدير من حزمة nlp
from nlp import (
    get_transformers_version,
    set_summary_source,
    get_summary_source,
    score_sentences_by_tfidf,
    extract_keywords,
    restore_punct,
    extract_entities,
    summarize,
    rag_retrieve,
    _FAISS_OK,
    faiss,
)

__all__ = [
    "get_transformers_version",
    "set_summary_source",
    "get_summary_source",
    "score_sentences_by_tfidf",
    "extract_keywords",
    "restore_punct",
    "extract_entities",
    "summarize",
    "rag_retrieve",
    "_FAISS_OK",
    "faiss",
]
