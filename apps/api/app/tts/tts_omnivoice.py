import logging
import os
import pathlib
import subprocess
import threading
from typing import Optional, Tuple

from app.config import settings
from app.infrastructure.omnivoice_download import (
    cleanup_omnivoice_stale_incomplete,
    omnivoice_cache_dirs,
    omnivoice_snapshot_model,
)

logger = logging.getLogger("tts_omnivoice")

_OMNIVOICE_MODEL_ID = "k2-fsa/OmniVoice"
_OMNIVOICE_CACHE_DIRNAME = "models--k2-fsa--OmniVoice"
_OMNIVOICE_EXPECTED_BYTES = 3_200_000_000  # ~3.2 GB total repo weights
_OMNIVOICE_MODEL_MIN_BYTES = 1_000_000_000
_OMNIVOICE_INFER_LOCK = threading.Lock()


def _project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[4]


def _resolve_omnivoice_infer_bin() -> str:
    """
    Return path to `omnivoice-infer` binary.

    OmniVoice runs in a separate venv to avoid dependency conflicts with the API.
    """
    configured = (os.getenv("OMNIVOICE_INFER_BIN", "") or "").strip()
    if configured:
        return configured

    root = _project_root()
    for candidate in (
        root / ".tools" / "omnivoice" / ".venv" / "bin" / "omnivoice-infer",
        root / ".tools" / "omnivoice" / "bin" / "omnivoice-infer",
    ):
        if candidate.exists():
            return str(candidate)
    return "omnivoice-infer"


def _omnivoice_cache_dirs() -> list[pathlib.Path]:
    return [p for p in omnivoice_cache_dirs() if p.exists()]


def _omnivoice_snapshot_model() -> Optional[pathlib.Path]:
    return omnivoice_snapshot_model()


def _omnivoice_download_status() -> Tuple[bool, str]:
    """Return (ready, human-readable status)."""
    model_file = omnivoice_snapshot_model()
    if model_file is not None:
        cleanup_omnivoice_stale_incomplete()
        return True, "جاهز"

    cache_dirs = _omnivoice_cache_dirs()
    if not cache_dirs:
        return False, "لم يبدأ تنزيل نموذج OmniVoice بعد (~3.2 GB)."

    incomplete = []
    total_bytes = 0
    for cache_dir in cache_dirs:
        blobs = cache_dir / "blobs"
        if blobs.is_dir():
            for path in blobs.iterdir():
                if not path.is_file():
                    continue
                try:
                    total_bytes += path.stat().st_size
                except OSError:
                    continue
                if path.name.endswith(".incomplete"):
                    incomplete.append(path)

    if incomplete:
        mb_done = total_bytes / (1024 * 1024)
        mb_expected = _OMNIVOICE_EXPECTED_BYTES / (1024 * 1024)
        return (
            False,
            f"تنزيل OmniVoice قيد التقدم: ~{mb_done:.0f}MB / ~{mb_expected:.0f}MB "
            f"({len(incomplete)} ملف غير مكتمل). انتظر اكتمال التنزيل ثم أعد المحاولة.",
        )

    if total_bytes < _OMNIVOICE_MODEL_MIN_BYTES:
        mb_done = total_bytes / (1024 * 1024)
        return False, f"تنزيل OmniVoice غير مكتمل (~{mb_done:.0f}MB محفوظ)."

    return True, "جاهز"


def omnivoice_readiness() -> Tuple[bool, str, str]:
    """
    Return (ready, status_message, infer_bin_path).
    ready requires both model weights and a resolvable omnivoice-infer binary.
    """
    infer_bin = _resolve_omnivoice_infer_bin()
    model_ready, model_status = _omnivoice_download_status()
    if not model_ready:
        return False, model_status, infer_bin

    bin_path = pathlib.Path(infer_bin)
    if infer_bin == "omnivoice-infer":
        # PATH lookup — treat as present; synthesize will FileNotFoundError if missing.
        import shutil

        resolved = shutil.which("omnivoice-infer")
        if not resolved:
            return (
                False,
                "OmniVoice غير مُثبّت. أنشئ .tools/omnivoice/.venv أو اضبط OMNIVOICE_INFER_BIN.",
                infer_bin,
            )
        return True, "جاهز", resolved

    if not bin_path.exists():
        return (
            False,
            f"ملف omnivoice-infer غير موجود: {infer_bin}",
            infer_bin,
        )
    return True, "جاهز", str(bin_path)


def _omnivoice_subprocess_env() -> dict:
    env = os.environ.copy()
    env["HF_HOME"] = str(settings.HF_DIR)
    env.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    return env


