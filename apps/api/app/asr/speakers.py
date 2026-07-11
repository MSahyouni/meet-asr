# asr/speakers.py — SpeechBrain تسجيل المتكلمين وربط البصمات
import logging
import os
import shutil
import pathlib
from typing import List, Dict, Optional
from collections import defaultdict

import numpy as np

_log = logging.getLogger("asr.speakers")

try:
    from speechbrain.inference import SpeakerRecognition
    _SB_AVAILABLE = True
except Exception:
    _SB_AVAILABLE = False
    SpeakerRecognition = None

from huggingface_hub import snapshot_download

from app.config import settings
from app.infrastructure.download_retry import run_with_download_retry
from app.storage.user_paths import speaker_enrollment_dir, user_speakers_root
from .common import speaker_label, to_ar_speaker, safe_filename
from .audio import wav_read_mono, to_wav16k

MODELS_DIR = None
SPK_DIR = None
_HF_TOKEN = None
_SPKRECOG = None
_ENROLLED: Dict[str, np.ndarray] = {}


def init_speakers(models_dir, spk_dir, hf_token):
    global MODELS_DIR, SPK_DIR, _HF_TOKEN
    MODELS_DIR = models_dir
    SPK_DIR = spk_dir
    _HF_TOKEN = hf_token


def get_spkrec():
    global _SPKRECOG
    if _SPKRECOG is not None:
        return _SPKRECOG
    if not _SB_AVAILABLE:
        return None
    try:
        import torch
        local_dir_path = (MODELS_DIR / "spkrec_ecapa_cpu")
        local_dir = local_dir_path.as_posix()
        if not local_dir_path.exists():
            print("[SB] Downloading ECAPA model...")
            def _download_once():
                return snapshot_download(
                    repo_id="speechbrain/spkrec-ecapa-voxceleb",
                    local_dir=local_dir,
                    local_dir_use_symlinks=False,
                    cache_dir=str(settings.HF_DIR),
                    token=_HF_TOKEN,
                )

            run_with_download_retry(_download_once, "asr:spkrec-ecapa")
        _SPKRECOG = SpeakerRecognition.from_hparams(
            source=local_dir, savedir=local_dir, run_opts={"device": "cpu"}
        )
    except Exception as e:
        print(f"[SB] فشل تحميل ECAPA: {e}")
        _SPKRECOG = None
    return _SPKRECOG


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    try:
        an = a / (np.linalg.norm(a) + 1e-9)
        bn = b / (np.linalg.norm(b) + 1e-9)
        return float(np.dot(an, bn))
    except Exception:
        return 0.0


def _to1d(emb) -> np.ndarray:
    try:
        import torch
        if isinstance(emb, torch.Tensor):
            emb = emb.detach().cpu().numpy()
        arr = np.asarray(emb)
        if arr.ndim == 1:
            return arr
        if arr.shape[-1] == 192:
            return arr.reshape(-1, 192).mean(axis=0)
        return arr.reshape(-1)[:192]
    except Exception:
        return np.zeros(192, dtype=np.float32)


def _embed_audio_chunk(chunk: np.ndarray) -> np.ndarray:
    try:
        rec = get_spkrec()
        if rec is None:
            return np.zeros(192, dtype=np.float32)
        import torch
        t = torch.from_numpy(chunk).float().unsqueeze(0)
        with torch.no_grad():
            emb = _to1d(rec.encode_batch(t))
        return emb
    except Exception as e:
        print(f"[EMB_CHUNK] {e}")
        return np.zeros(192, dtype=np.float32)


_AUDIO_SAMPLE_EXT = {
    ".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac", ".webm", ".aac", ".3gp", ".opus",
}


def _is_audio_sample_file(path: pathlib.Path) -> bool:
    return path.is_file() and path.suffix.lower() in _AUDIO_SAMPLE_EXT


def _list_audio_samples(speaker_dir: pathlib.Path) -> List[pathlib.Path]:
    if not speaker_dir.exists():
        return []
    return sorted(p for p in speaker_dir.iterdir() if _is_audio_sample_file(p))


def _unique_sample_path(speaker_dir: pathlib.Path, src_name: str) -> pathlib.Path:
    import uuid
    from datetime import datetime

    raw = pathlib.Path(src_name or "sample.wav")
    stem = safe_filename(raw.stem) or "sample"
    ext = raw.suffix.lower() if raw.suffix else ".wav"
    if ext not in _AUDIO_SAMPLE_EXT:
        ext = ".wav"
    speaker_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    return speaker_dir / f"{stem}_{ts}_{short_id}{ext}"


def _embedding_from_audio_path(audio_path: pathlib.Path) -> Optional[np.ndarray]:
    try:
        wav16 = to_wav16k(audio_path)
        try:
            y, sr = wav_read_mono(wav16, 16000)
        finally:
            try:
                os.unlink(wav16)
            except OSError:
                pass
        emb = _embed_audio_chunk(y)
        if emb is not None and np.any(emb):
            return emb
    except Exception as e:
        print(f"[ENROLL_FILE] {e}")
    return None


def _rebuild_speaker_embedding(speaker_dir: pathlib.Path) -> tuple[int, Optional[np.ndarray]]:
    embs = []
    for sample in _list_audio_samples(speaker_dir):
        emb = _embedding_from_audio_path(sample)
        if emb is not None:
            embs.append(emb)
    if not embs:
        return 0, None
    mean_emb = np.mean(np.stack(embs, axis=0), axis=0)
    np.save(speaker_dir / "embedding.npy", mean_emb)
    return len(embs), mean_emb


