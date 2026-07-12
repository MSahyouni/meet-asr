# nlp/punctuation_ner.py — ترقيم عربي و NER
import re
from typing import List, Dict, Optional

from transformers import (
    pipeline,
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    AutoModelForTokenClassification,
)

from ..config import settings
from .models_loader import ensure_local

_PUNCT_PIPE = None
_NER_PIPE = None

# makdadTaleb/arabic-punctuation-arabert ships generic LABEL_N in config.json;
# real symbols are documented in the model card.
_ARABIC_PUNCT_ID2SYMBOL = {
    0: "",
    1: ".",
    2: "،",
    3: "؟",
    4: "!",
    5: "؛",
    6: ":",
}
_NO_PUNCT_LABELS = {"O", "", "NONE", "NO_PUNCT", "LABEL_0"}
_LEAKED_LABEL_RE = re.compile(r"LABEL_\d+", re.IGNORECASE)


def _punct_from_label(label: str, label_id: Optional[int] = None) -> str:
    """Map model class label/id to an actual punctuation character."""
    if label_id is not None and label_id in _ARABIC_PUNCT_ID2SYMBOL:
        return _ARABIC_PUNCT_ID2SYMBOL[label_id]

    raw = str(label or "").strip()
    if not raw or raw.upper() in _NO_PUNCT_LABELS or raw.upper() == "LABEL_0":
        return ""

    # Generic HF placeholders: LABEL_1 .. LABEL_6
    m = re.fullmatch(r"LABEL_(\d+)", raw, flags=re.IGNORECASE)
    if m:
        return _ARABIC_PUNCT_ID2SYMBOL.get(int(m.group(1)), "")

    # Model already exposes the punctuation character as the label
    if len(raw) <= 2 and not raw.isalnum():
        return raw
    return ""


def _load_punct_pipe():
    global _PUNCT_PIPE
    if _PUNCT_PIPE is not None:
        return _PUNCT_PIPE
    try:
        local_path = ensure_local(
            settings.PUNCT_MODEL,
            "punctuation/arabic_punct",
            hf_repo_id="makdadTaleb/arabic-punctuation-arabert",
            max_download_attempts=3,
        )
        # Most Arabic punctuation restorers are token-classification models.
        # Try token-classification first; fall back to seq2seq if needed.
        try:
            tok = AutoTokenizer.from_pretrained(local_path, token=settings.HF_TOKEN, use_fast=True)
            mdl = AutoModelForTokenClassification.from_pretrained(local_path, token=settings.HF_TOKEN)
            # Override generic LABEL_N so pipeline/debug dumps show real symbols.
            mdl.config.id2label = {i: (sym or "O") for i, sym in _ARABIC_PUNCT_ID2SYMBOL.items()}
            mdl.config.label2id = {(sym or "O"): i for i, sym in _ARABIC_PUNCT_ID2SYMBOL.items()}
            _PUNCT_PIPE = pipeline(
                "token-classification",
                model=mdl,
                tokenizer=tok,
                aggregation_strategy="none",
                device=settings.HF_DEVICE_ID,
            )
            return _PUNCT_PIPE
        except Exception:
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
            chunk_words = words[i : i + max_len]
            chunk = " ".join(chunk_words)
            try:
                if getattr(p, "task", "") == "token-classification":
                    tok = p.tokenizer
                    mdl = p.model
                    enc = tok(
                        chunk_words,
                        is_split_into_words=True,
                        return_tensors="pt",
                        truncation=True,
                        max_length=384,
                    )
                    import torch

                    word_ids = enc.word_ids(batch_index=0)
                    try:
                        device = next(mdl.parameters()).device
                    except Exception:
                        device = torch.device("cpu")
                    model_inputs = {k: v.to(device) for k, v in enc.items()}
                    with torch.no_grad():
                        logits = mdl(**model_inputs).logits
                    pred_ids = logits.argmax(dim=-1)[0].tolist()
                    restored = []
                    prev_word_id = None
                    for token_pred, word_id in zip(pred_ids, word_ids):
                        if word_id is None or word_id == prev_word_id:
                            continue
                        w = chunk_words[word_id]
                        punct = _punct_from_label("", label_id=int(token_pred))
                        if punct:
                            w = w + punct
                        restored.append(w)
                        prev_word_id = word_id
                    restored_text = " ".join(restored).strip() or chunk
                    out.append(_LEAKED_LABEL_RE.sub("", restored_text).strip())
                else:
                    y = p(chunk, max_new_tokens=max_len, do_sample=False)[0]["generated_text"]
                    out.append(_LEAKED_LABEL_RE.sub("", y.strip()))
            except Exception:
                out.append(chunk)
    return "\n".join(out)


def _load_ner_pipe():
    global _NER_PIPE
    if _NER_PIPE is not None:
        return _NER_PIPE
    try:
        local_path = ensure_local(
            settings.NER_MODEL,
            "ner/arabic_ner",
            hf_repo_id="CAMeL-Lab/bert-base-arabic-camelbert-ner",
            max_download_attempts=3,
        )
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
