import os, re, collections, json, numpy as np
from typing import Tuple, List, Dict
from pathlib import Path
from fastapi import HTTPException
import joblib
from collections import Counter
import sys, types

# مكتبات transformers
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM, __version__ as transformers_version
from huggingface_hub import snapshot_download
import pathlib

# مكتبات اختيارية
try:
    import faiss; _FAISS_OK = True
except ImportError:
    faiss, _FAISS_OK = None, False
try:
    from sentence_transformers import SentenceTransformer; _ST_OK = True
except ImportError:
    SentenceTransformer, _ST_OK = None, False

from config import settings

# ===== ثوابت ودوال نصية =====

_AR_STOP = set("في على الى إلى مع عن من ما هذا هذه ذلك تلك هناك هنا ثم حيث لقد قد كان كانت يكون كانوا كنت إن أن لكن لأن لو إذا إذ كما ربما حتى بين لدى لديهم لدي إليها فيها منه منها فيه بها بنا لكم لنا فقط جدا جدًا حقا حقيقة أيضًا أيضاً قبل بعد خلال أثناء ضد عبر نحو فوق تحت بين إلا بأن وإن أنّ لا لم لن ليس بدون غير كافة جميع بعض أي أحد نعم مثل ايضا ايضاً جداً جدا حقاً حقا".split())

def get_transformers_version() -> str: return transformers_version

def _advanced_clean_text(text: str) -> str:
    text = re.sub(r"(?m)^\s*المدة\s*:\s*.*", " ", text)
    text = re.sub(r"\[\d+(?:\.\d+)?[^\]]*\]|\(متكلم\s*\d+\)|\(.*?\)|\###\s*ملف:.*", " ", text)
    fillers = r'\b(يعني|هيك|تمام|مزبوط|اوكي|أوكي|طيب|مم|اها|ايه|اه|آه)\b'
    text = re.sub(fillers, ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\w+)(?:\s+\1)+\b', r'\1', text)
    return re.sub(r"\s+", " ", text).strip()

def _normalize_ar(s: str):
    # إزالة التطويل
    s = s.replace("\u0640", "")
    # توحيد الألف والهمزات واليا/الواو
    trans_map = {
        "آ": "ا", "أ": "ا", "إ": "ا",
        "ى": "ي", "ئ": "ي",
        "ؤ": "و",
    }
    s = s.translate(str.maketrans(trans_map))
    # تحويل التاء المربوطة إلى هاء
    s = s.replace("ة", "ه")
    return s

def _tokenize_ar(s: str): return [t for t in re.findall(r"[\u0621-\u064A]+", _normalize_ar(s)) if t not in _AR_STOP]
def _keywords_ar(text: str, k: int=10):
    return ", ".join(w for w,_ in Counter(_tokenize_ar(text)).most_common(k))
_SUMMARY_SOURCE = "local"
def set_summary_source(s): global _SUMMARY_SOURCE; _SUMMARY_SOURCE=s
def get_summary_source(): return _SUMMARY_SOURCE


# ===== منطق TF-IDF (تم نقله من asr_core.py) =====

_TFIDF = {"vec": None, "vocab": None}

def _split_tokens(s: str) -> List[str]:
    return s.split()

def _ensure_tfidf() -> bool:
    if _TFIDF.get("vec") is not None:
        return True
    
    if settings.TFIDF_PATH.exists():
        try:
            # --- Backward-compat shim ---
            # بعض ملفات joblib القديمة حُفظت وهي تشير إلى asr_core._split_tokens.
            # نحقن وحدة مؤقتة باسم "asr_core" ونوفّر الرمز المطلوب لتنجح عملية load.
            if "asr_core" not in sys.modules:
                shim = types.ModuleType("asr_core")
                def _legacy_split_tokens(s: str):
                    return s.split()
                shim._split_tokens = _legacy_split_tokens
                sys.modules["asr_core"] = shim
            # --- /shim ---

            vec = joblib.load(settings.TFIDF_PATH)
            _TFIDF["vec"] = vec
            _TFIDF["vocab"] = vec.get_feature_names_out()
            print(f"[TFIDF] Loaded from {settings.TFIDF_PATH}")
            return True
        except Exception as e:
            print(f"[TFIDF] Failed to load from disk: {e}")

    # (Optional) Build logic if you have parquet files can be added here
    # TFIDF اختياري - التطبيق يعمل بدونه باستخدام طريقة بسيطة لاستخراج الكلمات المفتاحية
    # يمكن بناء النموذج لاحقاً من بيانات parquet إذا توفرت
    import logging
    logger = logging.getLogger(__name__)
    logger.debug("[TFIDF] Model file not found. Using fallback keyword extraction method.")
    return False

