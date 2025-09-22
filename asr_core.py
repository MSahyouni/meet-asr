# asr_core.py - نسخة مستقرة
import os, pathlib, tempfile, subprocess, shutil, atexit, re
# خيوط أقل وذاكرة أخف
os.environ.setdefault("OMP_NUM_THREADS","1")
os.environ.setdefault("MKL_NUM_THREADS","1")
os.environ.setdefault("NUMEXPR_NUM_THREADS","1")
os.environ.setdefault("CT2_USE_MMAP","1")
os.environ["SPEECHBRAIN_LOCAL_FILE_STRATEGY"] = "copy"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import numpy as np
import soundfile as sf
import resampy
from faster_whisper import WhisperModel
import librosa
import noisereduce as nr
import torch
from collections import Counter
from huggingface_hub import snapshot_download

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

MODEL_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]
_HAS_CUDA = torch.cuda.is_available()
DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "large-v3" if _HAS_CUDA else "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cuda" if _HAS_CUDA else "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE", "float16" if DEVICE == "cuda" else "int8")
_MODEL_CACHE = {}

SPK_DIR = pathlib.Path("voices"); SPK_DIR.mkdir(exist_ok=True)
_SPKRECOG = None
_ENROLLED = {}  # {name: np.ndarray(192,)}

# ديازة
DIAR_WIN = 1.5
DIAR_HOP = 0.75
AUTO_K_MAX = 5
AUTO_K_MIN = 1

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
def get_model(name: str, device: str = None, compute_type: str = None):
    dev = (device or DEVICE).lower()
    ctp = (compute_type or COMPUTE_TYPE).lower()
    key = (name, dev, ctp)

    if key not in _MODEL_CACHE:
        try:
            # 📌 تحديد مسار محلي ثابت لكل موديل
            local_dir = pathlib.Path("models") / f"whisper-{name}"
            if not local_dir.exists():
                print(f"[CACHE] تنزيل الموديل {name} لأول مرة...")
                snapshot_download(
                    repo_id=f"Systran/faster-whisper-{name}",
                    local_dir=local_dir.as_posix()
                )
            # 📌 استدعاء الموديل من المسار المحلي
            _MODEL_CACHE[key] = WhisperModel(local_dir.as_posix(), device=dev, compute_type=ctp)

        except Exception as e:
            print(f"[WHISPER] فشل تحميل {name}: {e} → استخدام fallback")
            fb = "base" if name != "base" else "tiny"
            fb_dir = pathlib.Path("models") / f"whisper-{fb}"
            if not fb_dir.exists():
                snapshot_download(
                    repo_id=f"Systran/faster-whisper-{fb}",
                    local_dir=fb_dir.as_posix()
                )
            _MODEL_CACHE[key] = WhisperModel(fb_dir.as_posix(), device=dev, compute_type=ctp)

    return _MODEL_CACHE[key]

def _squash_repeats(text: str) -> str:
    # يطوي تكرار نفس الكلمة العربية القصيرة (1–4 أحرف) ≥3 مرات إلى مرتين فقط
    patt = r'(?:(?<=\s)|^)([اأإآبتثجحخدذرزسشصضطظعغفقكلمنهوية]{1,4})(?:\s+\1){2,}(?=\s|$)'
    text = re.sub(patt, r'\1 \1', text)
    # حالات شائعة
    text = re.sub(r'(اي\s*){3,}', 'اي اي ', text)
    text = re.sub(r'(اه\s*){3,}', 'اه اه ', text)
    text = re.sub(r'(او\s*){3,}', 'او او ', text)
    return text

