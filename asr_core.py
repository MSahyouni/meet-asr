# asr_core.py — نسخة مرتبة وموحّدة
import os
import re
import time
import atexit
import shutil
import pathlib
import tempfile
import subprocess
import traceback
from typing import Optional, List, Dict
from collections import defaultdict

import numpy as np
import soundfile as sf
import resampy
import librosa
import noisereduce as nr
import torch
from huggingface_hub import snapshot_download
from faster_whisper import WhisperModel

import nlp_core
# اختياري: Pyannote ديازة
try:
    from pyannote.audio import Pipeline
    _PYANNOTE_AVAILABLE = True
except ImportError:
    _PYANNOTE_AVAILABLE = False
    print("[DIAR] pyannote.audio not found. Diarization disabled.")

# اختياري: SpeechBrain للتعرّف على المتكلمين
try:
    from speechbrain.inference import SpeakerRecognition
    _SB_AVAILABLE = True
except Exception:
    _SB_AVAILABLE = False
    print("[SB] speechbrain not found. Speaker recognition disabled.")

# إعدادات خارجية
from config import settings

# ===== بيئة أخف =====
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("CT2_USE_MMAP", "1")
os.environ["SPEECHBRAIN_LOCAL_FILE_STRATEGY"] = "copy"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HOME"] = str(settings.HF_DIR)
os.environ.pop("TRANSFORMERS_CACHE", None)
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(settings.HF_DIR))

# ===== ثوابت ومسارات =====
_HF_TOKEN     = settings.HF_TOKEN
_HAS_CUDA     = torch.cuda.is_available()
DEFAULT_MODEL = settings.WHISPER_MODEL
MODEL_CHOICES = ["light", "heavy"]

if _HAS_CUDA and hasattr(torch, "set_float32_matmul_precision"):
    torch.set_float32_matmul_precision("high")

OUTPUTS_DIR = settings.OUTPUTS_DIR
MODELS_DIR  = settings.MODELS_DIR
SPK_DIR     = settings.SPK_DIR

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
SPK_DIR.mkdir(parents=True, exist_ok=True)

_MODEL_CACHE: Dict = {}
_SPKRECOG = None
_ENROLLED: Dict[str, np.ndarray] = {}
_PYANNOTE_PIPELINE = None

# ===== أدوات مساعدة عامة =====

def _speaker_label(i: int) -> str:
    return f"متكلم_{i:02d}"

def _to_ar_speaker(label: str) -> str:
    """تحويلات قوية للأشكال الشائعة: SPEAKER_00 / SPEAKER 00 / 00."""
    s = str(label or "").strip()
    if not s:
        return _speaker_label(0)
    u = s.upper()
    if u.startswith("SPEAKER"):
        m = re.search(r"(\d+)$", u)
        if m:
            return _speaker_label(int(m.group(1)))
        return _speaker_label(0)
    if re.fullmatch(r"\d+", s):
        return _speaker_label(int(s))
    return s

def _err(msg: str) -> Dict:
    return {
        "text": "", "txt_path": None,
        "summary": "", "summary_path": None,
        "keywords": "", "segments": [],
        "srt_path": None, "vtt_path": None,
        "error": msg,
    }

def _tmp_wav(suffix: str = ".wav") -> str:
    return tempfile.NamedTemporaryFile(prefix="asr_", suffix=suffix, delete=False).name

def _safe_filename(p) -> str:
    try:
        base = pathlib.Path(str(p)).stem or "audio"
        return "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in base) or "audio"
    except Exception:
        return "audio"

def _resolve_model(name: str) -> str:
    n = (name or "").strip().lower()
    return "large-v3" if n in ("heavy", "large-v3") else "medium"

def _safe_compute(device: Optional[str], compute_type: Optional[str]):
    dev = (device or ("cuda" if _HAS_CUDA else "cpu")).lower()
    ctp = (compute_type or ("float16" if dev == "cuda" else "int8_float32")).lower()
    if dev != "cuda" and ctp == "float16":
        ctp = "int8_float32"
    return dev, ctp

