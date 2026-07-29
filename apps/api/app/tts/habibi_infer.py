"""Habibi/F5-TTS inference helpers — reduce ref_text bleeding and batch repetition."""
from __future__ import annotations

import logging
import os
import pathlib
import re
import tempfile
from typing import List, Tuple

import numpy as np
import soundfile as sf
import torch
import torchaudio

logger = logging.getLogger("tts_habibi.infer")

HOP_LENGTH = 256
TARGET_SAMPLE_RATE = 24000
TAIL_SILENCE_SEC = 1.0
CONTINUATION_REF_SEC = 5.0
REF_AUDIO_MAX_SEC = 10.0
MAX_TOTAL_DURATION_SEC = 28.0
MAX_MEL_FRAMES = int(MAX_TOTAL_DURATION_SEC * TARGET_SAMPLE_RATE / HOP_LENGTH)
DURATION_SAFETY = 1.06


def normalize_habibi_ref_text(ref_text: str) -> str:
    text = re.sub(r"\s+", " ", (ref_text or "").strip())
    if not text:
        return text
    text = text.rstrip(" .،,؛;:!?！？")
    if text[-1] not in ".。！？":
        text += "."
    return text


def normalize_habibi_gen_text(gen_text: str, ref_text: str = "") -> str:
    gen = re.sub(r"\s+", " ", (gen_text or "").strip())
    if not gen:
        return gen
    ref_norm = normalize_habibi_ref_text(ref_text).rstrip(".").strip()
    if ref_norm:
        gen_plain = gen.lstrip()
        if gen_plain.startswith(ref_norm):
            gen = gen_plain[len(ref_norm) :].lstrip(" .،,؛")
    if gen and not gen.startswith(" "):
        gen = " " + gen
    return gen


def append_trailing_silence_wav(wav_path: str, silence_sec: float = TAIL_SILENCE_SEC) -> str:
    data, sr = sf.read(wav_path, dtype="float32", always_2d=False)
    if getattr(data, "ndim", 1) > 1:
        data = np.mean(data, axis=1)
    pad = np.zeros(max(1, int(sr * silence_sec)), dtype=np.float32)
    out = np.concatenate([np.asarray(data, dtype=np.float32), pad])
    sf.write(wav_path, out, sr)
    return wav_path


def _ref_audio_seconds(ref_audio_path: str) -> float:
    audio, sr = torchaudio.load(ref_audio_path)
    if sr <= 0:
        return 0.5
    return min(REF_AUDIO_MAX_SEC, float(audio.shape[-1]) / float(sr))


def _habibi_chunk_gen_text(gen_text: str, ref_audio_path: str, ref_text: str) -> Tuple[List[str], int]:
    from habibi_tts.infer.utils_infer import chunk_text

    audio_secs = _ref_audio_seconds(ref_audio_path)
    ref_bytes = max(1, len(ref_text.encode("utf-8")))
    ref_frames = max(1, int(audio_secs * TARGET_SAMPLE_RATE / HOP_LENGTH))

    # Habibi default heuristic (small chunks when ref audio is long).
    dynamic = int(ref_bytes / max(0.5, audio_secs) * max(1.0, 22.0 - audio_secs))

    # Stay within ~28s total mel frames (ref + generated).
    budget_frames = max(160, MAX_MEL_FRAMES - ref_frames - 24)
    max_gen_bytes_by_duration = int(budget_frames * ref_bytes / ref_frames * 0.90)
    max_chars = max(64, min(dynamic if dynamic > 0 else 120, max_gen_bytes_by_duration, 260))

    batches = chunk_text(gen_text, max_chars=max_chars)
    if not batches:
        batches = [gen_text]
    return batches, max_chars


def _estimate_duration_frames(ref_audio_len_frames: int, ref_text: str, gen_text: str) -> int:
    ref_text_len = max(1, len(ref_text.encode("utf-8")))
    gen_text_len = max(1, len((gen_text or " ").encode("utf-8")))
    if gen_text_len < 10:
        local_speed = 0.35
    else:
        local_speed = 1.0
    gen_frames = int(ref_audio_len_frames / ref_text_len * gen_text_len / local_speed)
    total = ref_audio_len_frames + int(gen_frames * DURATION_SAFETY)
    total = max(ref_audio_len_frames + 1, total)
    return min(total, MAX_MEL_FRAMES)


def _prepare_audio_tensor(ref_audio_path: str, device: str):
    from habibi_tts.infer.utils_infer import target_rms, target_sample_rate

    audio, sr = torchaudio.load(ref_audio_path)
    if audio.shape[0] > 1:
        audio = torch.mean(audio, dim=0, keepdim=True)
    rms = torch.sqrt(torch.mean(torch.square(audio)))
    if rms < target_rms:
        audio = audio * target_rms / rms
    if sr != target_sample_rate:
        audio = torchaudio.transforms.Resample(sr, target_sample_rate)(audio)
    max_samples = int(REF_AUDIO_MAX_SEC * target_sample_rate)
    if audio.shape[-1] > max_samples:
        audio = audio[..., :max_samples]
    return audio.to(device), int(target_sample_rate)


