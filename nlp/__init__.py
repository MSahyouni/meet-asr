# nlp/__init__.py — نقطة دخول حزمة NLP
from nlp.text_utils import (
    get_transformers_version,
    advanced_clean_text,
    set_summary_source,
    get_summary_source,
)
from nlp.keywords import score_sentences_by_tfidf, extract_keywords
from nlp.punctuation_ner import restore_punct, extract_entities
from nlp.summarization import summarize
from nlp.rag import rag_retrieve

# للتوافق مع من يستدعي nlp_core._FAISS_OK أو nlp_core.faiss
from nlp import rag as _rag_mod
_FAISS_OK = getattr(_rag_mod, "_FAISS_OK", False)
faiss = getattr(_rag_mod, "faiss", None)

__all__ = [
    "get_transformers_version",
    "advanced_clean_text",
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
