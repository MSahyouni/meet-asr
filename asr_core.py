# asr_core.py - نسخة مستقرة
import os, pathlib, tempfile, subprocess, shutil, atexit, re, time
from typing import Optional
# خيوط أقل وذاكرة أخف
os.environ.setdefault("OMP_NUM_THREADS","1")
os.environ.setdefault("MKL_NUM_THREADS","1")
os.environ.setdefault("NUMEXPR_NUM_THREADS","1")
os.environ.setdefault("CT2_USE_MMAP","1")
os.environ["SPEECHBRAIN_LOCAL_FILE_STRATEGY"] = "copy"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ.setdefault("HF_HOME", str((pathlib.Path(__file__).resolve().parent / "data" / ".hf")))
os.environ.setdefault("ASR_DATA_DIR", str(pathlib.Path(__file__).resolve().parent / "data"))
os.environ.setdefault("TRANSFORMERS_CACHE", str((pathlib.Path(__file__).resolve().parent / "data" / ".hf")))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str((pathlib.Path(__file__).resolve().parent / "data" / ".hf")))

import numpy as np
import soundfile as sf
import resampy
from faster_whisper import WhisperModel
import librosa
import noisereduce as nr
import torch
from collections import Counter
from huggingface_hub import snapshot_download
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib

# ---------- إعدادات عامة ----------
IS_WIN = os.name == "nt"
try:
    import multiprocessing as mp
    if IS_WIN:
        try: mp.set_start_method("spawn", force=True)
        except RuntimeError: pass
        try: torch.set_num_threads(1)
        except Exception: pass
except Exception:
    pass

MODEL_CHOICES = ["light", "heavy"]  # light=medium, heavy=large-v3
_HAS_CUDA = torch.cuda.is_available()
DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "heavy" if _HAS_CUDA else "light")
DEVICE = os.getenv("WHISPER_DEVICE", "cuda" if _HAS_CUDA else "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE", "float16" if DEVICE == "cuda" else "int8_float32")
# دقة ضرب المصفوفات في PyTorch 2.x لتحسين الاستدلال
try:
    if _HAS_CUDA and hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")
except Exception:
    pass

GPU_ID = int(os.getenv("GPU_ID", "0"))
ASR_VAD = os.getenv("ASR_VAD", "0") in ("1","true","True")
ASR_CHUNK = int(os.getenv("ASR_CHUNK_LEN", "30"))
ASR_BEAM  = int(os.getenv("ASR_BEAM", "3"))
_MODEL_CACHE = {}
LOG_LOAD = os.getenv("ASR_LOG_LOAD", "1") in ("1","true","True")

# مجلد بيانات موحد تحت data/
DATA_DIR = pathlib.Path(os.getenv("ASR_DATA_DIR", "data"))
OUTPUTS_DIR = DATA_DIR / "outputs"
MODELS_DIR  = DATA_DIR / "models"
SPK_DIR     = DATA_DIR / "voices"
for _d in (OUTPUTS_DIR, MODELS_DIR, SPK_DIR):
    _d.mkdir(parents=True, exist_ok=True)
KW_DIR      = MODELS_DIR / "keywords"
KW_DIR.mkdir(parents=True, exist_ok=True)
TFIDF_PATH  = (KW_DIR / "tfidf_ar.joblib")
_SPKRECOG = None
_ENROLLED = {}  # {name: np.ndarray(192,)}
_DIAR_CACHE = {}  # {(wav_path, mtime, win, hop): np.ndarray[n_frames, 192]}

# ديازة
DIAR_WIN = 1.5
DIAR_HOP = 0.75
AUTO_K_MAX = 5
AUTO_K_MIN = 1

# كائن خطأ موحّد ليرجِع دائمًا Dict
def _err(msg: str):
    return {
        "text": "",
        "txt_path": None,
        "summary": "",
        "summary_path": None,
        "keywords": "",
        "segments": [],
        "error": msg,
    }
# ---------- أدوات ملفية ----------
def _tmp_wav(suffix=".wav"):
    return tempfile.NamedTemporaryFile(prefix="asr_", suffix=suffix, delete=False).name

def _safe_filename(p):
    try:
        base = pathlib.Path(str(p)).stem or "audio"
        return "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in base) or "audio"
    except Exception:
        return "audio"

# ---------- نموذج Whisper مع كاش ----------
def _resolve_model(name: str) -> str:
    n = (name or "").strip().lower()
    if n in ("light", "medium"): return "medium"
    if n in ("heavy", "large-v3"): return "large-v3"
    # أي اسم آخر → light كافتراضي
    return "medium"