# ===== تحميل نموذج Whisper =====
def get_model(name: str, device: Optional[str] = None, compute_type: Optional[str] = None) -> WhisperModel:
    name = _resolve_model(name)
    dev, ctp = _safe_compute(device, compute_type)
    key = (name, dev, ctp)
    if key not in _MODEL_CACHE:
        try:
            local_dir = MODELS_DIR / f"whisper-{name}"
            if not local_dir.exists():
                snapshot_download(
                    repo_id=f"Systran/faster-whisper-{name}",
                    local_dir=str(local_dir),
                    local_dir_use_symlinks=False,
                    cache_dir=str(settings.HF_DIR),
                    token=_HF_TOKEN,
                )
            model_args = {
                "device": dev,
                "compute_type": ctp,
                "cpu_threads": settings.CPU_THREADS,
                "download_root": str(MODELS_DIR),
            }
            if dev == "cuda":
                model_args["device_index"] = settings.GPU_ID
            _MODEL_CACHE[key] = WhisperModel(str(local_dir), **model_args)
            if settings.ASR_LOG_LOAD:
                print(f"[WHISPER] loaded name={name} path={local_dir} device={dev} compute={ctp}")
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model {name}: {e}") from e
    return _MODEL_CACHE[key]

# ===== Pyannote Diarization =====
def _load_pyannote_pipeline():
    global _PYANNOTE_PIPELINE
    if not _PYANNOTE_AVAILABLE:
        return None
    if _PYANNOTE_PIPELINE is not None:
        return _PYANNOTE_PIPELINE
    try:
        print("[PYANNOTE] Loading diarization pipeline...")
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=_HF_TOKEN)
        if _HAS_CUDA:
            pipeline.to(torch.device("cuda"))
        _PYANNOTE_PIPELINE = pipeline
        print("[PYANNOTE] Pipeline loaded.")
        return _PYANNOTE_PIPELINE
    except Exception as e:
        print(f"[PYANNOTE] Failed to load pipeline. Disabled. Error: {e}")
        _PYANNOTE_PIPELINE = None
        return None

def diarize_with_pyannote(wav_path: str, num_speakers: int = 0) -> List[Dict]:
    pipeline = _load_pyannote_pipeline()
    if not pipeline:
        return []
    try:
        params = {}
        if num_speakers > 0:
            params["num_speakers"] = num_speakers
        diarization = pipeline(wav_path, **params)
        return [
            {"start": turn.start, "end": turn.end, "speaker": speaker}
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        ]
    except Exception as e:
        print(f"[PYANNOTE] Diarization failed: {e}")
        return []

def _map_speakers_to_segments(whisper_segments: List[Dict], speaker_turns: List[Dict]) -> List[Dict]:
    """إسناد معرفات المتكلمين من pyannote إلى مقاطع Whisper بالاعتماد على التداخل الزمني."""
    if not speaker_turns:
        for seg in whisper_segments:
            seg["speaker"] = _speaker_label(0)
        return whisper_segments

    for seg in whisper_segments:
        seg_start, seg_end = seg["start"], seg["end"]
        overlap = defaultdict(float)
        for turn in speaker_turns:
            turn_start, turn_end = turn["start"], turn["end"]
            o = max(0.0, min(seg_end, turn_end) - max(seg_start, turn_start))
            if o > 0:
                overlap[turn["speaker"]] += o
        ar_label = max(overlap, key=overlap.get) if overlap else _speaker_label(0)
        seg["speaker"] = _to_ar_speaker(ar_label)
    return whisper_segments

