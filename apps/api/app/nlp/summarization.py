# nlp/summarization.py — تلخيص Jais-2 فقط (محاضر اجتماعات + map-reduce)
import os
import re
from typing import List, Tuple

from fastapi import HTTPException
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM

from ..config import settings
from .text_utils import advanced_clean_text, polish_summary_ar, set_summary_source
from .keywords import extract_keywords
from .models_loader import ensure_local
from .rag import rag_retrieve
from .prompts import build_ultra_messages, build_ultra_prompt, normalize_prompt_mode

_ULTRA_PIPE = None
_ULTRA_TOKENIZER = None
_ULTRA_LOAD_LOCK = None


def _ultra_lock():
    global _ULTRA_LOAD_LOCK
    if _ULTRA_LOAD_LOCK is None:
        import threading

        _ULTRA_LOAD_LOCK = threading.RLock()
    return _ULTRA_LOAD_LOCK


def _release_asr_before_nlp() -> None:
    flag = os.getenv("SUM_RELEASE_ASR_GPU", "1").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return
    try:
        from app.asr import release_asr_gpu

        release_asr_gpu(reason="summarize")
    except Exception as e:
        print(f"[SUM] ASR GPU release skipped: {e}")


def unload_summarizer_pipes(which: str = "all") -> None:
    """which: all | jais (أسماء قديمة ultra/lite مقبولة)."""
    global _ULTRA_PIPE, _ULTRA_TOKENIZER
    w = (which or "all").lower()
    if w in ("all", "jais", "jais2", "ultra", "lite") and _ULTRA_PIPE is not None:
        try:
            del _ULTRA_PIPE
        except Exception:
            pass
        _ULTRA_PIPE = None
        _ULTRA_TOKENIZER = None
        print("[SUM] jais2 unloaded")
    try:
        from app.infrastructure.gpu_memory import cuda_empty_cache

        cuda_empty_cache(reason=f"unload_summarizer:{w}")
    except Exception:
        pass


def warm_ultra_in_background() -> None:
    """حمّل Jais-2 مسبقاً بعد انتهاء ASR حتى يكون التلخيص التالي أسرع."""
    flag = (
        os.getenv("SUM_WARM_JAIS")
        or os.getenv("SUM_WARM_ULTRA")
        or "1"
    ).strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return
    if _ULTRA_PIPE is not None:
        return

    import threading

    def _run() -> None:
        try:
            print("[SUM] warming jais2 in background…")
            _load_ultra_pipe()
            print("[SUM] jais2 warm ready")
        except Exception as e:
            print(f"[SUM] jais2 warm skipped: {e}")

    threading.Thread(target=_run, daemon=True, name="warm-jais2").start()


def warm_jais_in_background() -> None:
    warm_ultra_in_background()


def schedule_warm_ultra_after_asr() -> None:
    """حرّر Whisper ثم ابدأ تسخين Jais-2 (بعد إنهاء تفريغ)."""
    try:
        _release_asr_before_nlp()
    except Exception as e:
        print(f"[SUM] ASR release before warm skipped: {e}")
    warm_ultra_in_background()


def schedule_warm_jais_after_asr() -> None:
    schedule_warm_ultra_after_asr()


