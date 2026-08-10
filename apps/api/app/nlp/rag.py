# nlp/rag.py — RAG (FAISS + sentence-transformers)
import json

import numpy as np

from ..config import settings

faiss = None
_FAISS_OK = False
try:
    import faiss as _faiss  # type: ignore

    faiss = _faiss
    _FAISS_OK = True
except ImportError:
    faiss = None
    _FAISS_OK = False

try:
    from sentence_transformers import SentenceTransformer

    _ST_OK = True
except ImportError:
    SentenceTransformer = None
    _ST_OK = False

_rag_index = None
_rag_model = None
_rag_texts = []
_rag_dim = None


def _rag_load() -> None:
    global _rag_index, _rag_model, _rag_texts, _rag_dim
    if not settings.RAG_ENABLED or _rag_index is not None:
        return
    if not (_FAISS_OK and _ST_OK and faiss is not None):
        print("[RAG] disabled (faiss or sentence-transformers missing).")
        return
    _RAG_INDEX = settings.RAG_DIR / "index.faiss"
    _RAG_DOCS = settings.RAG_DIR / "docs.jsonl"
    if not _RAG_INDEX.exists() or not _RAG_DOCS.exists():
        print("[RAG] no ArabicText-Large index found.")
        return
    print("[RAG] loading FAISS + docs ...")
    try:
        _rag_index = faiss.read_index(str(_RAG_INDEX))
        with open(_RAG_DOCS, "r", encoding="utf-8") as f:
            _rag_texts = [json.loads(line).get("text", "") for line in f]
        _rag_model = SentenceTransformer(settings.RAG_EMB_MODEL)
        print(f"[RAG] model={settings.RAG_EMB_MODEL} loaded")
        _rag_dim = getattr(_rag_model, "get_sentence_embedding_dimension", lambda: None)()
        if _rag_dim and _rag_index.d != int(_rag_dim):
            print(f"[RAG] dim mismatch: index.d={_rag_index.d} vs model.d={_rag_dim} → disabling RAG")
            _rag_index = None
    except Exception as e:
        print(f"[RAG] load failed: {e}")
        _rag_index = None


def rag_retrieve(query: str, k: int = 6) -> str:
    if not query.strip():
        return ""
    _rag_load()
    if _rag_index is None:
        return ""
    try:
        qv = _rag_model.encode([f"query: {query}"], normalize_embeddings=True)
        D, I = _rag_index.search(np.asarray(qv, dtype="float32"), max(1, min(k, _rag_index.ntotal)))
        return "\n\n".join(_rag_texts[i] for i in I[0] if i < len(_rag_texts)).strip()
    except Exception as e:
        print(f"[RAG] search failed: {e}")
        return ""
