import logging
import pathlib
from typing import Optional

import numpy as np

from app.config import settings
from app.tts.audio_speed import apply_speed_numpy, trim_ref_text_for_duration
from app.tts.habibi_infer import run_habibi_inference

logger = logging.getLogger("tts_habibi")

_HABIBI_RUNTIME = {}

HABIBI_UNIFIED_DIALECTS = {
    "UNK",
    "MSA",
    "SAU",
    "UAE",
    "ALG",
    "IRQ",
    "EGY",
    "MAR",
    "OMN",
    "TUN",
    "LEV",
    "SDN",
    "LBY",
}

HABIBI_SPECIALIZED_DIALECTS = {"MSA", "SAU", "UAE", "ALG", "IRQ", "EGY", "MAR"}


def _normalize_model_choice(model_choice: str) -> str:
    value = (model_choice or "unified").strip().lower()
    if value in {"habibi_unified", "unified"}:
        return "unified"
    if value in {"habibi_specialized", "specialized"}:
        return "specialized"
    raise ValueError("Habibi model must be one of: unified, specialized")


def _normalize_dialect(dialect: Optional[str], model_choice: str) -> str:
    value = (dialect or "UNK").strip().upper() or "UNK"
    if model_choice == "unified":
        if value not in HABIBI_UNIFIED_DIALECTS:
            raise ValueError(f"Habibi unified dialect must be one of: {', '.join(sorted(HABIBI_UNIFIED_DIALECTS))}")
        return value
    if value not in HABIBI_SPECIALIZED_DIALECTS:
        raise ValueError(f"Habibi specialized dialect must be one of: {', '.join(sorted(HABIBI_SPECIALIZED_DIALECTS))}")
    return value


def _resolve_ckpt_and_vocab(model_choice: str, dialect: str):
    from cached_path import cached_path

    if model_choice == "unified":
        ckpt_file = str(cached_path("hf://SWivid/Habibi-TTS/Unified/model_200000.safetensors"))
        vocab_file = str(cached_path("hf://SWivid/Habibi-TTS/Unified/vocab.txt"))
        return ckpt_file, vocab_file

    if dialect in {"MSA", "SAU"}:
        ckpt_step = 200000
    else:
        ckpt_step = 100000
    ckpt_file = str(cached_path(f"hf://SWivid/Habibi-TTS/Specialized/{dialect}/model_{ckpt_step}.safetensors"))
    vocab_file = str(cached_path(f"hf://SWivid/Habibi-TTS/Specialized/{dialect}/vocab.txt"))
    return ckpt_file, vocab_file


def _get_runtime(model_choice: str, dialect: str):
    model_key = f"{model_choice}:{dialect}"
    if model_key in _HABIBI_RUNTIME:
        return _HABIBI_RUNTIME[model_key]

    try:
        from importlib.resources import files

        from f5_tts.infer.utils_infer import load_model, load_vocoder
        from hydra.utils import get_class
        from omegaconf import OmegaConf

        from habibi_tts.infer.utils_infer import device as habibi_device
        from habibi_tts.model.utils import dialect_id_map
    except ImportError as e:
        raise RuntimeError(
            "Habibi backend requires optional dependencies. Install in a dedicated env: "
            "pip install habibi-tts"
        ) from e

    model_cfg = OmegaConf.load(str(files("f5_tts").joinpath("configs/F5TTS_v1_Base.yaml")))
    model_cls = get_class(f"f5_tts.model.{model_cfg.model.backbone}")
    model_arc = model_cfg.model.arch
    vocoder_name = model_cfg.model.mel_spec.mel_spec_type

    ckpt_file, vocab_file = _resolve_ckpt_and_vocab(model_choice=model_choice, dialect=dialect)
    logger.info("Loading Habibi model (%s, %s)", model_choice, dialect)
    model = load_model(
        model_cls,
        model_arc,
        ckpt_file,
        mel_spec_type=vocoder_name,
        vocab_file=vocab_file,
        device=habibi_device,
    )
    vocoder = load_vocoder(
        vocoder_name=vocoder_name,
        is_local=False,
        local_path="",
        device=habibi_device,
    )
    dialect_id = dialect_id_map.get(dialect) if model_choice == "unified" else None

    runtime = {
        "model": model,
        "vocoder": vocoder,
        "device": habibi_device,
        "dialect_id": dialect_id,
    }
    _HABIBI_RUNTIME[model_key] = runtime
    logger.info("Habibi model loaded (%s)", model_key)
    return runtime


def synthesize_habibi(
    text: str,
    ref_audio_path: str,
    ref_text: str,
    speed: float = 1.0,
    out_path: str = "",
    model_choice: str = "unified",
    dialect: Optional[str] = "UNK",
) -> dict:
    model_choice = _normalize_model_choice(model_choice)
    dialect = _normalize_dialect(dialect, model_choice=model_choice)

    ref_audio = pathlib.Path(ref_audio_path).resolve()
    if not ref_audio.exists() or not ref_audio.is_file():
        raise ValueError(f"Habibi reference audio not found: {ref_audio}")
    if not (ref_text or "").strip():
        raise ValueError("Habibi requires ref_text (transcript of reference audio)")

    out_dir = pathlib.Path(settings.OUTPUTS_DIR) / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not out_path or not pathlib.Path(out_path).suffix:
        import time

        base = f"habibi_{int(time.time() * 1000)}"
        out_path = str(out_dir / f"{base}.wav")
    else:
        p = pathlib.Path(out_path)
        if not p.is_absolute():
            p = out_dir / p.name
        p.parent.mkdir(parents=True, exist_ok=True)
        out_path = str(p.resolve())

    runtime = _get_runtime(model_choice=model_choice, dialect=dialect)

    from f5_tts.infer.utils_infer import preprocess_ref_audio_text
    import soundfile as sf

    ref_audio_ready, ref_text_ready = preprocess_ref_audio_text(str(ref_audio), ref_text.strip())
    try:
        ref_duration_sec = float(sf.info(ref_audio_ready).duration)
    except Exception:
        ref_duration_sec = 0.0
    ref_text_ready = trim_ref_text_for_duration(ref_text_ready, ref_duration_sec)

    final_wave, final_sample_rate = run_habibi_inference(
        ref_audio_ready,
        ref_text_ready,
        text.strip(),
        runtime,
    )

    if final_wave is None:
        raise RuntimeError("Habibi synthesis produced no audio")
    final_wave = apply_speed_numpy(np.asarray(final_wave, dtype=np.float32), speed)

    sf.write(out_path, final_wave, final_sample_rate)
    duration_sec = len(final_wave) / float(final_sample_rate)
    return {
        "audio_path": out_path,
        "sample_rate": int(final_sample_rate),
        "duration_sec": round(duration_sec, 3),
        "voice": f"habibi_{model_choice}",
        "dialect": dialect,
    }