# ---------- ترقيعات SpeechBrain ----------
def _force_copy(fetched_file, destination, local_strategy=None):
    try:
        destination = pathlib.Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fetched_file, destination)
        return destination
    except Exception as e:
        print(f"[SB] نسخ فشل: {e}")
        return destination

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

        DUMMY_FILE = pathlib.Path("pretrained_models/_dummy_custom.py")
        DUMMY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not DUMMY_FILE.exists():
            DUMMY_FILE.write_text("# dummy\n", encoding="utf-8")

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

        local_dir = "pretrained_models/spkrec_ecapa_cpu"
        snapshot_download(repo_id="speechbrain/spkrec-ecapa-voxceleb", local_dir=local_dir)
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
        # لا تفتح stdout كـ PIPE على ويندوز
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode(errors="ignore")
        print(f"[FFMPEG] {err[:300]}")
        return False
    except Exception as e:
        print(f"[FFMPEG] خطأ عام: {e}")
        return False

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
        if not _ffmpeg_extract(path, tmp, target_sr):
            raise RuntimeError("فشل استخراج الصوت")
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
        segments, info = model_obj.transcribe(
            wav_path,
            language="ar",
            task="transcribe",
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.7,
                min_silence_duration_ms=800,
                speech_pad_ms=100,
            ),
            beam_size=3,
            best_of=3,
            temperature=0.0,
            log_prob_threshold=-1.2,
            no_speech_threshold=0.7,
            condition_on_previous_text=True,
            initial_prompt="لغة عربية عامية سورية." if whisper_mode == "whisper" else None,
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

        X = []
        with torch.no_grad():
            for (_, _, chunk) in frames:
                t = torch.from_numpy(chunk).float().unsqueeze(0)
                v = _to1d(rec.encode_batch(t))
                X.append(v)
        if not X:
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

def _clean_text_for_summary(text: str) -> str:
    t = re.sub(r"\[[0-9.:]+(?:→[0-9.:]+)?\]", " ", text)
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def extract_keywords(text, top_k=10):
    try:
        t = _clean_text_for_summary(text)
        toks = [w for w in _tokenize_ar(t) if w not in _AR_STOP]
        cnt = Counter(toks)
        return ", ".join([w for w,_ in cnt.most_common(top_k)])
    except Exception as e:
        print(f"[KW] {e}")
        return ""