def get_model(name: str, device: str = None, compute_type: str = None):
    name = _resolve_model(name)
    dev = (device or DEVICE).lower()
    ctp = (compute_type or COMPUTE_TYPE).lower()
    key = (name, dev, ctp)

    if key not in _MODEL_CACHE:
        try:
            # 📌 تحديد المسار ضمن data/models/
            local_dir = MODELS_DIR / f"whisper-{name}"
            if not local_dir.exists():
                print(f"[CACHE] تنزيل الموديل {name} لأول مرة...")
                snapshot_download(
                    repo_id=f"Systran/faster-whisper-{name}",
                    local_dir=local_dir.as_posix(),
                    local_dir_use_symlinks=False,
                    cache_dir=(DATA_DIR / ".hf").as_posix()
                )
            else:
                if LOG_LOAD:
                    print(f"[CACHE] استخدام النسخة المحلية: {local_dir.as_posix()}")                
            dev, ctp = _safe_compute(dev, ctp)  # <-- حارس موحّد
            if torch.cuda.is_available() and dev == "cuda":
                _MODEL_CACHE[key] = WhisperModel(
                    local_dir.as_posix(),
                    device=dev,
                    device_index=GPU_ID,
                    compute_type=ctp,
                    cpu_threads=max(1, os.cpu_count() // 2),
                    download_root=MODELS_DIR.as_posix()
                )
            else:
                _MODEL_CACHE[key] = WhisperModel(
                    local_dir.as_posix(),
                    device=dev,                 # cpu
                    compute_type=ctp,           # يضمن int8_float32 على CPU
                    cpu_threads=max(1, os.cpu_count() // 2),
                    download_root=MODELS_DIR.as_posix()
                )
            if LOG_LOAD:
                print(f"[WHISPER] loaded name={name} path={local_dir.as_posix()} device={dev} compute={ctp}")

        except Exception as e:
            print(f"[WHISPER] فشل تحميل {name}: {e} → استخدام fallback")
            fb = "medium" if name != "medium" else "tiny"
            fb_dir = MODELS_DIR / f"whisper-{fb}"
            if not fb_dir.exists():
                snapshot_download(
                    repo_id=f"Systran/faster-whisper-{fb}",
                    local_dir=fb_dir.as_posix(),
                    local_dir_use_symlinks=False,
                    cache_dir=(DATA_DIR / ".hf").as_posix()
                )
            fdev, fctp = _safe_compute(dev, ctp)
            _MODEL_CACHE[key] = WhisperModel(
                fb_dir.as_posix(), device=fdev, compute_type=fctp,
                cpu_threads=max(1, os.cpu_count() // 2), download_root=MODELS_DIR.as_posix()
            )
            if LOG_LOAD:
                print(f"[WHISPER] fallback name={fb} path={fb_dir.as_posix()} device={fdev} compute={fctp}")

    return _MODEL_CACHE[key]

# داخل مُحمّل Whisper أضف حارس الدقة إن لم يكن موجودًا:
def _safe_compute(device, compute_type):
    dev = (device or ("cuda" if _HAS_CUDA else "cpu")).lower()
    ctp = (compute_type or ("float16" if dev=="cuda" else "int8_float32")).lower()
    if dev != "cuda" and ctp == "float16":
        ctp = "int8_float32"
    return dev, ctp

def _squash_repeats(text: str) -> str:
    # يطوي تكرار نفس الكلمة العربية القصيرة (1–4 أحرف) ≥3 مرات إلى مرتين فقط
    patt = r'(?:(?<=\s)|^)([اأإآبتثجحخدذرزسشصضطظعغفقكلمنهوية]{1,4})(?:\s+\1){2,}(?=\s|$)'
    text = re.sub(patt, r'\1 \1', text)
    # حالات شائعة
    text = re.sub(r'(اي\s*){3,}', 'اي اي ', text)
    text = re.sub(r'(اه\s*){3,}', 'اه اه ', text)
    text = re.sub(r'(او\s*){3,}', 'او او ', text)
    return text

# -------- تنظيف كلام (حشو عربي + تكرارات) --------
_FILLERS = {
    "يعني","هيك","تمام","مزبوط","اوكي","أوكي","طيب","مم","اها","اهاه","اممم","اي","ايه","اها؟","طيب؟","اوكي؟",
    "تمام؟","مزبوط؟","هي","هون","شو","اه","آه"
}
def _clean_utterance(t: str) -> str:
    t0 = re.sub(r"\s+", " ", (t or "").strip())
    # احذف كلمات الحشو المفردة
    words, out, prev, run = t0.split(), [], None, 0
    for w in words:
        w0 = w.strip(".,،!؟").lower()
        if w0 in _FILLERS: 
            continue
        if w0 == prev:
            run += 1
            if run > 3:
                continue
        else:
            prev, run = w0, 1
        out.append(w)
    t1 = " ".join(out).strip()
    # طيّ تكرارات قصيرة جدًا
    return _squash_repeats(t1)

# ---------- ترقيعات SpeechBrain ----------
def _force_copy(fetched_file, destination, local_strategy=None):
    dest = pathlib.Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        # إن كان المصدر غير موجود أو ليس ملفًا، أنشئ ملفًا فارغًا مكانه
        src = pathlib.Path(str(fetched_file))
        if src.exists() and src.is_file():
            shutil.copy2(src, dest)
        else:
            dest.write_text("# stub", encoding="utf-8")
    except Exception:
        try: dest.write_text("# stub", encoding="utf-8")
        except Exception: pass
    return dest

def get_spkrec():
    global _SPKRECOG
    if _SPKRECOG is not None:
        return _SPKRECOG
    try:
        from huggingface_hub import snapshot_download
        from speechbrain.inference import SpeakerRecognition
        try:
            import speechbrain.utils.fetching as sb_fetch
        except ImportError:
            from speechbrain.utils import data_utils as sb_fetch
        try:
            import speechbrain.inference.interfaces as sb_interfaces
        except Exception:
            class _SBInterfacesFallback:
                def fetch(*a, **k): raise RuntimeError("interfaces missing")
                def link_with_strategy(*a, **k): return None
            sb_interfaces = _SBInterfacesFallback()

        DUMMY_FILE = (DATA_DIR / "pretrained_models" / "_dummy_custom.py")
        DUMMY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not DUMMY_FILE.exists():
            DUMMY_FILE.write_text("# stub\n", encoding="utf-8")

        if hasattr(sb_fetch, "link_with_strategy"): sb_fetch.link_with_strategy = _force_copy
        if hasattr(sb_interfaces, "link_with_strategy"): sb_interfaces.link_with_strategy = _force_copy

        def _wrap_fetch_module(mod):
            fname = "fetch" if hasattr(mod, "fetch") else ("download_file" if hasattr(mod, "download_file") else None)
            if not fname: return
            original = getattr(mod, fname)
            def wrapper(*args, **kwargs):
                code = getattr(original, "__code__", None)
                names = tuple(getattr(code, "co_varnames", ())) if code else ()
                if "filename" in names and "filename" not in kwargs and "save_filename" not in kwargs:
                    kwargs["filename"] = str(DUMMY_FILE)
                return original(*args, **kwargs)
            setattr(mod, fname, wrapper)
        _wrap_fetch_module(sb_fetch); _wrap_fetch_module(sb_interfaces)

        local_dir = (MODELS_DIR / "spkrec_ecapa_cpu").as_posix()
        snapshot_download(
            repo_id="speechbrain/spkrec-ecapa-voxceleb",
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            cache_dir=(DATA_DIR / ".hf").as_posix()
        )
        _SPKRECOG = SpeakerRecognition.from_hparams(
            source=local_dir, savedir=local_dir,
            run_opts={"device": "cpu"},
            hparams_file="hyperparams.yaml",
        )
    except Exception as e:
        print(f"[SB] فشل تحميل ECAPA: {e}")
        _SPKRECOG = None
    return _SPKRECOG

# ---------- I/O صوت ----------
def _is_container(p: str) -> bool:
    try:
        return pathlib.Path(p).suffix.lower() in {".mp4",".m4a",".mov",".3gp",".mkv",".webm",".avi"}
    except Exception:
        return False

def _ffmpeg_extract(src: str, dst_wav: str, target_sr=16000):
    try:
        cmd = ["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error",
               "-i",src,"-ac","1","-ar",str(target_sr),"-vn","-acodec","pcm_s16le",dst_wav]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode(errors="ignore")
        print(f"[FFMPEG] {err[:300]}")
        raise RuntimeError("ffmpeg_extract_failed") from e
    except Exception as e:
        print(f"[FFMPEG] خطأ عام: {e}")
        raise RuntimeError("ffmpeg_extract_failed") from e

def _wav_read_mono(path, target_sr=16000):
    try:
        y, sr = sf.read(path, dtype="float32", always_2d=False)
        if isinstance(y, np.ndarray) and y.ndim > 1:
            y = y.mean(axis=1)
        if sr != target_sr:
            y = resampy.resample(y, sr, target_sr)
            sr = target_sr
        return y.astype(np.float32, copy=False), sr
    except Exception as e:
        print(f"[READ] {path}: {e}")
        return np.array([0.0], dtype=np.float32), target_sr

def to_wav16k(path, target_sr=16000):
    if not path or not os.path.exists(str(path)):
        raise ValueError(f"الملف غير موجود: {path}")
    if _is_container(path):
        tmp = _tmp_wav()
        _ffmpeg_extract(path, tmp, target_sr)
        return tmp
    y, sr = _wav_read_mono(path, target_sr)
    y = np.clip(y, -1.0, 1.0)
    tmp = _tmp_wav()
    sf.write(tmp, (y*32767).astype(np.int16), target_sr, subtype="PCM_16")
    return tmp

# ---------- تحسين ----------
def noisereduce(y, sr, strong=False):
    try:
        return nr.reduce_noise(y=y, sr=sr, prop_decrease=0.9 if strong else 0.6, stationary=False)
    except Exception as e:
        print(f"[NR] {e}")
        return y

def enhance_audio(y, sr, strong=False, gain_db=6.0):
    try:
        y = librosa.effects.preemphasis(y, coef=0.85)
        y = noisereduce(y, sr, strong=strong)
        rms = float(np.sqrt(np.mean(y**2) + 1e-9))
        target_rms = 0.08
        if rms > 0: y *= (target_rms / rms)
        y = np.clip(y * (10 ** (gain_db/20.0)), -1.0, 1.0)
        return y.astype(np.float32, copy=False)
    except Exception as e:
        print(f"[ENH] {e}")
        return y

def to_wav16k_enhanced(path, enhance=False, whisper_mode="normal", target_sr=16000):
    wav = to_wav16k(path, target_sr)
    if not enhance:
        return wav
    y, sr = _wav_read_mono(wav, target_sr)
    strong = (whisper_mode == "whisper")
    y = enhance_audio(y, sr, strong=strong, gain_db=8.0 if strong else 5.0)
    tmp = _tmp_wav()
    sf.write(tmp, (y*32767).astype(np.int16), sr, subtype="PCM_16")
    return tmp

# ---------- ASR ----------
def run_asr(wav_path, model_obj, whisper_mode="normal"):
    try:
        init_prompt = "لغة عربية عامية سورية." if whisper_mode == "whisper" else "لغة عربية فصحى."
        segments, info = model_obj.transcribe(
            wav_path,
            language="ar",
            task="transcribe",
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.7,
                min_silence_duration_ms=800 if whisper_mode == "whisper" else 1000,
                speech_pad_ms=100,
            ),
            condition_on_previous_text=False,
            temperature=[0.0, 0.2, 0.4],
            beam_size=5,
            best_of=5,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-0.3,
            no_speech_threshold=0.6 if whisper_mode == "whisper" else 0.55,
            word_timestamps=False,
            initial_prompt=init_prompt,
        )
        seglist = [s for s in segments]
        lines = [f"[{s.start:.2f}→{s.end:.2f}] {s.text.strip()}" for s in seglist]
        duration = getattr(info, "duration", 0.0) or 0.0
        language = getattr(info, "language", "ar") or "ar"
        probability = getattr(info, "language_probability", 0.0) or 0.0
        meta = f"المدة: {duration:.1f}s | اللغة: {language} | ثقة: {probability:.2f}"
        return meta + "\n\n" + "\n".join(lines), seglist
    except Exception as e:
        print(f"[ASR] {e}")
        return f"خطأ في المعالجة: {e}", []

# ---------- بصمات المتكلمين ----------
def cosine(a, b):
    try:
        an = a / (np.linalg.norm(a) + 1e-9)
        bn = b / (np.linalg.norm(b) + 1e-9)
        return float(np.dot(an, bn))
    except Exception:
        return 0.0

def _to1d(emb):
    try:
        if isinstance(emb, torch.Tensor):
            emb = emb.detach().cpu().numpy()
        arr = np.asarray(emb)
        if arr.ndim == 1: return arr
        if arr.shape[-1] == 192: return arr.reshape(-1, 192).mean(axis=0)
        return arr.reshape(-1)[:192]
    except Exception:
        return np.zeros(192, dtype=np.float32)

def _embed_file(path):
    try:
        rec = get_spkrec()
        if rec is None:
            return np.zeros(192, dtype=np.float32)
        wav, sr = _wav_read_mono(path, 16000)
        t = torch.from_numpy(wav).float().unsqueeze(0)
        with torch.no_grad():
            emb = _to1d(rec.encode_batch(t))
        return emb
    except Exception as e:
        print(f"[EMB] {e}")
        return np.zeros(192, dtype=np.float32)

def load_enrolled():
    try:
        _ENROLLED.clear()
        for p in SPK_DIR.iterdir():
            if p.is_dir():
                emb = p / "embedding.npy"
                if emb.exists():
                    _ENROLLED[p.name] = np.load(emb)
        return list(_ENROLLED.keys())
    except Exception as e:
        print(f"[ENROLL_LOAD] {e}")
        return []

def get_speaker_files(name: str):
    try:
        name = (name or "").strip()
        if not name:
            return []
        p = SPK_DIR / name
        if not p.exists() or not p.is_dir():
            return []
        files = []
        for fp in sorted(p.iterdir()):
            if fp.is_file() and fp.name != "embedding.npy":
                files.append(fp.as_posix())
        return files
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
        if name in _ENROLLED:
            _ENROLLED.pop(name, None)
        return True, "تم الحذف."
    except Exception as e:
        return False, f"فشل الحذف: {e}"

def enroll_voice(name: str, files: list):
    try:
        name = (name or "").strip()
        if not name or not files:
            return False, "أدخل اسمًا ورفَع ملفات صوتية."
        user_dir = SPK_DIR / name
        if user_dir.exists(): shutil.rmtree(user_dir)
        user_dir.mkdir(parents=True, exist_ok=True)
        embs = []
        for f in files:
            try:
                fpath = f["name"] if isinstance(f, dict) and "name" in f else (f.name if hasattr(f, "name") else f)
                if not fpath or not os.path.exists(str(fpath)): continue
                dst = user_dir / pathlib.Path(fpath).name
                shutil.copyfile(fpath, dst)
                emb = _embed_file(str(dst))
                if emb is not None: embs.append(emb)
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

# ---------- ديازة ----------
try:
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False
    print("[DIAR] sklearn غير متوفر، سيتم تعطيل التجميع")

def label_speakers(wav_path, seglist, threshold=0.65):
    if not SKLEARN_AVAILABLE:
        return ["متكلم 1" for _ in seglist] if seglist else ["متكلم 1"]
    try:
        if not _ENROLLED: load_enrolled()
        y, sr = _wav_read_mono(wav_path, 16000)
        win = int(DIAR_WIN * sr); hop = int(DIAR_HOP * sr)

        frames, tcur, i = [], 0.0, 0
        while i + win <= len(y):
            frames.append((tcur, tcur + DIAR_WIN, y[i:i+win]))
            i += hop; tcur += DIAR_HOP
        if not frames:
            return ["متكلم 1" for _ in seglist] if seglist else ["متكلم 1"]

        rec = get_spkrec()
        if rec is None:
            return ["متكلم 1" for _ in seglist] if seglist else ["متكلم 1"]

        # كاش embeddings على مستوى الملف
        key = (wav_path, pathlib.Path(wav_path).stat().st_mtime, win, hop)
        X = _DIAR_CACHE.get(key)
        if X is None:
            Xl = []
            with torch.no_grad():
                for (_, _, chunk) in frames:
                    t = torch.from_numpy(chunk).float().unsqueeze(0)
                    v = _to1d(rec.encode_batch(t))
                    Xl.append(v)
            if not Xl:
                return ["متكلم 1" for _ in seglist] if seglist else ["متكلم 1"]
            X = np.stack(Xl, axis=0)
            _DIAR_CACHE[key] = X
        if X.size == 0:
            return ["متكلم 1" for _ in seglist] if seglist else ["متكلم 1"]
        X = np.stack(X, axis=0)

        def _cluster_with_k(k):
            try:
                try:
                    model = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
                except TypeError:
                    model = AgglomerativeClustering(n_clusters=k, affinity="cosine", linkage="average")
                labels = model.fit_predict(X)
                score = -1.0
                if not IS_WIN and k > 1 and len(set(labels)) > 1:
                    try:
                        score = silhouette_score(X, labels, metric="cosine")
                    except Exception:
                        score = -1.0
                return labels, score
            except Exception as e:
                print(f"[CLUSTER] {e}")
                return np.zeros(len(X), dtype=int), -1.0

        k_best = max(1, int(getattr(label_speakers, "_k", 2)))
        auto_k = bool(getattr(label_speakers, "_auto_k", True))
        if auto_k:
            labels_best, score_best = None, -1.0
            for k in range(AUTO_K_MIN, min(AUTO_K_MAX, len(X)) + 1):
                lbls, sc = _cluster_with_k(k)
                if sc > score_best:
                    score_best, labels_best, k_best = sc, lbls, k
            z = labels_best if labels_best is not None else np.zeros(len(X), dtype=int)
        else:
            z, _ = _cluster_with_k(k_best)

        cluster_names = {}
        for c in sorted(set(z)):
            idx = np.where(z == c)[0]
            c_emb = X[idx].mean(axis=0)
            best_name, best_sim = None, -1.0
            for name, ref in _ENROLLED.items():
                sim = cosine(c_emb, ref)
                if sim > best_sim:
                    best_sim, best_name = sim, name
            cluster_names[c] = best_name if (best_name and best_sim >= threshold) else None

        diar_segs = []
        if len(frames) > 0:
            cur_c = z[0]; cur_start = frames[0][0]; cur_end = frames[0][1]
            for j in range(1, len(frames)):
                if z[j] == cur_c and abs(frames[j][0] - cur_end) < 1e-6:
                    cur_end = frames[j][1]
                else:
                    diar_segs.append((cur_start, cur_end, cur_c))
                    cur_c = z[j]; cur_start = frames[j][0]; cur_end = frames[j][1]
            diar_segs.append((cur_start, cur_end, cur_c))

        def _overlap(a0,a1,b0,b1): return max(0.0, min(a1,b1) - max(a0,b0))

        labels_out, anon_map, anon_counter = [], {}, 1
        for s in seglist:
            s0, s1 = float(s.start), float(s.end)
            best_c, best_ov = None, 0.0
            for (d0, d1, cc) in diar_segs:
                ov = _overlap(s0, s1, d0, d1)
                if ov > best_ov:
                    best_ov, best_c = ov, cc
            if best_c is None:
                labels_out.append("متكلم 1"); continue
            name = cluster_names.get(best_c)
            if name:
                labels_out.append(name)
            else:
                if best_c not in anon_map:
                    anon_map[best_c] = f"متكلم {anon_counter}"; anon_counter += 1
                labels_out.append(anon_map[best_c])
        return labels_out
    except Exception as e:
        print(f"[DIAR] {e}")
        return ["متكلم 1" for _ in seglist] if seglist else ["متكلم 1"]

# ---------- تلخيص وكلمات مفتاحية بالعربية ----------
_AR_STOP = set("""
في على الى إلى مع عن من ما هذا هذه ذلك تلك هناك هنا ثم حيث لقد قد كان كانت يكون كانوا كنت إن أن لكن لأن لو إذا إذ كما ربما حتى بين لدى لديهم لدي إليها فيها منه منها فيه بها بنا لكم لنا فقط جدا جدًا حقا حقيقة أيضًا أيضاً قبل بعد خلال أثناء ضد عبر نحو فوق تحت بين إلا بأن وإن أنّ لا لم لن ليس بدون غير كافة جميع بعض أي أحد نعم مثل ايضا ايضاً جداً جدا حقاً حقا
""".split())

def _normalize_ar(s: str) -> str:
    s = s.replace("\u0640","")
    s = re.sub("[\u0617-\u061A\u064B-\u0652]", "", s)
    s = re.sub("[\u0622\u0623\u0625]", "\u0627", s)
    s = s.replace("ى","ي").replace("ئ","ي").replace("ؤ","و").replace("ة","ه")
    return s

def _tokenize_ar(s: str):
    s = _normalize_ar(s)
    return re.findall(r"[اأإآابتثجحخدذرزسشصضطظعغفقكلمنهوية]{2,}", s)

# ========= TF-IDF اختياري اعتماداً على Parquet =========
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    _SK_TFIDF_OK = True
except Exception:
    _SK_TFIDF_OK = False

_TFIDF = {"vec": None, "vocab": None}
_TFIDF_MAX_ROWS = int(os.getenv("TFIDF_MAX_ROWS", "140000"))
_DATASET_DIR = pathlib.Path(os.getenv("ASR_DATA_DIR", "data")) / "datasets" / "ArabicText-Large" / "data"

def _split_tokens(s: str):
    # الكوربس لدينا مُجزّأ مسبقًا (مسافات). لا تستعمل lambda كي يصلح الحفظ بـ joblib.
    return s.split()

def _iter_parquet_texts(max_rows=_TFIDF_MAX_ROWS):
    if not _DATASET_DIR.exists():
        return
    remaining = max_rows
    for pq in sorted(_DATASET_DIR.glob("*.parquet")):
        try:
            df = pd.read_parquet(pq)
        except Exception as e:
            print(f"[PARQUET] {pq}: {e}")
            continue
        if df.empty:
            continue
        text_cols = [c for c in df.columns if str(c).lower() in ("text","content","body","document")]
        if not text_cols:
            text_cols = df.select_dtypes(include=["object"]).columns.tolist()
        if not text_cols:
            continue
        col = text_cols[0]
        for v in df[col].astype(str).head(remaining):
            yield " ".join(_tokenize_ar(v))
        remaining -= min(len(df), remaining)
        if remaining <= 0:
            break

def _load_tfidf_from_disk():
    try:
        if TFIDF_PATH.exists():
            vec = joblib.load(TFIDF_PATH)
            _TFIDF["vec"] = vec
            _TFIDF["vocab"] = vec.get_feature_names_out()
            print(f"[TFIDF] loaded from {TFIDF_PATH}")
            return True
    except Exception as e:
        print(f"[TFIDF] load failed: {e}")
    return False

def _ensure_tfidf():
    if _TFIDF["vec"] is not None:
        return True
    if TFIDF_PATH.exists():
        try:
            _TFIDF["vec"] = joblib.load(TFIDF_PATH)
            _TFIDF["vocab"] = _TFIDF["vec"].get_feature_names_out()
            return True
        except Exception as e:
            print(f"[TFIDF] load failed: {e}")

    if not (_SK_TFIDF_OK and _DATASET_DIR.exists()):
        return False
    try:
        corpus = list(_iter_parquet_texts(max_rows=140000))
        if not corpus:
            return False
        vec = TfidfVectorizer(
            tokenizer=_split_tokens,     # ← بدل lambda
            preprocessor=None,
            token_pattern=None,
            ngram_range=(1, 2),
            min_df=3,
            max_df=0.8
        )
        vec.fit(corpus)
        joblib.dump(vec, TFIDF_PATH)
        _TFIDF["vec"] = vec
        _TFIDF["vocab"] = vec.get_feature_names_out()
        print(f"[TFIDF] fitted {len(corpus)} docs, {len(_TFIDF['vocab'])} terms")
        return True
    except Exception as e:
        print(f"[TFIDF] build failed: {e}")
        _TFIDF["vec"] = None
        return False
    
def _clean_text_for_summary(text: str) -> str:
    t = re.sub(r"\[[0-9.:]+(?:→[0-9.:]+)?\]", " ", text)  # احذف التواقيت
    t = re.sub(r"\(.*?\)", " ", t)                       # احذف (المتحدث)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def extract_keywords(text, top_k=10):
    """يرجّع كلمات مفتاحية: يفضّل TF-IDF من Parquet، وإلا عدّ تكراري بسيط."""
    try:
        t = _clean_text_for_summary(text)
        # محاولة TF-IDF
        if _ensure_tfidf():
            doc = " ".join(_tokenize_ar(t))
            if doc.strip():
                v = _TFIDF["vec"].transform([doc]).toarray()[0]
                idx = v.argsort()[::-1]
                out = []
                for i in idx:
                    tok = _TFIDF["vocab"][i]
                    if tok in _AR_STOP:
                        continue
                    out.append(tok)
                    if len(out) >= top_k:
                        break
                if out:
                    return ", ".join(out)
        # احتياطي: تكرارات بسيطة
        toks = [w for w in _tokenize_ar(t) if w not in _AR_STOP]
        cnt = Counter(toks)
        return ", ".join([w for w, _ in cnt.most_common(top_k)])
    except Exception as e:
        print(f"[KW] {e}")
        return ""

def summarize_text(text, summary_mode="off"):
    return ""

# ---------- توليد SRT/VTT وإصدار ----------
def _fmt_ts(t: float) -> str:
    t = max(0.0, float(t))
    total_ms = int(round(t * 1000.0))   # ← أدق
    s, ms = divmod(total_ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def segments_to_srt(segments, base_txt_path: str) -> str:
    p = pathlib.Path(base_txt_path) if base_txt_path else (OUTPUTS_DIR / "transcript")
    srt_path = p.with_suffix(".srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(
                f"{i}\n{_fmt_ts(seg['start'])} --> {_fmt_ts(seg['end'])}\n"
                f"{seg['speaker']}: {seg['text']}\n\n"
            )
    return srt_path.as_posix()

def segments_to_vtt(segments, base_txt_path: str) -> str:
    p = pathlib.Path(base_txt_path) if base_txt_path else (OUTPUTS_DIR / "transcript")
    vtt_path = p.with_suffix(".vtt")
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            st = _fmt_ts(seg["start"]).replace(",", ".")
            en = _fmt_ts(seg["end"]).replace(",", ".")
            f.write(f"{st} --> {en}\n{seg['speaker']}: {seg['text']}\n\n")
    return vtt_path.as_posix()

def version() -> str:
    return "asr_core/1.0.0"

# ---------- نقاط الدخول ----------
def _normalize_single_file_input(file_path):
    try:
        if isinstance(file_path, dict):
            file_path = file_path.get("name") or file_path.get("path")
        return str(file_path) if file_path else ""
    except Exception:
        return ""

def process(file_path, model_name=None, enhance=False, whisper_mode="normal",
            diarize=False, auto_k=True, max_speakers=2, enroll_threshold=0.65,
            device_sel="auto", compute_sel="auto", summary_mode="best",
            punctuate=False):
    file_path = _normalize_single_file_input(file_path)
    if not file_path:
        return _err("الرجاء رفع ملف صحيح.")
    try:
        if not os.path.exists(file_path):
            return _err(f"الملف غير موجود: {file_path}")
    except Exception as e:
        return _err(f"خطأ في التحقق من الملف: {str(e)}")

    try:
        if (device_sel or "auto") == "auto":
            device_sel = "cuda" if _HAS_CUDA else "cpu"
        if (compute_sel or "auto") == "auto":
            compute_sel = "float16" if device_sel == "cuda" else "int8_float32"

        if IS_WIN and diarize:
            # تقليل التعقيد لتجنّب أخطاء PIPE/MP
            auto_k = False if auto_k is None else bool(auto_k)
            max_speakers = min(2, int(max_speakers or 2))

        wav = to_wav16k_enhanced(file_path, enhance=enhance, whisper_mode=whisper_mode)
        model = get_model(model_name or DEFAULT_MODEL, device_sel, compute_sel)
        header_txt, seglist = run_asr(wav, model, whisper_mode=whisper_mode)

        if diarize:
            label_speakers._auto_k = bool(auto_k)
            label_speakers._k = int(max(1, int(max_speakers or 2)))
            spk_labels = label_speakers(wav, seglist, threshold=float(enroll_threshold or 0.65))
        else:
            spk_labels = ["غير معروف"] * len(seglist)

        lines = []
        seg_rows = []
        last_end = None
        for s, who in zip(seglist, spk_labels):
            st = float(s.start); en = float(s.end)
            txt = _clean_utterance(s.text.strip())
            # تنقيط بسيط حسب فجوة الصمت
            if punctuate and last_end is not None and (st - last_end) >= 1.2 and txt and not txt.endswith(("؟","!",".")):
                txt += "."
            lines.append(f"[{st:.2f}→{en:.2f}] ({who}) {txt}")
            seg_rows.append({"start": st, "end": en, "speaker": who, "text": txt})
            last_end = en

        full_txt = header_txt.split("\n\n", 1)[0] + "\n\n" + "\n".join(lines)
        full_txt = _squash_repeats(full_txt)

        summary_text = ""
        keywords = extract_keywords(full_txt)

        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        base = _safe_filename(file_path)
        out_path = (OUTPUTS_DIR / f"{base}_transcript.txt").as_posix()
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(full_txt)
        except Exception as e:
            print(f"[SAVE_TXT] {e}"); out_path = None

        sum_path = None

        # توليد ملفات SRT/VTT
        srt_path = vtt_path = None
        try:
            if seg_rows:
                srt_path = segments_to_srt(seg_rows, out_path)
                vtt_path = segments_to_vtt(seg_rows, out_path)
        except Exception as e:
            print(f"[TIMECODES] {e}")

        # كائن موحّد للنتيجة
        return {
            "text": full_txt,
            "txt_path": out_path,
            "summary": "",
            "summary_path": sum_path,
            "keywords": keywords,
            "segments": seg_rows,
            "srt_path": srt_path,
            "vtt_path": vtt_path,
        }

    except Exception as e:
        msg = f"خطأ أثناء المعالجة: {str(e)}"
        print(f"[PROCESS] {msg}")
        return _err(msg)


def process_many(file_paths, model_name=None, enhance=False, whisper_mode="normal",
                 diarize=False, auto_k=True, max_speakers=2, enroll_threshold=0.65,
                 device_sel="auto", compute_sel="auto", summary_mode="best",
                 punctuate=False):
    if not file_paths:
        return _err("الرجاء رفع ملفات.")
    try:
        if isinstance(file_paths, dict):
            fp = file_paths.get("name") or file_paths.get("path")
            file_paths = [fp] if fp else []
        if not isinstance(file_paths, (list, tuple)):
            file_paths = [file_paths]

        norm_paths = []
        for fp in file_paths:
            if not fp: continue
            if isinstance(fp, dict):
                p = fp.get("name") or fp.get("path")
                if p: norm_paths.append(str(p))
            else:
                norm_paths.append(str(fp))
        if not norm_paths:
            return _err("لم أتعرف على مسارات صالحة.")

        if (device_sel or "auto") == "auto":
            device_sel = "cuda" if _HAS_CUDA else "cpu"
        if (compute_sel or "auto") == "auto":
            compute_sel = "float16" if device_sel == "cuda" else "int8_float32"
        if IS_WIN:
            diarize = False

        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        all_texts, all_summaries = [], []
        for fp in norm_paths:
            res = process(
                fp, model_name, enhance, whisper_mode, diarize,
                auto_k, max_speakers, enroll_threshold,
                device_sel, compute_sel, "off", punctuate=punctuate
            )

            txt = _squash_repeats((res or {}).get("text",""))

            name = pathlib.Path(fp).name
            all_texts.append(f"### ملف: {name}\n{txt}\n")
            if res and res.get("summary"):
                all_summaries.append(f"### ملخص {name}:\n{res['summary']}\n")

        merged_text = "\n\n".join(all_texts).strip()
        merged_summary = "\n\n".join(all_summaries).strip() if all_summaries else ""

        merged_path = (OUTPUTS_DIR / "batch_transcripts.txt").as_posix()
        try:
            with open(merged_path, "w", encoding="utf-8") as f:
                f.write(merged_text)
        except Exception as e:
            print(f"[SAVE_BATCH_TXT] {e}"); merged_path = None

        merged_sum_path = None
        if merged_summary:
            merged_sum_path = (OUTPUTS_DIR / "batch_summaries.txt").as_posix()
            try:
                with open(merged_sum_path, "w", encoding="utf-8") as f:
                    f.write(merged_summary)
            except Exception as e:
                print(f"[SAVE_BATCH_SUM] {e}"); merged_sum_path = None

        return {
            "text": merged_text,
            "txt_path": merged_path,
            "summary": "",
            "summary_path": None,
            "keywords": "",
            "segments": [],
            "srt_path": None,
            "vtt_path": None,
        }

    except Exception as e:
        msg = f"خطأ في معالجة الملفات المتعددة: {str(e)}"
        print(f"[PROCESS_MANY] {msg}")
        return _err(msg)

# ---------- تنظيف مؤقت ----------
def cleanup_temp_files():
    try:
        temp_dir = pathlib.Path(tempfile.gettempdir())
        for temp_file in temp_dir.glob("asr_*.wav"):
            if temp_file.stat().st_mtime < (time.time() - 86400):  # أقدم من يوم
                try:
                    temp_file.unlink()
                except Exception:
                    pass
    except Exception:
        pass

atexit.register(cleanup_temp_files)