def score_sentences_by_tfidf(sentences: List[str]) -> List[Tuple[str, float]]:
    if not _ensure_tfidf() or not sentences:
        return [(s, 0.0) for s in sentences]

    vec = _TFIDF["vec"]
    tokenized_sentences = [" ".join(_tokenize_ar(s)) for s in sentences]
    
    try:
        tfidf_matrix = vec.transform(tokenized_sentences)
        scores = np.asarray(tfidf_matrix.mean(axis=1)).ravel()
        return list(zip(sentences, scores))
    except Exception as e:
        print(f"[TFIDF_SCORE] Failed to score sentences: {e}")
        return [(s, 0.0) for s in sentences]

def extract_keywords(text: str, top_k: int = 10) -> str:
    """
    كلمات مفتاحية باستخدام TF-IDF إن توفر نموذج محفوظ،
    وإلا سقوط احتياطي إلى تردد بسيط (_keywords_ar).
    """
    if not text:
        return ""
    if _ensure_tfidf() and _TFIDF["vec"] is not None:
        try:
            vec = _TFIDF["vec"]
            toks = " ".join(_tokenize_ar(text))
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
    # احتياطي
    return _keywords_ar(text, k=top_k)

# ===== دوال التلخيص =====

_ABST_PIPE = None
_PUNCT_PIPE = None
_NER_PIPE = None

def _ensure_local(repo_or_path: str, subdir: str) -> str:
    """
    إذا كان repo_or_path مسارًا موجودًا نعيده.
    إن كان معرّف مستودع HF ننزّله لمجلد ثابت تحت data/models/<subdir>/ ونرجع ذلك المسار.
    """
    p = pathlib.Path(repo_or_path)
    if p.exists():
        return p.as_posix()
    # repo id → نزّل لمجلد ثابت
    target = (settings.MODELS_DIR / subdir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_or_path,
        local_dir=target.as_posix(),
        local_dir_use_symlinks=False,
        cache_dir=settings.HF_DIR.as_posix(),
        token=settings.HF_TOKEN,
    )
    return target.as_posix()

def _load_abstractive_pipe():
    """يحمل نموذج التلخيص باستخدام Transformers Pipeline."""
    global _ABST_PIPE
    if _ABST_PIPE is not None: return _ABST_PIPE
    try:
        print("[SUM] Loading summarization model with Transformers...")
        local_path = _ensure_local(settings.SUMMARIZER_MODEL, "summarizers/mT5_XLSum")
        tok = AutoTokenizer.from_pretrained(local_path, token=settings.HF_TOKEN, use_fast=False)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(local_path, token=settings.HF_TOKEN)
        _ABST_PIPE = pipeline("summarization", model=mdl, tokenizer=tok, device=settings.HF_DEVICE_ID)
        print("[SUM] Transformers summarizer loaded.")
        return _ABST_PIPE
    except Exception as e:
        print(f"[TF] mT5 load failed: {e}")
        return None

def _load_punct_pipe():
    """تحميل نموذج استرجاع علامات الترقيم (اختياري)."""
    global _PUNCT_PIPE
    if _PUNCT_PIPE is not None: return _PUNCT_PIPE
    try:
        local_path = _ensure_local(settings.PUNCT_MODEL, "punctuation/arabic_punct")
        tok = AutoTokenizer.from_pretrained(local_path, token=settings.HF_TOKEN, use_fast=False)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(local_path, token=settings.HF_TOKEN)
        _PUNCT_PIPE = pipeline("text2text-generation", model=mdl, tokenizer=tok, device=settings.HF_DEVICE_ID)
        return _PUNCT_PIPE
    except Exception as e:
        print(f"[PUNCT] load failed: {e}")
        return None

def restore_punct(text: str, max_len: int = 512) -> str:
    """يعيد علامات الترقيم لنص عربي. يسقط بصمت إن لم يتوفر النموذج."""
    if not text: return ""
    p = _load_punct_pipe()
    if p is None: return text
    # معالجة على مستوى الأسطر مع تقطيع يحترم الحد الأقصى للكلمات
    parts = [t.strip() for t in re.split(r'[\n]', text) if t.strip()]
    out = []
    for part in parts:
        words = part.split()
        if not words:
            continue
        # قسّم السطر إلى كُتَل لا تتجاوز max_len كلمة
        for i in range(0, len(words), max_len):
            chunk = " ".join(words[i:i+max_len])
            try:
                y = p(chunk, max_new_tokens=max_len, do_sample=False)[0]["generated_text"]
                out.append(y.strip())
            except Exception:
                out.append(chunk)
    return "\n".join(out)

def _load_ner_pipe():
    """تحميل نموذج NER عربي (اختياري)."""
    global _NER_PIPE
    if _NER_PIPE is not None: return _NER_PIPE
    try:
        local_path = _ensure_local(settings.NER_MODEL, "ner/arabic_ner")
        _NER_PIPE = pipeline(
           "token-classification",
            model=local_path,
            tokenizer=local_path,
            aggregation_strategy="simple",
            device=settings.HF_DEVICE_ID
        )
        return _NER_PIPE
    except Exception as e:
        print(f"[NER] load failed: {e}")
        return None