def _omnivoice_timeout_sec() -> Optional[float]:
    value = int(getattr(settings, "OMNIVOICE_TIMEOUT_SEC", 7200) or 0)
    if value <= 0:
        return None
    return float(value)


def synthesize_omnivoice(
    text: str,
    ref_audio_path: str,
    ref_text: Optional[str] = None,
    speed: float = 1.0,
    out_path: str = "",
) -> dict:
    """
    Synthesize text using OmniVoice voice cloning.

    Notes:
    - ref_text is optional. If omitted, OmniVoice will auto-transcribe ref_audio.
    - Output is always WAV at 24 kHz.
    """
    ref_audio = pathlib.Path(ref_audio_path).resolve()
    if not ref_audio.exists() or not ref_audio.is_file():
        raise ValueError(f"OmniVoice reference audio not found: {ref_audio}")
    if not (text or "").strip():
        raise ValueError("OmniVoice requires non-empty text")

    ready, status, _infer = omnivoice_readiness()
    if not ready:
        raise RuntimeError(
            f"OmniVoice غير جاهز: {status} "
            "نفّذ scripts/download_omnivoice.sh ثم أعد المحاولة."
        )

    out_dir = pathlib.Path(settings.OUTPUTS_DIR) / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not out_path or not pathlib.Path(out_path).suffix:
        import time

        base = f"omnivoice_{int(time.time() * 1000)}"
        out_path = str(out_dir / f"{base}.wav")
    else:
        p = pathlib.Path(out_path)
        if not p.is_absolute():
            p = out_dir / p.name
        p.parent.mkdir(parents=True, exist_ok=True)
        out_path = str(p.resolve())

    infer_bin = _resolve_omnivoice_infer_bin()
    cmd = [
        infer_bin,
        "--model",
        _OMNIVOICE_MODEL_ID,
        "--text",
        text.strip(),
        "--ref_audio",
        str(ref_audio),
        "--output",
        out_path,
    ]
    if (ref_text or "").strip():
        cmd.extend(["--ref_text", ref_text.strip()])

    timeout_sec = _omnivoice_timeout_sec()
    logger.info(
        "Running OmniVoice (timeout=%s): %s",
        "none" if timeout_sec is None else f"{int(timeout_sec)}s",
        " ".join(cmd[:6]) + " ...",
    )
    # Serialize CLI runs to avoid GPU/VRAM contention across concurrent requests.
    with _OMNIVOICE_INFER_LOCK:
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=timeout_sec,
                env=_omnivoice_subprocess_env(),
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "OmniVoice غير مُثبّت كأداة. ثبّته في بيئة منفصلة ثم اضبط OMNIVOICE_INFER_BIN "
                "أو أنشئ .tools/omnivoice/.venv. "
                f"Details: {e}"
            ) from e
        except subprocess.TimeoutExpired as e:
            _, status_after = _omnivoice_download_status()
            raise RuntimeError(
                "انتهت مهلة OmniVoice على السيرفر. "
                f"{status_after} "
                "يمكنك زيادة OMNIVOICE_TIMEOUT_SEC (مثلاً 14400) أو تشغيل scripts/download_omnivoice.sh "
                "لإكمال التنزيل خارج الواجهة."
            ) from e

    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        if "name resolution" in msg.lower() or "timed out" in msg.lower():
            _, status_after = _omnivoice_download_status()
            raise RuntimeError(
                "فشل تنزيل/تحميل OmniVoice بسبب الشبكة أو DNS. "
                f"{status_after} "
                "جرّب إصلاح DNS في WSL ثم أعد المحاولة، أو نفّذ scripts/download_omnivoice.sh."
            )
        raise RuntimeError(f"OmniVoice CLI failed (code={proc.returncode}): {msg}")

    sample_rate = 24000
    duration_sec = 0.0
    try:
        if abs(float(speed) - 1.0) > 1e-3:
            import numpy as np
            import soundfile as sf

            from app.tts.audio_speed import apply_speed_numpy

            wave, sr = sf.read(out_path, dtype="float32", always_2d=False)
            if int(sr) != sample_rate:
                sample_rate = int(sr)
            wave = np.asarray(wave, dtype=np.float32)
            wave = apply_speed_numpy(wave, float(speed))
            sf.write(out_path, wave, sample_rate)
            duration_sec = len(wave) / float(sample_rate)
        else:
            import soundfile as sf

            info = sf.info(out_path)
            sample_rate = int(info.samplerate)
            duration_sec = float(info.duration)
    except Exception:
        pass

    return {
        "audio_path": out_path,
        "sample_rate": sample_rate,
        "duration_sec": round(duration_sec, 3),
        "voice": "omnivoice",
    }
