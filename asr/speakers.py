# asr/speakers.py — SpeechBrain تسجيل المتكلمين وربط البصمات
import os
import shutil
import pathlib
from typing import List, Dict
from collections import defaultdict

import numpy as np

try:
    from speechbrain.inference import SpeakerRecognition
    _SB_AVAILABLE = True
except Exception:
    _SB_AVAILABLE = False
    SpeakerRecognition = None

from huggingface_hub import snapshot_download

from config import settings
from asr.common import speaker_label, to_ar_speaker
from asr.audio import wav_read_mono

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
            snapshot_download(
                repo_id="speechbrain/spkrec-ecapa-voxceleb",
                local_dir=local_dir,
                local_dir_use_symlinks=False,
                cache_dir=str(settings.HF_DIR),
                token=_HF_TOKEN,
            )
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


def load_enrolled() -> List[str]:
    global _ENROLLED
    try:
        _ENROLLED.clear()
        for p in SPK_DIR.iterdir():
            if p.is_dir():
                emb_path = p / "embedding.npy"
                if emb_path.exists():
                    _ENROLLED[p.name] = np.load(emb_path)
        return list(_ENROLLED.keys())
    except Exception as e:
        print(f"[ENROLL_LOAD] {e}")
        return []


def get_speaker_files(name: str) -> List[str]:
    try:
        name = (name or "").strip()
        if not name:
            return []
        p = SPK_DIR / name
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


def delete_speaker(name: str):
    global _ENROLLED
    try:
        name = (name or "").strip()
        if not name:
            return False, "اسم فارغ."
        p = SPK_DIR / name
        if not p.exists():
            return False, "غير موجود."
        shutil.rmtree(p, ignore_errors=True)
        _ENROLLED.pop(name, None)
        return True, "تم الحذف."
    except Exception as e:
        return False, f"فشل الحذف: {e}"


def enroll_voice(name: str, files: List[str]):
    global _ENROLLED
    try:
        name = (name or "").strip()
        if not name or not files:
            return False, "أدخل اسمًا وملفات صوتية."
        user_dir = SPK_DIR / name
        if user_dir.exists():
            shutil.rmtree(user_dir)
        user_dir.mkdir(parents=True, exist_ok=True)
        embs = []
        for fpath in files:
            try:
                if not os.path.exists(fpath):
                    continue
                dst = user_dir / pathlib.Path(fpath).name
                shutil.copyfile(fpath, dst)
                wav, sr = wav_read_mono(dst)
                emb = _embed_audio_chunk(wav)
                if emb is not None and np.any(emb):
                    embs.append(emb)
            except Exception as e:
                print(f"[ENROLL_FILE] {e}")
        if not embs:
            return False, "لم يتم العثور على ملفات صوتية صالحة."
        mean_emb = np.mean(np.stack(embs, axis=0), axis=0)
        np.save(user_dir / "embedding.npy", mean_emb)
        _ENROLLED[name] = mean_emb
        return True, f"تم تسجيل {name} ({len(embs)} ملف)."
    except Exception as e:
        return False, f"خطأ في التسجيل: {e}"


def map_generic_to_enrolled_speakers(wav_path: str, seg_rows: List[Dict], threshold: float) -> List[Dict]:
    if not seg_rows or not _ENROLLED:
        load_enrolled()
    if get_spkrec() is None or not _ENROLLED:
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
        for generic_speaker, chunks in speaker_audio_chunks.items():
            if not chunks:
                continue
            full_chunk = np.concatenate(chunks)
            if len(full_chunk) < sr * 1.0:
                continue
            embedding = _embed_audio_chunk(full_chunk)
            best_sim, best_name = -1.0, None
            for enrolled_name, enrolled_emb in _ENROLLED.items():
                if enrolled_name in used_enrolled_names:
                    continue
                sim = _cosine(embedding, enrolled_emb)
                if sim > best_sim:
                    best_sim, best_name = sim, enrolled_name
            if best_name and best_sim >= threshold:
                speaker_mapping[generic_speaker] = best_name
                used_enrolled_names.add(best_name)
        final_seg_rows = []
        unmapped_counter = 1
        unmapped_map = {}
        for seg in seg_rows:
            g = seg["speaker"]
            if g in speaker_mapping:
                seg["speaker"] = speaker_mapping[g]
            else:
                if g not in unmapped_map:
                    unmapped_map[g] = speaker_label(unmapped_counter)
                    unmapped_counter += 1
                seg["speaker"] = unmapped_map[g]
            final_seg_rows.append(seg)
        return final_seg_rows
    except Exception as e:
        print(f"[MAP_ENROLLED] Failed to map speakers: {e}")
        return seg_rows