def summarize_text(text, summary_mode="best"):
    try:
        if summary_mode == "off": return ""
        t = _clean_text_for_summary(text)
        sents = re.split(r"[\.!\?؟]+", t)
        sents = [s.strip() for s in sents if s.strip()]
        if len(sents) <= 3: return " ".join(sents)
        # TF-based scoring بدل طول الجملة فقط
        toks = [w for w in _tokenize_ar(t) if w not in _AR_STOP]
        freq = Counter(toks)
        def score(s): 
            ws = [w for w in _tokenize_ar(s) if w not in _AR_STOP]
            return sum(freq.get(w,0) for w in ws) / max(1,len(ws))
        if summary_mode == "fast":
            picked = [sents[0], sents[len(sents)//2], sents[-1]]
        else:
            ranked = sorted(((i,score(s),s) for i,s in enumerate(sents)), key=lambda x: x[1], reverse=True)[:3]
            picked = [t[2] for t in sorted(ranked, key=lambda x: x[0])]
        return "، ".join(picked)
    except Exception as e:
        print(f"[SUM] {e}")
        return (text[:200] + "...") if len(text) > 200 else text

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
            device_sel="auto", compute_sel="auto", summary_mode="best"):
    file_path = _normalize_single_file_input(file_path)
    if not file_path:
        return "الرجاء رفع ملف صحيح.", None, None, "", "", None
    try:
        if not os.path.exists(file_path):
            return f"الملف غير موجود: {file_path}", None, None, "", "", None
    except Exception as e:
        return f"خطأ في التحقق من الملف: {str(e)}", None, None, "", "", None

    try:
        if (device_sel or "auto") == "auto":
            device_sel = "cuda" if _HAS_CUDA else "cpu"
        if (compute_sel or "auto") == "auto":
            compute_sel = "float16" if device_sel == "cuda" else "int8"

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
        for s, who in zip(seglist, spk_labels):
            st = float(s.start); en = float(s.end)
            lines.append(f"[{st:.2f}→{en:.2f}] ({who}) {s.text.strip()}")

        full_txt = header_txt.split("\n\n", 1)[0] + "\n\n" + "\n".join(lines)
        full_txt = _squash_repeats(full_txt)

        summary_text = summarize_text(full_txt, summary_mode)
        keywords = extract_keywords(full_txt)

        out_dir = pathlib.Path("outputs"); out_dir.mkdir(exist_ok=True)
        base = _safe_filename(file_path)
        out_path = (out_dir / f"{base}_transcript.txt").as_posix()
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(full_txt)
        except Exception as e:
            print(f"[SAVE_TXT] {e}"); out_path = None

        sum_path = None
        if summary_text:
            sum_path = (out_dir / f"{base}_summary.txt").as_posix()
            try:
                with open(sum_path, "w", encoding="utf-8") as f:
                    f.write(f"الملخص:\n{summary_text}\n\nالكلمات المفتاحية:\n{keywords}")
            except Exception as e:
                print(f"[SAVE_SUM] {e}"); sum_path = None

        return full_txt, out_path, out_path, summary_text, keywords, sum_path

    except Exception as e:
        msg = f"خطأ أثناء المعالجة: {str(e)}"
        print(f"[PROCESS] {msg}")
        return msg, None, None, "", "", None


def process_many(file_paths, model_name=None, enhance=False, whisper_mode="normal",
                 diarize=False, auto_k=True, max_speakers=2, enroll_threshold=0.65,
                 device_sel="auto", compute_sel="auto", summary_mode="best"):
    if not file_paths:
        return "الرجاء رفع ملفات.", None, None, "", "", None
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
            return "لم أتعرف على مسارات صالحة.", None, None, "", "", None

        if (device_sel or "auto") == "auto":
            device_sel = "cuda" if _HAS_CUDA else "cpu"
        if (compute_sel or "auto") == "auto":
            compute_sel = "float16" if device_sel == "cuda" else "int8"
        if IS_WIN:
            diarize = False

        out_dir = pathlib.Path("outputs"); out_dir.mkdir(exist_ok=True)
        all_texts, all_summaries = [], []
        for fp in norm_paths:
            txt, _, _, summary, _, _ = process(
                fp, model_name, enhance, whisper_mode, diarize,
                auto_k, max_speakers, enroll_threshold,
                device_sel, compute_sel, summary_mode
            )

            txt = _squash_repeats(txt or "")

            name = pathlib.Path(fp).name
            all_texts.append(f"### ملف: {name}\n{txt}\n")
            if summary:
                all_summaries.append(f"### ملخص {name}:\n{summary}\n")

        merged_text = "\n\n".join(all_texts).strip()
        merged_summary = "\n\n".join(all_summaries).strip() if all_summaries else ""

        merged_path = (out_dir / "batch_transcripts.txt").as_posix()
        try:
            with open(merged_path, "w", encoding="utf-8") as f:
                f.write(merged_text)
        except Exception as e:
            print(f"[SAVE_BATCH_TXT] {e}"); merged_path = None

        merged_sum_path = None
        if merged_summary:
            merged_sum_path = (out_dir / "batch_summaries.txt").as_posix()
            try:
                with open(merged_sum_path, "w", encoding="utf-8") as f:
                    f.write(merged_summary)
            except Exception as e:
                print(f"[SAVE_BATCH_SUM] {e}"); merged_sum_path = None

        return merged_text, merged_path, merged_path, merged_summary, "", merged_sum_path

    except Exception as e:
        msg = f"خطأ في معالجة الملفات المتعددة: {str(e)}"
        print(f"[PROCESS_MANY] {msg}")
        return msg, None, None, "", "", None

# ---------- تنظيف مؤقت ----------
def cleanup_temp_files():
    try:
        temp_dir = pathlib.Path(tempfile.gettempdir())
        for temp_file in temp_dir.glob("asr_*.wav"):
            try: temp_file.unlink()
            except Exception: pass
    except Exception: pass

atexit.register(cleanup_temp_files)