def extract_entities(text: str) -> List[Dict]:
    """يُرجع قائمة كيانات: {word, entity_group, score, start, end}. يسقط بصمت إن لم يتوفر النموذج."""
    if not text: return []
    ner = _load_ner_pipe()
    if ner is None: return []
    try:
        res = ner(text)
        # توحيد الحقول
        out = []
        for r in res:
            out.append({
                "word": r.get("word",""),
                "label": r.get("entity_group") or r.get("entity",""),
                "score": float(r.get("score", 0.0)),
                "start": int(r.get("start", 0)),
                "end": int(r.get("end", 0)),
            })
        return out
    except Exception as e:
        print(f"[NER] inference failed: {e}")
        return []

def _summarize_abstractive(text: str) -> str:
    """ينفذ التلخيص باستخدام Transformers Pipeline."""
    p = _load_abstractive_pipe()
    if p is None: return ""
    try:
        prompt = f"لخّص المقطع التالي بأسلوب عربي فصيح وواضح:\n{text}"
        out = p(prompt, max_length=400, min_length=100, do_sample=False, num_beams=4)
        summary = (out[0].get("summary_text") or "").strip()
        if summary:
            set_summary_source(f"transformers:{settings.SUMMARIZER_MODEL}")
        return summary
    except Exception as e:
        print(f"[TF] mT5 summarize failed: {e}")
        return ""

def _summarize_ultra(prompt: str) -> str:
    # TODO: أضف هنا المنطق الخاص بنموذج Jais-13B
    print("[SUM] Ultra mode (Jais-13B) is not implemented yet.")
    set_summary_source("ultra:not_implemented")
    return ""

def summarize(text: str, mode: str = "lite") -> Tuple[str, str]:
    if not text or not mode or mode == "off":
        set_summary_source("off")
        return ("", "")
        
    clean = _advanced_clean_text(text) # <-- إصلاح الخطأ
    m = mode.lower()

    if m == "lite":
        sentences = [s.strip() for s in re.split(r'[.!?؟]+', clean) if s.strip()]
        if not sentences:
            extractive_summary = clean
        else:
            scored_sentences = score_sentences_by_tfidf(sentences)
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            num_top_sentences = max(5, min(7, int(len(sentences) * 0.3)))
            top_sentences = [s for s, score in scored_sentences[:num_top_sentences]]
            extractive_summary = " ".join(top_sentences)

        TH = int(os.getenv("SUM_LITE_ABS_THRESHOLD", "5"))
        if len(extractive_summary.split()) < TH:
            print("[SUM] lite -> using extractive summary directly (already short).")
            summary_text = extractive_summary
            set_summary_source("extractive:tfidf")
        else:
            print(f"[SUM] lite (hybrid) -> processing {len(extractive_summary)} chars from top sentences.")
            summary_text = _summarize_abstractive(extractive_summary)

    elif m == "ultra":
        print("[SUM] ultra -> Jais-13B-Chat")
        ctx = _rag_retrieve(clean, k=3)
        prompt = f"السياق المسترجع:\n{ctx}\n\nالنص:\n{clean}" if ctx else clean
        summary_text = _summarize_ultra(prompt)
    else:
        raise HTTPException(status_code=400, detail=f"unsupported summary_mode: {mode}")
    
    keywords = extract_keywords(clean) if summary_text else ""
    return (summary_text, keywords)

# ===== RAG (Retrieval-Augmented Generation) =====

_rag_index, _rag_model, _rag_texts, _rag_dim = None, None, [], None

def _rag_load():
    global _rag_index, _rag_model, _rag_texts, _rag_dim
    if not settings.RAG_ENABLED or _rag_index is not None: return
    if not (_FAISS_OK and _ST_OK): return print("[RAG] disabled (faiss or sentence-transformers missing).")
    
    _RAG_INDEX = settings.RAG_DIR / "index.faiss"
    _RAG_DOCS = settings.RAG_DIR / "docs.jsonl"
    if not _RAG_INDEX.exists() or not _RAG_DOCS.exists(): return print("[RAG] no ArabicText-Large index found.")

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

def _rag_retrieve(query: str, k: int = 6) -> str:
    if not query.strip(): return ""
    _rag_load()
    if _rag_index is None: return ""
    
    try:
        qv = _rag_model.encode([f"query: {query}"], normalize_embeddings=True)
        D, I = _rag_index.search(np.asarray(qv, dtype="float32"), max(1, min(k, _rag_index.ntotal)))
        return "\n\n".join(_rag_texts[i] for i in I[0] if i < len(_rag_texts)).strip()
    except Exception as e:
        print(f"[RAG] search failed: {e}")
        return ""