def load_enrolled(user_email: Optional[str] = None) -> List[str]:
    global _ENROLLED
    try:
        _ENROLLED.clear()
        if not (user_email or "").strip():
            return []
        root = user_speakers_root(user_email)
        for p in root.iterdir():
            if p.is_dir() and (p / "embedding.npy").exists():
                _ENROLLED[p.name] = np.load(p / "embedding.npy")
        return list(_ENROLLED.keys())
    except Exception as e:
        print(f"[ENROLL_LOAD] {e}")
        return []


def get_speaker_files(name: str, user_email: Optional[str] = None) -> List[str]:
    try:
        name = (name or "").strip()
        if not name or not (user_email or "").strip():
            return []
        p = speaker_enrollment_dir(user_email, name)
        if not p.exists() or not p.is_dir():
            return []
        return [
            fp.as_posix()
            for fp in sorted(p.iterdir())
            if fp.is_file() and fp.name != "embedding.npy"
        ]
    except Exception as e:
        print(f"[ENROLL_LIST] {e}")
        return []


def delete_speaker(name: str, user_email: Optional[str] = None):
    global _ENROLLED
    try:
        name = (name or "").strip()
        if not name:
            return False, "اسم فارغ."
        if not (user_email or "").strip():
            return False, "يلزم تسجيل الدخول."
        p = speaker_enrollment_dir(user_email, name)
        if not p.exists():
            return False, "غير موجود."
        shutil.rmtree(p, ignore_errors=True)
        _ENROLLED.pop(name, None)
        return True, "تم الحذف."
    except Exception as e:
        return False, f"فشل الحذف: {e}"


def enroll_voice(name: str, files: List[str], user_email: Optional[str] = None):
    global _ENROLLED
    try:
        name = (name or "").strip()
        if not name or not files:
            return False, "أدخل اسمًا وملفات صوتية."
        if not (user_email or "").strip():
            return False, "يلزم تسجيل الدخول لحفظ بصمة المتكلم."
        user_dir = speaker_enrollment_dir(user_email, name)
        user_dir.mkdir(parents=True, exist_ok=True)
        added = 0
        for fpath in files:
            if not os.path.exists(fpath):
                continue
            dst = _unique_sample_path(user_dir, pathlib.Path(fpath).name)
            shutil.copyfile(fpath, dst)
            added += 1
        if added == 0:
            return False, "لم يتم العثور على ملفات صوتية صالحة."
        total, mean_emb = _rebuild_speaker_embedding(user_dir)
        if mean_emb is None:
            return False, "فشل استخراج بصمة من الملفات الصوتية."
        _ENROLLED[name] = mean_emb
        return True, f"تم حفظ {added} مقطع جديد لـ {name} (المجموع {total} مقطع)."
    except Exception as e:
        return False, f"خطأ في التسجيل: {e}"


def map_generic_to_enrolled_speakers(
    wav_path: str,
    seg_rows: List[Dict],
    threshold: float,
    user_email: Optional[str] = None,
) -> List[Dict]:
    load_enrolled(user_email)
    if not seg_rows:
        return seg_rows
    if get_spkrec() is None:
        _log.warning("speaker mapping skipped: ECAPA model unavailable")
        return seg_rows
    if not _ENROLLED:
        _log.info("speaker mapping skipped: no enrolled speakers")
        return seg_rows
    try:
        y, sr = wav_read_mono(wav_path, 16000)
        speaker_audio_chunks = defaultdict(list)
        for seg in seg_rows:
            start_sample = int(seg["start"] * sr)
            end_sample = int(seg["end"] * sr)
            speaker_audio_chunks[seg["speaker"]].append(y[start_sample:end_sample])
        speaker_mapping = {}
        used_enrolled_names = set()
        single_speaker_audio = len(speaker_audio_chunks) == 1
        single_enrolled = len(_ENROLLED) == 1
        for generic_speaker, chunks in speaker_audio_chunks.items():
            if not chunks:
                continue
            full_chunk = np.concatenate(chunks)
            if len(full_chunk) < sr * 0.8:
                _log.info("skip speaker %s: audio too short (%.2fs)", generic_speaker, len(full_chunk) / sr)
                continue
            embedding = _embed_audio_chunk(full_chunk)
            if embedding is None or not np.any(embedding):
                _log.warning("skip speaker %s: empty embedding", generic_speaker)
                continue
            best_sim, best_name = -1.0, None
            for enrolled_name, enrolled_emb in _ENROLLED.items():
                if enrolled_name in used_enrolled_names:
                    continue
                sim = _cosine(embedding, enrolled_emb)
                if sim > best_sim:
                    best_sim, best_name = sim, enrolled_name
            effective_threshold = threshold
            if single_speaker_audio and single_enrolled:
                effective_threshold = min(threshold, 0.52)
            if best_name and best_sim >= effective_threshold:
                speaker_mapping[generic_speaker] = best_name
                used_enrolled_names.add(best_name)
                _log.info(
                    "mapped %s -> %s (similarity=%.3f, threshold=%.2f)",
                    generic_speaker,
                    best_name,
                    best_sim,
                    effective_threshold,
                )
            else:
                _log.info(
                    "no match for %s (best=%s, similarity=%.3f, threshold=%.2f)",
                    generic_speaker,
                    best_name or "-",
                    best_sim,
                    effective_threshold,
                )
        for seg in seg_rows:
            g = seg["speaker"]
            if g in speaker_mapping:
                seg["speaker"] = speaker_mapping[g]
        return seg_rows
    except Exception as e:
        _log.exception("failed to map enrolled speakers: %s", e)
        return seg_rows
