# nlp/punctuation_ner.py — ترقيم عربي و NER
import re
from typing import List, Dict

from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

from config import settings
from nlp.models_loader import ensure_local

_PUNCT_PIPE = None
_NER_PIPE = None


def _load_punct_pipe():
    global _PUNCT_PIPE
    if _PUNCT_PIPE is not None:
        return _PUNCT_PIPE
    try:
        local_path = ensure_local(settings.PUNCT_MODEL, "punctuation/arabic_punct")
        tok = AutoTokenizer.from_pretrained(local_path, token=settings.HF_TOKEN, use_fast=False)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(local_path, token=settings.HF_TOKEN)
        _PUNCT_PIPE = pipeline(
            "text2text-generation", model=mdl, tokenizer=tok, device=settings.HF_DEVICE_ID
        )
        return _PUNCT_PIPE
    except Exception as e:
        print(f"[PUNCT] load failed: {e}")
        return None


def restore_punct(text: str, max_len: int = 512) -> str:
    if not text:
        return ""
    p = _load_punct_pipe()
    if p is None:
        return text
    parts = [t.strip() for t in re.split(r"[\n]", text) if t.strip()]
    out = []
    for part in parts:
        words = part.split()
        if not words:
            continue
        for i in range(0, len(words), max_len):
            chunk = " ".join(words[i : i + max_len])
            try:
                y = p(chunk, max_new_tokens=max_len, do_sample=False)[0]["generated_text"]
                out.append(y.strip())
            except Exception:
                out.append(chunk)
    return "\n".join(out)


def _load_ner_pipe():
    global _NER_PIPE
    if _NER_PIPE is not None:
        return _NER_PIPE
    try:
        local_path = ensure_local(settings.NER_MODEL, "ner/arabic_ner")
        _NER_PIPE = pipeline(
            "token-classification",
            model=local_path,
            tokenizer=local_path,
            aggregation_strategy="simple",
            device=settings.HF_DEVICE_ID,
        )
        return _NER_PIPE
    except Exception as e:
        print(f"[NER] load failed: {e}")
        return None


def extract_entities(text: str) -> List[Dict]:
    if not text:
        return []
    ner = _load_ner_pipe()
    if ner is None:
        return []
    try:
        res = ner(text)
        out = []
        for r in res:
            out.append({
                "word": r.get("word", ""),
                "label": r.get("entity_group") or r.get("entity", ""),
                "score": float(r.get("score", 0.0)),
                "start": int(r.get("start", 0)),
                "end": int(r.get("end", 0)),
            })
        return out
    except Exception as e:
        print(f"[NER] inference failed: {e}")
        return []