# ===== Speaker Recognition via SpeechBrain =====
def get_spkrec():
    global _SPKRECOG
    if _SPKRECOG is not None:
        return _SPKRECOG
    if not _SB_AVAILABLE:
        return None
    try:
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
    """إنتاج تمثيل متجه للصوت الخام."""
    try:
        rec = get_spkrec()
        if rec is None:
            return np.zeros(192, dtype=np.float32)
        t = torch.from_numpy(chunk).float().unsqueeze(0)
        with torch.no_grad():
            emb = _to1d(rec.encode_batch(t))
        return emb
    except Exception as e:
        print(f"[EMB_CHUNK] {e}")
        return np.zeros(192, dtype=np.float32)

def load_enrolled() -> List[str]:
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
                wav, sr = _wav_read_mono(dst)
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

def _map_generic_to_enrolled_speakers(wav_path: str, seg_rows: List[Dict], threshold: float) -> List[Dict]:
    """استبدال وسوم المتكلمين العامة بأسماء مسجّلة إذا تشابهت المتجهات."""
    if not seg_rows or not _ENROLLED:
        load_enrolled()
    if get_spkrec() is None or not _ENROLLED:
        return seg_rows

    try:
        y, sr = _wav_read_mono(wav_path, 16000)
        # تجميع مقاطع كل متكلم عام
        speaker_audio_chunks = defaultdict(list)
        for seg in seg_rows:
            start_sample = int(seg["start"] * sr)
            end_sample   = int(seg["end"]   * sr)
            speaker_audio_chunks[seg["speaker"]].append(y[start_sample:end_sample])

        speaker_mapping = {}
        used_enrolled_names = set()

        for generic_speaker, chunks in speaker_audio_chunks.items():
            if not chunks:
                continue
            full_chunk = np.concatenate(chunks)
            if len(full_chunk) < sr * 1.0:
                continue  # أقل من ثانية
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

        # تطبيق الاستبدال
        final_seg_rows = []
        unmapped_counter = 1
        unmapped_map = {}
        for seg in seg_rows:
            g = seg["speaker"]
            if g in speaker_mapping:
                seg["speaker"] = speaker_mapping[g]
            else:
                if g not in unmapped_map:
                    unmapped_map[g] = _speaker_label(unmapped_counter)
                    unmapped_counter += 1
                seg["speaker"] = unmapped_map[g]
            final_seg_rows.append(seg)
        return final_seg_rows
    except Exception as e:
        print(f"[MAP_ENROLLED] Failed to map speakers: {e}")
        return seg_rows

# ===== Audio I/O & Enhancement =====
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

def _wav_read_mono(path, target_sr=16000):
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
    tmp = _tmp_wav()
    if _is_container(path):
        _ffmpeg_extract(path, tmp, target_sr)
    else:
        y, _ = _wav_read_mono(path, target_sr)
        sf.write(tmp, (np.clip(y, -1.0, 1.0) * 32767).astype(np.int16), target_sr)
    return tmp

def enhance_audio(y: np.ndarray, sr: int, strong=False, gain_db=6.0) -> np.ndarray:
    try:
        y = librosa.effects.preemphasis(y, coef=0.85)
        y = nr.reduce_noise(y=y, sr=sr, prop_decrease=0.9 if strong else 0.6, stationary=False)
        rms = float(np.sqrt(np.mean(y**2) + 1e-9))
        if rms > 0:
            y *= (0.08 / rms)
        y = np.clip(y * (10 ** (gain_db / 20.0)), -1.0, 1.0)
        return y.astype(np.float32, copy=False)
    except Exception:
        return y

def to_wav16k_enhanced(path, enhance=False, whisper_mode="normal", target_sr=16000):
    wav = to_wav16k(path, target_sr)
    if not enhance:
        return wav
    y, sr = _wav_read_mono(wav, target_sr)
    strong = (whisper_mode == "whisper")
    y = enhance_audio(y, sr, strong=strong, gain_db=8.0 if strong else 5.0)
    tmp = _tmp_wav()
    sf.write(tmp, (y * 32767).astype(np.int16), sr)
    return tmp

