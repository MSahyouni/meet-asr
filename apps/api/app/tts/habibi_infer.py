"""Habibi/F5-TTS inference — long-form via official batch path + hard Arabic chunking."""
from __future__ import annotations

import logging
import os
import re
from typing import List, Optional, Tuple

import numpy as np
import torch
import torchaudio

logger = logging.getLogger("tts_habibi.infer")

HOP_LENGTH = 256
TARGET_SAMPLE_RATE = 24000
# ~2 Arabic lines in UTF-8 bytes — quality sweet spot per batch.
DEFAULT_MAX_CHUNK_BYTES = 120
# Merge leftovers smaller than this into a neighbor (avoids 1–2s stutter clips).
MIN_CHUNK_BYTES = 40
# Stay under Habibi/F5 comfort zone for ref+gen mel length.
DURATION_BUDGET_FRAC = 0.85
CROSSFADE_SEC = 0.22
SENTENCE_GAP_SEC = 0.08


def normalize_habibi_ref_text(ref_text: str) -> str:
    """Match Habibi/F5 expectation: sentence end + trailing space."""
    text = re.sub(r"\s+", " ", (ref_text or "").strip())
    if not text:
        return text
    if text.endswith(". "):
        return text
    if text.endswith("."):
        return text + " "
    text = text.rstrip(" .،,؛;:!?！？")
    return text + ". "


def normalize_habibi_gen_text(gen_text: str, ref_text: str = "") -> str:
    """Strip accidental ref prefix; do not force a leading space (ref already ends with '. ')."""
    gen = re.sub(r"\s+", " ", (gen_text or "").strip())
    if not gen:
        return gen
    ref_norm = (ref_text or "").strip().rstrip(".。！？ ").strip()
    if ref_norm and gen.startswith(ref_norm):
        gen = gen[len(ref_norm) :].lstrip(" .،,؛")
    return gen


def _max_chunk_bytes_cap(override: Optional[int] = None) -> int:
    if override is not None:
        try:
            return max(48, min(220, int(override)))
        except (TypeError, ValueError):
            pass
    raw = (os.environ.get("HABIBI_MAX_CHUNK_CHARS") or os.environ.get("HABIBI_MAX_CHUNK_BYTES") or "").strip()
    if raw.isdigit():
        return max(48, min(220, int(raw)))
    return DEFAULT_MAX_CHUNK_BYTES


def _utf8_len(text: str) -> int:
    return len((text or "").encode("utf-8"))


def _force_split_by_words(text: str, max_bytes: int) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if _utf8_len(text) <= max_bytes:
        return [text]
    words = text.split(" ")
    chunks: List[str] = []
    current = ""
    for word in words:
        if not word:
            continue
        if _utf8_len(word) > max_bytes:
            if current:
                chunks.append(current)
                current = ""
            raw = word.encode("utf-8")
            while raw:
                piece = raw[:max_bytes].decode("utf-8", errors="ignore").strip()
                raw = raw[len(piece.encode("utf-8")) :] if piece else raw[max_bytes:]
                if piece:
                    chunks.append(piece)
            continue
        candidate = f"{current} {word}".strip()
        if not current or _utf8_len(candidate) <= max_bytes:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks


def _split_habibi_batches(gen_text: str, max_bytes: int) -> List[str]:
    """
    Prefer strong sentence ends (.!?؟) so commas don't create tiny stutter clips.
    Hard UTF-8 cap still applies; Habibi's own chunk_text keeps oversize sentences.
    """
    text = re.sub(r"\s+", " ", (gen_text or "").strip())
    if not text:
        return []
    # Strong boundaries only — Arabic comma/colon stay inside the chunk when possible.
    pieces = re.split(r"(?<=[\.\!\?؟])\s+", text)
    batches: List[str] = []
    current = ""
    for piece in pieces:
        sentence = piece.strip()
        if not sentence:
            continue
        if _utf8_len(sentence) > max_bytes:
            if current:
                batches.append(current)
                current = ""
            # Soft-split long sentences on commas, then words.
            clause_parts = re.split(r"(?<=[،,;؛:])\s+", sentence)
            for clause in clause_parts:
                clause = clause.strip()
                if not clause:
                    continue
                if _utf8_len(clause) > max_bytes:
                    if current:
                        batches.append(current)
                        current = ""
                    batches.extend(_force_split_by_words(clause, max_bytes))
                    continue
                candidate = f"{current} {clause}".strip()
                if not current or _utf8_len(candidate) <= max_bytes:
                    current = candidate
                else:
                    batches.append(current)
                    current = clause
            continue
        candidate = f"{current} {sentence}".strip()
        if not current or _utf8_len(candidate) <= max_bytes:
            current = candidate
        else:
            batches.append(current)
            current = sentence
    if current:
        batches.append(current)
    return _coalesce_batches(batches, max_bytes=max_bytes, min_bytes=MIN_CHUNK_BYTES)


