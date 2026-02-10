# asr/audio.py — قراءة/كتابة صوت، تحويل إلى WAV 16k، تحسين
import os
import pathlib
import subprocess
import numpy as np
import soundfile as sf
import resampy
import librosa
import noisereduce as nr

try:
    from scipy.signal import butter, sosfilt
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

from config import settings
from asr.common import tmp_wav


def _is_container(p: str) -> bool:
    return pathlib.Path(p).suffix.lower() in {".mp4", ".m4a", ".mov", ".3gp", ".mkv", ".webm", ".avi"}


def _ffmpeg_extract(src: str, dst_wav: str, target_sr=16000):
    try:
        cmd = [
            "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
            "-i", src, "-ac", "1", "-ar", str(target_sr), "-vn", "-acodec", "pcm_s16le", dst_wav
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed: {(e.stderr or b'').decode(errors='ignore')[:300]}") from e


def wav_read_mono(path, target_sr=16000):
    y, sr = sf.read(path, dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != target_sr:
        y = resampy.resample(y, sr, target_sr)
        sr = target_sr
    return y.astype(np.float32, copy=False), sr


def to_wav16k(path, target_sr=16000):
    if not os.path.exists(str(path)):
        raise ValueError(f"File not found: {path}")
    tmp = tmp_wav()
    if _is_container(path):
        _ffmpeg_extract(path, tmp, target_sr)
    else:
        y, _ = wav_read_mono(path, target_sr)
        sf.write(tmp, (np.clip(y, -1.0, 1.0) * 32767).astype(np.int16), target_sr)
    return tmp


def enhance_audio_light(y: np.ndarray, sr: int, highpass_hz: float = 60.0, gain_db: float = 4.0) -> np.ndarray:
    """تحسين خفيف: تطبيع + highpass فقط (بدون تقليل ضجيج)."""
    try:
        if highpass_hz > 0 and _SCIPY_AVAILABLE:
            try:
                from scipy.signal import butter, sosfilt
                sos = butter(4, highpass_hz, btype="high", fs=sr, output="sos")
                y = sosfilt(sos, y)
            except Exception:
                pass
        rms = float(np.sqrt(np.mean(y**2) + 1e-9))
        if rms > 0:
            y = y * (0.08 / rms)
        y = np.clip(y * (10 ** (gain_db / 20.0)), -1.0, 1.0)
        return y.astype(np.float32, copy=False)
    except Exception:
        return y.astype(np.float32, copy=False)


def enhance_audio(y: np.ndarray, sr: int, enhance_level: str = "medium", gain_db: float = 6.0) -> np.ndarray:
    levels = {
        "light": {"noise_reduction": 0.5, "preemphasis": 0.75, "highpass": 40, "lowpass": 7000, "compression": 0.3},
        "medium": {"noise_reduction": 0.7, "preemphasis": 0.85, "highpass": 60, "lowpass": 7500, "compression": 0.5},
        "strong": {"noise_reduction": 0.85, "preemphasis": 0.90, "highpass": 80, "lowpass": 8000, "compression": 0.7},
        "aggressive": {"noise_reduction": 0.95, "preemphasis": 0.95, "highpass": 100, "lowpass": 8000, "compression": 0.9}
    }
    config = levels.get(enhance_level.lower(), levels["medium"])
    try:
        y = librosa.effects.preemphasis(y, coef=config["preemphasis"])
        if config["highpass"] > 0 and _SCIPY_AVAILABLE:
            try:
                sos = butter(4, config["highpass"], btype='high', fs=sr, output='sos')
                y = sosfilt(sos, y)
            except Exception:
                pass
        try:
            y = nr.reduce_noise(
                y=y, sr=sr, prop_decrease=config["noise_reduction"],
                stationary=False,
                n_std_thresh_stationary=1.5 if enhance_level in ["strong", "aggressive"] else 1.0
            )
        except Exception:
            pass
        if config["lowpass"] > 0 and config["lowpass"] < sr / 2 and _SCIPY_AVAILABLE:
            try:
                sos = butter(4, config["lowpass"], btype='low', fs=sr, output='sos')
                y = sosfilt(sos, y)
            except Exception:
                pass
        if config["compression"] > 0:
            try:
                rms = float(np.sqrt(np.mean(y**2) + 1e-9))
                if rms > 0:
                    threshold = 0.1
                    ratio = 1.0 + config["compression"] * (rms / threshold - 1.0) if rms > threshold else 1.0
                    y = y * min(ratio, 2.0)
            except Exception:
                pass
        rms = float(np.sqrt(np.mean(y**2) + 1e-9))
        if rms > 0:
            target_rms = 0.10 if enhance_level in ["strong", "aggressive"] else 0.08
            y *= (target_rms / rms)
        y = np.clip(y * (10 ** (gain_db / 20.0)), -1.0, 1.0)
        if enhance_level in ["strong", "aggressive"] and _SCIPY_AVAILABLE:
            try:
                sos_de = butter(2, [3500, 8500], btype='band', fs=sr, output='sos')
                y_hf = sosfilt(sos_de, y)
                y = y - 0.15 * y_hf
            except Exception:
                pass
        y = np.clip(y, -1.0, 1.0)
        return y.astype(np.float32, copy=False)
    except Exception:
        return y.astype(np.float32, copy=False)


def to_wav16k_enhanced(
    path,
    enhance=False,
    enhance_mode: str = "full",
    whisper_mode="normal",
    enhance_level="medium",
    target_sr=16000,
):
    """
    decode/resample ثم (اختياري) تحسين.
    enhance_mode: "off" | "light" (normalize + highpass) | "full" (noise reduce + filters).
    """
    wav = to_wav16k(path, target_sr)
    if not enhance or enhance_mode == "off":
        return wav
    y, sr = wav_read_mono(wav, target_sr)
    if enhance_mode == "light":
        y = enhance_audio_light(y, sr, highpass_hz=60.0, gain_db=4.0)
    else:
        if enhance_level == "medium" and whisper_mode == "whisper":
            enhance_level = "strong"
        gain_levels = {"light": 4.0, "medium": 5.0, "strong": 7.0, "aggressive": 8.0}
        gain_db = gain_levels.get(enhance_level, 5.0)
        y = enhance_audio(y, sr, enhance_level=enhance_level, gain_db=gain_db)
    tmp = tmp_wav()
    sf.write(tmp, (y * 32767).astype(np.int16), sr)
    return tmp
