# nlp/summarization.py — التلخيص (lite/ultra)
import os
import re
from typing import Tuple

from fastapi import HTTPException
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

from config import settings
from nlp.text_utils import advanced_clean_text, set_summary_source, get_summary_source
from nlp.keywords import score_sentences_by_tfidf, extract_keywords
from nlp.models_loader import ensure_local
from nlp.rag import rag_retrieve

_ABST_PIPE = None


def _load_abstractive_pipe():
    global _ABST_PIPE
    if _ABST_PIPE is not None:
        return _ABST_PIPE
    try:
        print("[SUM] Loading summarization model with Transformers...")
        local_path = ensure_local(settings.SUMMARIZER_MODEL, "summarizers/mT5_XLSum")
        tok = AutoTokenizer.from_pretrained(local_path, token=settings.HF_TOKEN, use_fast=False)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(local_path, token=settings.HF_TOKEN)
        _ABST_PIPE = pipeline(
            "summarization", model=mdl, tokenizer=tok, device=settings.HF_DEVICE_ID
        )
        print("[SUM] Transformers summarizer loaded.")
        return _ABST_PIPE
    except Exception as e:
        print(f"[TF] mT5 load failed: {e}")
        return None


def _summarize_abstractive(text: str) -> str:
    p = _load_abstractive_pipe()
    if p is None:
        return ""
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
    print("[SUM] Ultra mode (Jais-13B) is not implemented yet.")
    set_summary_source("ultra:not_implemented")
    return ""


def summarize(text: str, mode: str = "lite") -> Tuple[str, str]:
    if not text or not mode or mode == "off":
        set_summary_source("off")
        return ("", "")
    clean = advanced_clean_text(text)
    m = mode.lower()
    if m == "lite":
        sentences = [s.strip() for s in re.split(r"[.!?؟]+", clean) if s.strip()]
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
        ctx = rag_retrieve(clean, k=3)
        prompt = f"السياق المسترجع:\n{ctx}\n\nالنص:\n{clean}" if ctx else clean
        summary_text = _summarize_ultra(prompt)
    else:
        raise HTTPException(status_code=400, detail=f"unsupported summary_mode: {mode}")
    keywords = extract_keywords(clean) if summary_text else ""
    return (summary_text, keywords)