def _coalesce_batches(batches: List[str], *, max_bytes: int, min_bytes: int) -> List[str]:
    """Merge tiny fragments into neighbors so crossfades aren't every 1–2 seconds."""
    if not batches:
        return []
    merged: List[str] = []
    for batch in batches:
        b = batch.strip()
        if not b:
            continue
        if not merged:
            merged.append(b)
            continue
        if _utf8_len(b) < min_bytes:
            candidate = f"{merged[-1]} {b}".strip()
            if _utf8_len(candidate) <= max_bytes:
                merged[-1] = candidate
            else:
                merged.append(b)
            continue
        # Also pull a trailing tiny previous into this one when previous is undersized.
        if _utf8_len(merged[-1]) < min_bytes:
            candidate = f"{merged[-1]} {b}".strip()
            if _utf8_len(candidate) <= max_bytes:
                merged[-1] = candidate
            else:
                merged.append(b)
        else:
            merged.append(b)
    # Final pass: if last chunk is tiny, fold into previous.
    if len(merged) >= 2 and _utf8_len(merged[-1]) < min_bytes:
        candidate = f"{merged[-2]} {merged[-1]}".strip()
        if _utf8_len(candidate) <= max_bytes:
            merged[-2] = candidate
            merged.pop()
    return merged


def _habibi_chunk_gen_text(
    gen_text: str,
    ref_audio_path: str,
    ref_text: str,
    max_chunk_override: Optional[int] = None,
) -> Tuple[List[str], int]:
    audio, sr = torchaudio.load(ref_audio_path)
    audio_secs = max(0.5, float(audio.shape[-1]) / float(sr))
    ref_bytes = max(1, _utf8_len(ref_text))

    # Same heuristic as Habibi infer_process, then clamp to our sweet spot.
    dynamic = int(ref_bytes / audio_secs * max(1.0, 22.0 - audio_secs))
    # Leave headroom so ref+gen never sits on the ~30s training comfort edge.
    budget_secs = max(4.0, (22.0 - audio_secs) * DURATION_BUDGET_FRAC)
    max_by_duration = int(ref_bytes / audio_secs * budget_secs)
    max_bytes = max(
        48,
        min(dynamic if dynamic > 0 else 110, max_by_duration, _max_chunk_bytes_cap(max_chunk_override)),
    )

    batches = _split_habibi_batches(gen_text, max_bytes=max_bytes)
    logger.info(
        "Habibi chunk plan: batches=%d max_bytes=%d sizes=%s",
        len(batches),
        max_bytes,
        [_utf8_len(b) for b in batches],
    )
    return batches, max_bytes


def _nfe_step(device: str) -> int:
    raw = (os.environ.get("HABIBI_NFE_STEP") or "").strip()
    if raw.isdigit():
        return int(raw)
    return 16 if device == "cpu" else 32


def _ends_sentence(text: str) -> bool:
    t = (text or "").rstrip()
    return bool(t) and t[-1] in ".!?؟"


def _simple_crossfade(
    waves: List[np.ndarray],
    sample_rate: int,
    *,
    batch_texts: Optional[List[str]] = None,
    crossfade_sec: float = CROSSFADE_SEC,
) -> np.ndarray:
    """Join batches with a slightly longer crossfade; short pause after sentence ends."""
    if not waves:
        return np.array([], dtype=np.float32)
    if len(waves) == 1:
        return np.asarray(waves[0], dtype=np.float32)

    for i, w in enumerate(waves):
        w = np.asarray(w, dtype=np.float32)
        rms = float(np.sqrt(np.mean(np.square(w)) + 1e-12))
        logger.info(
            "Habibi concat chunk %d/%d: dur=%.2fs rms=%.4f peak=%.3f",
            i + 1,
            len(waves),
            len(w) / float(sample_rate),
            rms,
            float(np.max(np.abs(w))) if w.size else 0.0,
        )

    final = np.asarray(waves[0], dtype=np.float32)
    fade_samples = int(crossfade_sec * sample_rate)
    gap = np.zeros(int(SENTENCE_GAP_SEC * sample_rate), dtype=np.float32)
    for i, nxt in enumerate(waves[1:], start=1):
        nxt = np.asarray(nxt, dtype=np.float32)
        prev_text = batch_texts[i - 1] if batch_texts and i - 1 < len(batch_texts) else ""
        if _ends_sentence(prev_text) and gap.size:
            final = np.concatenate([final, gap])
        fade_n = min(fade_samples, len(final), len(nxt))
        if fade_n <= 0:
            final = np.concatenate([final, nxt])
            continue
        fade_out = np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
        fade_in = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
        overlap = final[-fade_n:] * fade_out + nxt[:fade_n] * fade_in
        final = np.concatenate([final[:-fade_n], overlap, nxt[fade_n:]])
    return final.astype(np.float32)