# ===== ASR =====
def run_asr(wav_path: str, model_obj: WhisperModel, whisper_mode: str = "normal"):
    # يمكنك تمرير initial_prompt إذا أردت توجيه النمط
    init_prompt = "لغة عربية عامية سورية." if whisper_mode == "whisper" else "لغة عربية فصحى."
    segments_generator, info = model_obj.transcribe(
        wav_path,
        language="ar",
        task="transcribe",
        vad_filter=True,
        vad_parameters={"threshold": 0.7, "min_silence_duration_ms": 800, "speech_pad_ms": 100},
        beam_size=5,
        temperature=[0.0, 0.2, 0.4],
        initial_prompt=init_prompt,
    )
    seglist = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments_generator]
    meta = f"المدة: {info.duration:.1f}s | اللغة: {info.language} | ثقة: {info.language_probability:.2f}"
    return meta, seglist

# ===== تنظيف نص + كلمات مفتاحية =====
def _clean_utterance(t: str) -> str:
    """تنظيف خفيف لعرض النص للمستخدم: يزيل الحشويات والتكرارات فقط."""
    if not t:
        return ""
    _FILLERS = {"يعني","تمام","طيب","هيك","مم","اها","اه","آه","بس"}
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"([.!؟?،,:;])\1+", r"\1", t)        # دمج تكرار الترقيم
    t = t.replace("?", "؟")                          # توحيد علامة السؤال
    # تقليص تكرار الكلمات المتتالية 3+ إلى 2 (اه اه اه -> اه اه)
    t = re.sub(r"\b(\w+)(?:\s+\1){2,}\b", r"\1 \1", t)
    words = [w for w in t.split() if w.lower() not in _FILLERS]
    cleaned = " ".join(words)
    cleaned = re.sub(r"\s*([،,:;.!؟])\s*", r"\1 ", cleaned).strip()
    return cleaned

# ===== ترقيم المتكلمين =====
def _renumber_speakers(text: str) -> str:
    """إعادة ترقيم المتكلمين بترتيب الظهور إلى متكلم_01, متكلم_02..."""
    mapping: Dict[str, int] = {}
    next_id = 1
    def repl(m):
        nonlocal next_id
        old_num = m.group(1)  # يلتقط الرقم سواء بعد مسافة أو شرطة سفلية
        if old_num not in mapping:
            mapping[old_num] = next_id
            next_id += 1
        return f"(متكلم_{mapping[old_num]:02d})"
    # يدعم (متكلم 3) و(متكلم_07)
    return re.sub(r"\(متكلم[_\s]+(\d+)\)", repl, text)

# ===== توليد ترجمات SRT/VTT =====
def _fmt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    s, ms = divmod(ms, 1000)
    m, s  = divmod(s, 60)
    h, m  = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def segments_to_srt(segments: List[Dict], base_path: str, out_path: Optional[str] = None) -> str:
    """
    يكتب SRT لمقاطع معطاة.
    إذا تم تمرير out_path يُستخدم مباشرة، وإلا يُشتق من base_path بامتداد .srt.
    """
    p = pathlib.Path(out_path) if out_path else pathlib.Path(base_path).with_suffix(".srt")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        rlm = "\u200F"  # Right-to-Left Mark لتثبيت الاتجاه في بعض المشغلات
        for i, seg in enumerate(segments, 1):
            spk = _to_ar_speaker(seg.get('speaker',''))
            f.write(f"{i}\n{_fmt_ts(seg['start'])} --> {_fmt_ts(seg['end'])}\n{rlm}{spk}: {seg['text']}\n\n")
    return str(p)

def segments_to_vtt(segments: List[Dict], base_path: str, out_path: Optional[str] = None) -> str:
    """
    يكتب VTT لمقاطع معطاة.
    إذا تم تمرير out_path يُستخدم مباشرة، وإلا يُشتق من base_path بامتداد .vtt.
    """
    p = pathlib.Path(out_path) if out_path else pathlib.Path(base_path).with_suffix(".vtt")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("WEBVTT\n\n")
        rlm = "\u200F"
        for seg in segments:
            st = _fmt_ts(seg["start"]).replace(",", ".")
            en = _fmt_ts(seg["end"]).replace(",", ".")
            spk = _to_ar_speaker(seg.get('speaker',''))
            f.write(f"{st} --> {en}\n{rlm}{spk}: {seg['text']}\n\n")
    return str(p)

