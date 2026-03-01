# nlp/summarization.py — التلخيص (lite/ultra)
import os
import re
from typing import Tuple

from fastapi import HTTPException
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM

from ..config import settings
from .text_utils import advanced_clean_text, set_summary_source, get_summary_source
from .keywords import score_sentences_by_tfidf, extract_keywords
from .models_loader import ensure_local
from .rag import rag_retrieve

_ABST_PIPE = None
_ULTRA_PIPE = None


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
    p = _load_ultra_pipe()
    if p is None:
        return ""
    try:
        max_new_tokens = max(120, int(os.getenv("SUM_ULTRA_MAX_NEW_TOKENS", "280")))
        prompt_text = (
            "أنت مساعد تلخيص عربي احترافي. "
            "اكتب ملخصاً عربيًا فصيحًا، دقيقًا، ومركّزًا على الحقائق فقط. "
            "بدون حشو، وبدون تكرار، ويفضّل شكل نقاط قصيرة عند الحاجة.\n\n"
            f"النص:\n{prompt}\n\n"
            "الملخص:"
        )
        out = p(
            prompt_text,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=0.2,
            repetition_penalty=1.12,
            return_full_text=False,
        )
        generated = ""
        if isinstance(out, list) and out:
            generated = (out[0].get("generated_text") or "").strip()
        summary = generated.strip()
        if summary:
            set_summary_source(f"ultra:{settings.ULTRA_MODEL}")
        return summary
    except Exception as e:
        print(f"[ULTRA] summarize failed: {e}")
        return ""


def _load_ultra_pipe():
    global _ULTRA_PIPE
    if _ULTRA_PIPE is not None:
        return _ULTRA_PIPE
    try:
        print("[SUM] Loading ultra Arabic summarizer with Transformers...")
        allow_download = os.getenv("ULTRA_ALLOW_DOWNLOAD", "1").strip().lower() in ("1", "true", "yes")
        local_path = ensure_local(settings.ULTRA_MODEL, "summarizers/ultra", allow_download=allow_download)
        tok = AutoTokenizer.from_pretrained(
            local_path,
            token=settings.HF_TOKEN,
            trust_remote_code=settings.ULTRA_TRUST_REMOTE,
            use_fast=False,
        )

        model = None
        if settings.ULTRA_4BIT:
            try:
                import torch
                from transformers import BitsAndBytesConfig

                bnb_cfg = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.float16,
                )
                model = AutoModelForCausalLM.from_pretrained(
                    local_path,
                    token=settings.HF_TOKEN,
                    trust_remote_code=settings.ULTRA_TRUST_REMOTE,
                    quantization_config=bnb_cfg,
                    device_map="auto",
                )
                _ULTRA_PIPE = pipeline("text-generation", model=model, tokenizer=tok)
                print("[SUM] Ultra summarizer loaded (4bit).")
                return _ULTRA_PIPE
            except Exception as e:
                print(f"[ULTRA] 4bit unavailable, fallback to standard load: {e}")

        try:
            import torch

            use_cuda = bool(torch.cuda.is_available())
        except Exception:
            use_cuda = False

        model = AutoModelForCausalLM.from_pretrained(
            local_path,
            token=settings.HF_TOKEN,
            trust_remote_code=settings.ULTRA_TRUST_REMOTE,
            torch_dtype=(__import__("torch").float16 if use_cuda else None),
            device_map="auto" if use_cuda else None,
        )

        if use_cuda:
            _ULTRA_PIPE = pipeline("text-generation", model=model, tokenizer=tok)
        else:
            _ULTRA_PIPE = pipeline(
                "text-generation",
                model=model,
                tokenizer=tok,
                device=settings.HF_DEVICE_ID,
            )

        print("[SUM] Ultra summarizer loaded.")
        return _ULTRA_PIPE
    except Exception as e:
        print(f"[ULTRA] model load failed: {e}")
        return None


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
        if not summary_text:
            print("[SUM] ultra failed -> fallback to lite abstractive")
            summary_text = _summarize_abstractive(clean)
    else:
        raise HTTPException(status_code=400, detail=f"unsupported summary_mode: {mode}")

    if m == "lite" and not summary_text:
        set_summary_source("extractive:tfidf")
        summary_text = extractive_summary

    keywords = extract_keywords(clean) if summary_text else ""
    return (summary_text, keywords)