def _synthesize_batches_sequential(
    ref_audio_path: str,
    ref_text: str,
    batches: List[str],
    runtime: dict,
    *,
    nfe_step: int,
) -> Tuple[np.ndarray, int]:
    """
    Official Habibi semantics: same original ref for every batch (no continuation),
    sequential on GPU to avoid ThreadPool CUDA contention.
    """
    from habibi_tts.infer.utils_infer import (
        cfg_strength,
        hop_length,
        mel_spec_type,
        sway_sampling_coef,
        target_rms,
        target_sample_rate,
    )
    from habibi_tts.model.utils import text_list_formatter

    device = runtime["device"]
    dialect_id = runtime.get("dialect_id")

    audio, sr = torchaudio.load(ref_audio_path)
    if audio.shape[0] > 1:
        audio = torch.mean(audio, dim=0, keepdim=True)
    rms = torch.sqrt(torch.mean(torch.square(audio)))
    if rms < target_rms:
        audio = audio * target_rms / rms
    if sr != target_sample_rate:
        audio = torchaudio.transforms.Resample(sr, target_sample_rate)(audio)
    audio = audio.to(device)

    if ref_text and len(ref_text[-1].encode("utf-8")) == 1:
        ref_text = ref_text + " "

    waves: List[np.ndarray] = []
    kept_texts: List[str] = []
    import time as _time

    for idx, gen_text in enumerate(batches):
        gen_text = (gen_text or "").strip()
        if not gen_text:
            continue
        local_speed = 0.3 if _utf8_len(gen_text) < 10 else 1.0
        text_list = [ref_text + gen_text]
        final_text_list = text_list_formatter(text_list, dialect_id=dialect_id)

        ref_audio_len = audio.shape[-1] // hop_length
        ref_text_len = max(1, _utf8_len(ref_text))
        gen_text_len = max(1, _utf8_len(gen_text))
        # Exact Habibi duration formula (no extra safety inflate / hard mel clamp).
        duration = ref_audio_len + int(ref_audio_len / ref_text_len * gen_text_len / local_speed)

        _t0 = _time.monotonic()
        with torch.inference_mode():
            generated, _ = runtime["model"].sample(
                cond=audio,
                text=final_text_list,
                duration=duration,
                steps=nfe_step,
                cfg_strength=cfg_strength,
                sway_sampling_coef=sway_sampling_coef,
            )
            generated = generated.to(torch.float32)
            generated = generated[:, ref_audio_len:, :]
            generated = generated.permute(0, 2, 1)
            if mel_spec_type == "vocos":
                generated_wave = runtime["vocoder"].decode(generated)
            else:
                generated_wave = runtime["vocoder"](generated)
            if rms < target_rms:
                generated_wave = generated_wave * rms / target_rms
            wave = generated_wave.squeeze().cpu().numpy().astype(np.float32)

        logger.info(
            "Habibi batch %d/%d done in %.1fs (device=%s, nfe_step=%d, chars=%d, dur_frames=%d, wave_s=%.2f, rms=%.4f)",
            idx + 1,
            len(batches),
            _time.monotonic() - _t0,
            device,
            nfe_step,
            _utf8_len(gen_text),
            duration,
            len(wave) / float(target_sample_rate),
            float(np.sqrt(np.mean(np.square(wave)) + 1e-12)),
        )
        waves.append(wave)
        kept_texts.append(gen_text)

    final = _simple_crossfade(waves, target_sample_rate, batch_texts=kept_texts)
    return final, int(target_sample_rate)


def run_habibi_inference(
    ref_audio_ready: str,
    ref_text_ready: str,
    gen_text: str,
    runtime: dict,
    max_chunk_chars: Optional[int] = None,
):
    """
    Long-form Habibi synthesis.

    Uses the official conditioning pattern (fixed speaker ref for every chunk) plus
    hard Arabic chunking so no batch exceeds the quality sweet spot.
    """
    ref_text_ready = normalize_habibi_ref_text(ref_text_ready)
    gen_text = normalize_habibi_gen_text(gen_text, ref_text_ready)

    batches, max_bytes = _habibi_chunk_gen_text(
        gen_text,
        ref_audio_ready,
        ref_text_ready,
        max_chunk_override=max_chunk_chars,
    )
    if not batches:
        raise RuntimeError("Habibi: empty text after chunking")

    nfe = _nfe_step(str(runtime.get("device", "cpu")))
    logger.info(
        "Habibi inference: mode=official-anchored batches=%d max_bytes=%d nfe=%d ref_text=%r",
        len(batches),
        max_bytes,
        nfe,
        ref_text_ready[:80],
    )

    return _synthesize_batches_sequential(
        ref_audio_ready,
        ref_text_ready,
        batches,
        runtime,
        nfe_step=nfe,
    )