# ===== المسار الرئيسي =====
def process(
    file_path: str,
    model_name: Optional[str] = None,
    enhance: bool = False,
    whisper_mode: str = "normal",
    diarize: bool = False,
    auto_k: bool = True,
    max_speakers: int = 2,
    enroll_threshold: float = 0.65,
    device_sel: str = "auto",
    compute_sel: str = "auto",
    punctuate: bool = False,
    summary_mode: str = "best",
):
    if not os.path.exists(file_path):
        return _err(f"File not found: {file_path}")
    try:
        # 1) تحضير الصوت والنموذج
        wav = to_wav16k_enhanced(file_path, enhance=enhance, whisper_mode=whisper_mode)
        model = get_model(model_name or DEFAULT_MODEL, device_sel, compute_sel)

        # 2) ASR
        header_txt, whisper_segments = run_asr(wav, model, whisper_mode=whisper_mode)

        # 3) ديازة اختيارية
        if diarize and _PYANNOTE_AVAILABLE:
            num_spk = max_speakers if not auto_k else 0
            speaker_turns = diarize_with_pyannote(wav, num_speakers=num_spk)
            seg_rows = _map_speakers_to_segments(whisper_segments, speaker_turns)
            seg_rows = _map_generic_to_enrolled_speakers(wav, seg_rows, enroll_threshold)
        else:
            seg_rows = _map_speakers_to_segments(whisper_segments, [])

        # 4) نص نهائي
        # ترقيم اختياري قبل التنظيف الخفيف
        if punctuate:
            try:
                for s in seg_rows:
                    s["text"] = nlp_core.restore_punct(s.get("text",""))
            except Exception as _e:
                print(f"[PUNCT] failed: {_e}")
        # RTL-friendly formatting:
        # متكلم_XX
        # [00.00 → 12.34]
        # النص
        # ────────────────
        RLM = "\u200F"  # Right-to-Left Mark لتثبيت الاتجاه العربي
        LRM = "\u200E"  # Left-to-Right Mark لضبط اتجاه الأرقام داخل العربية

        lines = []
        for s in seg_rows:
            spk = _to_ar_speaker(s.get("speaker",""))
            st  = f"{LRM}{s['start']:.2f}{LRM}"
            en  = f"{LRM}{s['end']:.2f}{LRM}"
            txt = _clean_utterance(s['text'])
            lines.append(
                f"{RLM}{spk}\n"
                f"{RLM}[{st} → {en}]\n"
                f"{RLM}{txt}\n"
                f"••••••••••••••••••••••••••••••••"
            )
        full_txt = header_txt + "\n\n" + "\n".join(lines)

        raw_text_for_keywords = "\n".join([s.get("text", "") for s in seg_rows])
        keywords = nlp_core.extract_keywords(raw_text_for_keywords)

        # 6) حفظ الملفات
        base = _safe_filename(file_path)
        out_path = str(OUTPUTS_DIR / f"{base}_transcript.txt")
        pathlib.Path(out_path).write_text(full_txt, encoding="utf-8")

        # 7) ترجمات
        for s in seg_rows:
            s["speaker"] = _to_ar_speaker(s.get("speaker",""))
        srt_path = segments_to_srt(seg_rows, out_path)
        vtt_path = segments_to_vtt(seg_rows, out_path)

        # ترقيم المتكلمين النهائي
        numbered_text = _renumber_speakers(full_txt)

        return {
            "text": numbered_text,
            "txt_path": out_path,
            "summary": "",
            "summary_path": None,
            "keywords": keywords,
            "segments": seg_rows,
            "srt_path": srt_path,
            "vtt_path": vtt_path,
        }

    except Exception as e:
        msg = f"Error during processing: {e}"
        print(f"[PROCESS] {msg}\n{traceback.format_exc()}")
        return _err(msg)