def _estimate_tokens(text: str) -> int:
    """تقدير تقريبي لطول المدخلات (كلمات ≈ توكنات للعربية في أغلب النماذج)."""
    words = len(text.split())
    chars = len(text)
    return max(words, chars // 3, 1)


def _split_sentences(text: str) -> List[str]:
    parts = [s.strip() for s in re.split(r"(?<=[.!?؟\n])\s+", text) if s.strip()]
    if parts:
        return parts
    return [text.strip()] if text.strip() else []


def _split_into_chunks(text: str, max_tokens: int, max_parts: int) -> List[str]:
    """قسّم النص إلى أجزاء لا تتجاوز max_tokens تقريباً، بحد أقصى max_parts."""
    clean = (text or "").strip()
    if not clean:
        return []
    if _estimate_tokens(clean) <= max_tokens or max_parts <= 1:
        return [clean]

    sentences = _split_sentences(clean)
    chunks: List[str] = []
    current: List[str] = []
    current_tokens = 0

    for idx, sent in enumerate(sentences):
        st = _estimate_tokens(sent)
        if current and current_tokens + st > max_tokens:
            chunks.append(" ".join(current).strip())
            current = [sent]
            current_tokens = st
            if len(chunks) >= max_parts - 1:
                rest = [sent] + sentences[idx + 1 :]
                chunks.append(" ".join(rest).strip())
                return [c for c in chunks if c]
        else:
            current.append(sent)
            current_tokens += st

    if current:
        chunks.append(" ".join(current).strip())

    if len(chunks) > max_parts:
        head = chunks[: max_parts - 1]
        tail = " ".join(chunks[max_parts - 1 :])
        chunks = head + [tail]

    return [c for c in chunks if c]


def _summarize_ultra(text: str, stage: str = "final") -> str:
    p = _load_ultra_pipe()
    if p is None:
        return ""
    try:
        import torch

        max_new_tokens = max(120, int(os.getenv("SUM_ULTRA_MAX_NEW_TOKENS", "280")))
        prompt_mode = normalize_prompt_mode(settings.JAIS_PROMPT_MODE)
        tok = _ULTRA_TOKENIZER or getattr(p, "tokenizer", None)
        model = getattr(p, "model", None)
        messages = build_ultra_messages(text, prompt_mode=prompt_mode, stage=stage)

        if tok is None or model is None:
            print("[ULTRA] missing tokenizer/model after load")
            return ""

        if getattr(tok, "pad_token_id", None) is None and getattr(tok, "eos_token_id", None) is not None:
            tok.pad_token = tok.eos_token

        # Tokenize via chat template directly (avoids double BOS/EOS from re-encoding).
        try:
            inputs = tok.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
                tokenize=True,
            )
        except TypeError:
            prompt_text = tok.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = tok(prompt_text, return_tensors="pt", add_special_tokens=False)

        if hasattr(inputs, "items"):
            inputs = dict(inputs)
        inputs.pop("token_type_ids", None)

        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        try:
            for param in model.parameters():
                if getattr(param, "device", None) is not None and param.device.type != "meta":
                    device = param.device
                    break
        except Exception:
            pass
        inputs = {k: v.to(device) for k, v in inputs.items() if hasattr(v, "to")}

        eos_id = getattr(tok, "eos_token_id", None)
        pad_id = getattr(tok, "pad_token_id", None) or eos_id
        bos_id = getattr(tok, "bos_token_id", None)
        # Jais-2 collapses to BOS (id=0) under bad dtype/settings — suppress it.
        suppress = [i for i in (bos_id, 0) if i is not None]
        suppress = sorted(set(suppress))

        def _run_generate(**extra):
            with torch.inference_mode():
                return model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=pad_id,
                    eos_token_id=eos_id,
                    suppress_tokens=suppress,
                    **extra,
                )

        out_ids = _run_generate(do_sample=False, repetition_penalty=1.05)
        prompt_len = inputs["input_ids"].shape[-1]
        gen_ids = out_ids[0][prompt_len:]
        summary = tok.decode(gen_ids, skip_special_tokens=True).strip()

        if not summary:
            raw = tok.decode(gen_ids, skip_special_tokens=False).strip()
            print(f"[ULTRA] greedy empty gen_len={int(gen_ids.shape[0])} raw={raw[:200]!r}")
            # Retry with light sampling — helps when 4bit greedy collapses.
            out_ids = _run_generate(
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.05,
            )
            gen_ids = out_ids[0][prompt_len:]
            summary = tok.decode(gen_ids, skip_special_tokens=True).strip()
            if not summary:
                raw = tok.decode(gen_ids, skip_special_tokens=False).strip()
                print(f"[ULTRA] sample empty gen_len={int(gen_ids.shape[0])} raw={raw[:200]!r}")

        if summary:
            summary = polish_summary_ar(summary)
            set_summary_source(f"jais2:{settings.JAIS_MODEL}")
        else:
            print("[SUM] jais2 produced empty text")
        return summary
    except Exception as e:
        import traceback

        print(f"[SUM] jais2 failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return ""


def _load_ultra_pipe():
    global _ULTRA_PIPE, _ULTRA_TOKENIZER
    with _ultra_lock():
        if _ULTRA_PIPE is not None:
            return _ULTRA_PIPE
        return _load_ultra_pipe_unlocked()


def _load_ultra_pipe_unlocked():
    global _ULTRA_PIPE, _ULTRA_TOKENIZER
    if _ULTRA_PIPE is not None:
        return _ULTRA_PIPE
    try:
        _release_asr_before_nlp()
        # transformers>=5 (Jais-2) imports DTensor; torch 2.4 exposes it under _tensor.
        try:
            from app.infrastructure.torch_compat import ensure_dtensor_export

            ensure_dtensor_export()
        except Exception:
            pass
        print("[SUM] Loading Jais-2 summarizer…")
        allow_download = (
            os.getenv("JAIS_ALLOW_DOWNLOAD")
            or os.getenv("ULTRA_ALLOW_DOWNLOAD")
            or "0"
        ).strip().lower() in ("1", "true", "yes")
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", settings.JAIS_MODEL.strip())
        # Prefer existing local install under summarizers/ultra/ (no re-download).
        from pathlib import Path

        ultra_dir = Path(settings.MODELS_DIR) / "summarizers" / "ultra" / slug
        jais_subdir = f"summarizers/ultra/{slug}" if ultra_dir.exists() else f"summarizers/jais2/{slug}"
        local_path = ensure_local(settings.JAIS_MODEL, jais_subdir, allow_download=allow_download)
        # Jais-2 ships tokenizer.json only — slow path (use_fast=False) raises NotImplementedError.
        tok = AutoTokenizer.from_pretrained(
            local_path,
            token=settings.HF_TOKEN,
            trust_remote_code=settings.JAIS_TRUST_REMOTE,
            use_fast=True,
        )
        _ULTRA_TOKENIZER = tok

        try:
            import torch

            use_cuda = bool(torch.cuda.is_available())
        except Exception:
            torch = None  # type: ignore
            use_cuda = False

        if use_cuda:
            try:
                from app.infrastructure.gpu_memory import cuda_empty_cache

                cuda_empty_cache(reason="ultra_load")
            except Exception:
                pass

        if settings.JAIS_4BIT and use_cuda and torch is not None:
            try:
                from transformers import BitsAndBytesConfig

                # 8B 4bit ≈ 5GB; pin to GPU0 so bitsandbytes does not refuse partial CPU offload.
                bnb_cfg = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    # Jais-2 weights are bf16; fp16 compute collapses logits to BOS.
                    bnb_4bit_compute_dtype=torch.bfloat16,
                )
                model = AutoModelForCausalLM.from_pretrained(
                    local_path,
                    token=settings.HF_TOKEN,
                    trust_remote_code=settings.JAIS_TRUST_REMOTE,
                    quantization_config=bnb_cfg,
                    device_map={"": 0},
                    torch_dtype=torch.bfloat16,
                )
                _ULTRA_PIPE = pipeline("text-generation", model=model, tokenizer=tok)
                print("[SUM] Jais-2 loaded (4bit).")
                return _ULTRA_PIPE
            except Exception as e:
                print(f"[SUM] Jais-2 4bit unavailable, fallback: {e}")

        # Full fp16 8B needs ~16GB+ VRAM; on laptop GPUs keep CPU offload without disk.
        max_memory = None
        if use_cuda and torch is not None:
            try:
                free_bytes, _total = torch.cuda.mem_get_info(0)
                free_gb = max(2.0, (free_bytes / (1024**3)) - 0.5)
                max_memory = {0: f"{free_gb:.1f}GiB", "cpu": "48GiB"}
            except Exception:
                max_memory = {0: "5GiB", "cpu": "48GiB"}

        model = AutoModelForCausalLM.from_pretrained(
            local_path,
            token=settings.HF_TOKEN,
            trust_remote_code=settings.JAIS_TRUST_REMOTE,
            torch_dtype=(torch.float16 if use_cuda and torch is not None else None),
            device_map="auto" if use_cuda else None,
            max_memory=max_memory,
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

        print("[SUM] Jais-2 loaded.")
        return _ULTRA_PIPE
    except Exception as e:
        import traceback

        print(f"[SUM] jais2 model load failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


def _summarize_ultra_long(text: str) -> str:
    """Map-reduce: لخّص الأجزاء ثم وحّدها في محضر واحد."""
    max_tokens = settings.SUM_MAX_INPUT_TOKENS
    max_parts = settings.SUM_MAX_PARTS
    chunks = _split_into_chunks(text, max_tokens=max_tokens, max_parts=max_parts)

    if not chunks:
        return ""

    if len(chunks) == 1:
        print(f"[SUM] jais2 -> single chunk (~{_estimate_tokens(chunks[0])} tok)")
        return _summarize_ultra(chunks[0], stage="final")

    print(f"[SUM] jais2 map-reduce -> {len(chunks)} parts (max_tokens={max_tokens})")
    partials: List[str] = []
    for i, chunk in enumerate(chunks):
        print(f"[SUM] jais2 part {i + 1}/{len(chunks)} (~{_estimate_tokens(chunk)} tok)")
        part = _summarize_ultra(chunk, stage="partial")
        if part:
            partials.append(part)
        else:
            preview = " ".join(chunk.split()[:80])
            if preview:
                partials.append(preview)

    if not partials:
        return ""
    if len(partials) == 1:
        return partials[0]

    merged_input = "\n\n".join(f"ملخص الجزء {i + 1}:\n{p}" for i, p in enumerate(partials))
    merge_chunks = _split_into_chunks(merged_input, max_tokens=max_tokens, max_parts=max(2, max_parts // 2))
    if len(merge_chunks) == 1:
        final = _summarize_ultra(merge_chunks[0], stage="final")
        return final or merged_input

    mid = []
    for mc in merge_chunks:
        mid_sum = _summarize_ultra(mc, stage="partial")
        mid.append(mid_sum or mc)
    final_input = "\n\n".join(f"ملخص الجزء {i + 1}:\n{p}" for i, p in enumerate(mid))
    final = _summarize_ultra(final_input, stage="final")
    return final or final_input


def _normalize_summary_mode(mode: str) -> str:
    """Jais-2 فقط. off يعطّل. أسماء قديمة (ultra/lite) تُقبل للتوافق وتُعامل كـ jais."""
    m = (mode or "jais").strip().lower()
    if m in ("off", "none", "0", "false"):
        return "off"
    if m in ("", "jais", "jais2", "jais-2", "ultra", "best", "lite", "light"):
        return "jais"
    raise HTTPException(status_code=400, detail=f"unsupported summary_mode: {mode} (jais only)")


def summarize(text: str, mode: str = "jais") -> Tuple[str, str]:
    if not text:
        set_summary_source("off")
        return ("", "")

    m = _normalize_summary_mode(mode if mode is not None else "jais")
    if m == "off":
        set_summary_source("off")
        return ("", "")

    clean = advanced_clean_text(text, preserve_speakers=True)
    print(f"[SUM] jais2 -> {settings.JAIS_MODEL} (prompt={normalize_prompt_mode(settings.JAIS_PROMPT_MODE)})")
    ctx = rag_retrieve(clean, k=3)
    body = f"السياق المسترجع:\n{ctx}\n\nالنص:\n{clean}" if ctx else clean
    summary_text = _summarize_ultra_long(body)
    if summary_text:
        summary_text = polish_summary_ar(summary_text)
    if not summary_text:
        print("[SUM] jais2 failed")
        set_summary_source("off")

    keywords = extract_keywords(clean) if summary_text else ""
    return (summary_text, keywords)