def _process_one_batch(
    audio_tensor: torch.Tensor,
    ref_text: str,
    gen_text: str,
    runtime: dict,
    *,
    mel_spec_type: str,
    nfe_step: int,
    cfg_strength: float,
    sway_sampling_coef: float,
    target_rms: float,
) -> np.ndarray:
    from habibi_tts.model.utils import text_list_formatter

    ref_text = (ref_text or "").strip()
    if ref_text and len(ref_text[-1].encode("utf-8")) == 1:
        ref_text = ref_text + " "

    text_list = [ref_text + gen_text]
    final_text_list = text_list_formatter(text_list, dialect_id=runtime.get("dialect_id"))

    ref_audio_len = audio_tensor.shape[-1] // HOP_LENGTH
    duration = _estimate_duration_frames(ref_audio_len, ref_text, gen_text)
    if duration >= MAX_MEL_FRAMES - 8:
        logger.warning(
            "Habibi batch near duration cap: duration=%d ref_frames=%d gen_chars=%d",
            duration,
            ref_audio_len,
            len(gen_text.encode("utf-8")),
        )
    rms = torch.sqrt(torch.mean(torch.square(audio_tensor)))

    with torch.inference_mode():
        generated, _ = runtime["model"].sample(
            cond=audio_tensor,
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
        return generated_wave.squeeze().cpu().numpy().astype(np.float32)


def _save_temp_wav(wave: np.ndarray, sr: int) -> str:
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="habibi_ref_")
    os.close(fd)
    sf.write(path, np.asarray(wave, dtype=np.float32), sr)
    return path


def _continuation_ref(wave: np.ndarray, sr: int, gen_chunk: str, fallback_ref: str) -> Tuple[str, str]:
    tail_samples = min(len(wave), int(CONTINUATION_REF_SEC * sr))
    tail = wave[-tail_samples:].astype(np.float32)
    ref_path = _save_temp_wav(tail, sr)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?؟。！])\s+", gen_chunk.strip()) if s.strip()]
    cont_text = normalize_habibi_ref_text(sentences[-1] if sentences else gen_chunk.strip() or fallback_ref)
    return ref_path, cont_text


def _crossfade_concat(waves: List[np.ndarray], sample_rate: int, crossfade_sec: float = 0.12) -> np.ndarray:
    if not waves:
        return np.array([], dtype=np.float32)
    if len(waves) == 1:
        return waves[0]
    final = waves[0]
    fade_samples = int(crossfade_sec * sample_rate)
    for nxt in waves[1:]:
        fade_samples = min(fade_samples, len(final), len(nxt))
        if fade_samples <= 0:
            final = np.concatenate([final, nxt])
            continue
        fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
        fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
        overlap = final[-fade_samples:] * fade_out + nxt[:fade_samples] * fade_in
        final = np.concatenate([final[:-fade_samples], overlap, nxt[fade_samples:]])
    return final.astype(np.float32)


def run_habibi_inference(ref_audio_ready: str, ref_text_ready: str, gen_text: str, runtime: dict):
    import os
    from habibi_tts.infer.utils_infer import (
        cfg_strength,
        mel_spec_type,
        nfe_step as _nfe_step_default,
        sway_sampling_coef,
        target_rms,
        target_sample_rate,
    )
    # On CPU use fewer diffusion steps for acceptable speed (quality slightly lower).
    # Override via HABIBI_NFE_STEP env var; default 16 on CPU, 32 on GPU.
    _on_cpu = runtime.get("device", "cpu") == "cpu"
    _nfe_env = os.environ.get("HABIBI_NFE_STEP", "")
    if _nfe_env.isdigit():
        nfe_step = int(_nfe_env)
    elif _on_cpu:
        nfe_step = 16
    else:
        nfe_step = _nfe_step_default

    ref_text_ready = normalize_habibi_ref_text(ref_text_ready)
    gen_text = normalize_habibi_gen_text(gen_text, ref_text_ready)
    append_trailing_silence_wav(ref_audio_ready, TAIL_SILENCE_SEC)

    batches, max_chars = _habibi_chunk_gen_text(gen_text, ref_audio_ready, ref_text_ready)
    logger.info(
        "Habibi inference: batches=%d max_chars=%d ref_text=%r",
        len(batches),
        max_chars,
        ref_text_ready[:80],
    )

    device = runtime["device"]
    waves: List[np.ndarray] = []
    current_ref_path = ref_audio_ready
    current_ref_text = ref_text_ready
    temp_paths: List[str] = []

    try:
        import time as _time
        for idx, batch in enumerate(batches):
            _t0 = _time.monotonic()
            batch_text = normalize_habibi_gen_text(batch, current_ref_text)
            audio_t, _ = _prepare_audio_tensor(current_ref_path, device)
            wave = _process_one_batch(
                audio_t,
                current_ref_text,
                batch_text,
                runtime,
                mel_spec_type=mel_spec_type,
                nfe_step=nfe_step,
                cfg_strength=cfg_strength,
                sway_sampling_coef=sway_sampling_coef,
                target_rms=target_rms,
            )
            _elapsed = _time.monotonic() - _t0
            logger.info(
                "Habibi batch %d/%d done in %.1fs (device=%s, nfe_step=%d, chars=%d)",
                idx + 1, len(batches), _elapsed, device, nfe_step, len(batch_text.encode()),
            )
            waves.append(wave)
            if idx < len(batches) - 1:
                next_ref_path, next_ref_text = _continuation_ref(wave, target_sample_rate, batch_text, current_ref_text)
                temp_paths.append(next_ref_path)
                append_trailing_silence_wav(next_ref_path, TAIL_SILENCE_SEC)
                current_ref_path = next_ref_path
                current_ref_text = next_ref_text

        final_wave = _crossfade_concat(waves, target_sample_rate)
        return final_wave, int(target_sample_rate)
    finally:
        for path in temp_paths:
            try:
                pathlib.Path(path).unlink(missing_ok=True)
            except OSError:
                pass