def process_many(file_paths: List[str], **kwargs):
    """
    تفريغ مجموعة ملفات مع دعم الدمج الزمني للمقاطع والترجمات.

    المعاملات الاختيارية في kwargs:
      - merge_outputs: دمج المقاطع زمنيًا عبر الملفات (افتراضي True)
      - tag_sources: وسم نص كل مقطع باسم الملف [name] عند الدمج (افتراضي True)

    القيمة المرجعة:
      - قاموس بالمخرجات المدمجة، ويشمل المفتاح "items" الذي يحوي
        نتائج كل ملف على حدة كما تُعيدها الدالة process.
    """
    if not file_paths:
        return _err("الرجاء رفع ملفات.")

    merge_outputs = kwargs.pop("merge_outputs", True)
    tag_sources   = kwargs.pop("tag_sources", True)

    per_file_results: List[Dict] = []
    all_text_blocks: List[str]   = []
    all_raw_text: List[str]      = []
    all_segments: List[Dict]     = []
    cumulative_offset = 0.0

    for fp in file_paths:
        res = process(fp, **kwargs)
        per_file_results.append(res)
        name = pathlib.Path(fp).stem

        all_text_blocks.append(f"### ملف: {name}\n{res.get('text','')}\n")
        raw_from_segments = "\n".join([s.get("text", "") for s in res.get("segments", [])])
        all_raw_text.append(raw_from_segments)

        if merge_outputs:
            segs = res.get("segments", [])
            for s in segs:
                new_seg = dict(s)
                new_seg["start"] = float(s["start"]) + cumulative_offset
                new_seg["end"]   = float(s["end"])   + cumulative_offset
                if tag_sources:
                    new_seg["text"] = f"[{name}] {new_seg.get('text','')}"
                all_segments.append(new_seg)
            if segs:
                cumulative_offset += max(float(s["end"]) for s in segs)

    # ملف نصي موحّد
    merged_text = "\n\n".join(all_text_blocks).strip()
    merged_txt_path = str(OUTPUTS_DIR / "batch_transcripts.txt")
    pathlib.Path(merged_txt_path).write_text(merged_text, encoding="utf-8")

    merged_keywords = nlp_core.extract_keywords("\n".join(all_raw_text))

    # ترقيم المتكلمين في النص المدمج
    merged_text = _renumber_speakers(merged_text)

    merged_srt_path = None
    merged_vtt_path = None
    if merge_outputs and all_segments:
        all_segments.sort(key=lambda s: (float(s["start"]), float(s["end"])))
        srt_out = OUTPUTS_DIR / "batch_merged.srt"
        vtt_out = OUTPUTS_DIR / "batch_merged.vtt"
        merged_srt_path = segments_to_srt(all_segments, base_path="", out_path=str(srt_out))
        merged_vtt_path = segments_to_vtt(all_segments, base_path="", out_path=str(vtt_out))

    return {
        "text": merged_text,
        "txt_path": merged_txt_path,
        "summary": "",
        "summary_path": None,
        "keywords": merged_keywords,
        "segments": all_segments if merge_outputs else [],
        "srt_path": merged_srt_path,
        "vtt_path": merged_vtt_path,
        "items": per_file_results,
    }

# ===== تنظيف مؤقت =====
def cleanup_temp_files():
    try:
        temp_dir = pathlib.Path(tempfile.gettempdir())
        cutoff = time.time() - 86400  # 24h
        for temp_file in temp_dir.glob("asr_*.wav"):
            try:
                if temp_file.stat().st_mtime < cutoff:
                    temp_file.unlink()
            except Exception:
                pass
    except Exception:
        pass

atexit.register(cleanup_temp_files)
