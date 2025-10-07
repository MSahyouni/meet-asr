import os, pathlib, tempfile, subprocess, shutil, re, time
import json, requests
import warnings, logging

# ===== بيئة تمنع الروابط الرمزية على ويندوز =====
os.environ["SPEECHBRAIN_LOCAL_FILE_STRATEGY"] = "copy"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", message="Requested Pretrainer collection using symlinks", module="speechbrain.utils.parameter_transfer")
logging.getLogger("transformers").setLevel(logging.ERROR)

import numpy as np
import soundfile as sf
import resampy
import gradio as gr
from faster_whisper import WhisperModel
import librosa
import noisereduce as nr
import torch
from huggingface_hub import snapshot_download
from speechbrain.inference import SpeakerRecognition
import speechbrain.utils.fetching as sb_fetch
import speechbrain.inference.interfaces as sb_interfaces

# سكِلرن: تعنقد + TF-IDF
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer

# =============== ترقيعات SpeechBrain/HF على ويندوز ===============
def _force_copy(fetched_file, destination, local_strategy=None):
    destination = pathlib.Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fetched_file, destination)
    return destination

sb_fetch.link_with_strategy = _force_copy
sb_interfaces.link_with_strategy = _force_copy

DUMMY_FILE = pathlib.Path("pretrained_models/_dummy_custom.py")
DUMMY_FILE.parent.mkdir(parents=True, exist_ok=True)
if not DUMMY_FILE.exists():
    DUMMY_FILE.write_text("# dummy custom.py\n", encoding="utf-8")

_original_fetch_fetching = sb_fetch.fetch
_original_fetch_interfaces = sb_interfaces.fetch

def _expected_name_key(func):
    try:
        names = func.__code__.co_varnames
        return "filename" if "filename" in names else "save_filename"
    except Exception:
        return "save_filename"

def _wrap_fetch(original_func):
    key = _expected_name_key(original_func)
    alt_key = "save_filename" if key == "filename" else "filename"
    def wrapper(*args, **kwargs):
        name = kwargs.get(key, kwargs.get(alt_key, None))
        if name is None:
            return DUMMY_FILE
        kwargs[key] = name
        kwargs.pop(alt_key, None)
        return original_func(*args, **kwargs)
    return wrapper

sb_fetch.fetch = _wrap_fetch(_original_fetch_fetching)
sb_interfaces.fetch = _wrap_fetch(_original_fetch_interfaces)

# ==================== إعدادات عامة ====================
MODEL_CHOICES = ["tiny", "small", "medium", "large-v3"]
_HAS_CUDA = torch.cuda.is_available()
DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "large-v3" if _HAS_CUDA else "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cuda" if _HAS_CUDA else "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE", "float16" if DEVICE == "cuda" else "int8_float32")
_MODEL_CACHE = {}

ROOT = pathlib.Path(".")
SPK_DIR = ROOT / "voices"; SPK_DIR.mkdir(exist_ok=True)
OUT_DIR = ROOT / "outputs"; OUT_DIR.mkdir(exist_ok=True)
REC_DIR = OUT_DIR / "recordings"; REC_DIR.mkdir(parents=True, exist_ok=True)

_SPKRECOG = None
_ENROLLED = {}   # {name: np.ndarray(192,)}

# ديازة
DIAR_WIN = 1.5   # ثوانٍ
DIAR_HOP = 0.75  # ثوانٍ
AUTO_K_MAX = 5
AUTO_K_MIN = 1

# تلخيص
_SUMM_CACHE = {"pipe": None, "device": None}
ENABLE_OLLAMA = os.getenv("ENABLE_OLLAMA_SUMMARY", "1") not in ("0","false","False")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "240"))
# كلمات حشو عربية شائعة
FILLERS = {"اي","ايه","طيب","مم","اها","يعني","هيك","اممم","تمام","اوك","مزبوط","طيب؟","اي؟"}
_STAMP_RE = re.compile(r"\[\s*\d+(?:\.\d+)?\s*→\s*\d+(?:\.\d+)?\s*\]")
_SPEAKER_RE = re.compile(r"\(متكلم\s+\d+\)")
_MULTI_SPACE = re.compile(r"\s+")
_AR_SPLIT = re.compile(r'[\.!\?؟\n]+')
_AR_TOKEN = r'(?u)(?<!\w)(?:[\u0600-\u06FF]{2,}|[A-Za-z]{3,})'
_AR_SENT_SPLIT = re.compile(r'[\.!\?؟\n]+')
_AR_STOP = {"في","على","عن","من","إلى","أن","إن","كان","كانت","هذا","هذه","ذلك","تلك","لقد","قد","تم","هو","هي","هم","هناك","كما","أو","و","ثم","أيضا","مع","بين","بعد","قبل","غير","حتى","كل","أي","وقد"}

def _top_terms(keywords:str, k:int=3):
    toks = [t.strip() for t in (keywords or "").split(",") if t.strip()]
    out = []
    for t in toks:
        if t in _AR_STOP: 
            continue
        out.append(t)
        if len(out) >= k: 
            break
    return out

def _structured_summary(body:str, base_summary:str, keywords:str)->str:
    """3 جمل عامة غير متحيّزة: فكرة رئيسية + محاور بارزة + خاتمة موجزة."""
    body = (body or "").strip()
    base = (base_summary or "").strip()
    sents_base = [s.strip() for s in _AR_SENT_SPLIT.split(base) if s.strip()]
    sents_body = [s.strip() for s in _AR_SENT_SPLIT.split(body) if s.strip()]
    # 1) الفكرة الرئيسية
    s1 = sents_base[0] if sents_base else (sents_body[0] if sents_body else "النص يعالج موضوعًا محددًا.")
    # 2) المحاور
    topk = _top_terms(keywords, k=3)
    if topk:
        s2 = "أبرز المحاور: " + "، ".join(topk) + "."
    else:
        s2 = "يركّز النص على نقاط أساسية متعدّدة."
    # 3) الخاتمة من آخر جملة مفيدة
    tail = (sents_base[-1] if len(sents_base) > 1 else (sents_body[-1] if len(sents_body) > 1 else "")).strip()
    s3 = tail if len(tail) > 10 else "الخلاصة موجزة وتركّز على النتائج أو التوصيات المذكورة."
    return f"{s1} {s2} {s3}"

# ==================== Whisper / SpeechBrain ====================
def get_model(name: str, device: str = None, compute_type: str = None):
    dev = (device or DEVICE).lower()
    ctp = (compute_type or COMPUTE_TYPE).lower()
    if dev != "cuda" and ctp == "float16":
        ctp = "int8_float32"
    key = (name, dev, ctp)
    if key not in _MODEL_CACHE:
        local_dir = pathlib.Path("models") / f"whisper-{name}"
        if not local_dir.exists():
            snapshot_download(repo_id=f"Systran/faster-whisper-{name}", local_dir=local_dir.as_posix())
        _MODEL_CACHE[key] = WhisperModel(local_dir.as_posix(), device=dev, compute_type=ctp)
    return _MODEL_CACHE[key]

def get_spkrec():
    """ECAPA محمّل محليًا بدون symlink وبدون custom.py."""
    global _SPKRECOG
    if _SPKRECOG is None:
        local_dir = "pretrained_models/spkrec_ecapa_cpu"
        snapshot_download(repo_id="speechbrain/spkrec-ecapa-voxceleb", local_dir=local_dir)
        _SPKRECOG = SpeakerRecognition.from_hparams(
            source=local_dir,
            savedir=local_dir,
            run_opts={"device": "cpu"},
            hparams_file="hyperparams.yaml",
            pymodule_file=None,
        )
    return _SPKRECOG

def _is_container(p: str) -> bool:
    return pathlib.Path(p).suffix.lower() in {".mp4",".m4a",".mov",".3gp",".mkv",".webm",".avi"}

def _ffmpeg_extract(src: str, dst_wav: str, target_sr=16000):
    cmd = ["ffmpeg","-y","-i",src,"-ac","1","-ar",str(target_sr),"-vn","-acodec","pcm_s16le",dst_wav]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def _wav_read_mono(path, target_sr=16000):
    y, sr = sf.read(path, dtype="float32", always_2d=False)
    if isinstance(y, np.ndarray) and y.ndim > 1:
        y = y.mean(axis=1)
    if sr != target_sr:
        y = resampy.resample(y, sr, target_sr); sr = target_sr
    return y.astype(np.float32, copy=False), sr

def to_wav16k(path, target_sr=16000):
    if _is_container(path):
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        _ffmpeg_extract(path, tmp, target_sr)
        return tmp
    y, sr = _wav_read_mono(path, target_sr)
    y = np.clip(y, -1.0, 1.0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    sf.write(tmp, (y*32767).astype(np.int16), target_sr, subtype="PCM_16")
    return tmp

# -------- تحسين الصوت --------
def noisereduce(y, sr, strong=False):
    return nr.reduce_noise(y=y, sr=sr, prop_decrease=0.9 if strong else 0.6, stationary=False)

def enhance_audio(y, sr, strong=False, gain_db=6.0):
    y = librosa.effects.preemphasis(y, coef=0.85)
    y = noisereduce(y, sr, strong=strong)
    rms = float(np.sqrt(np.mean(y**2) + 1e-9)); target_rms = 0.07
    if rms > 0:
        y *= (target_rms / rms)
    y = np.clip(y * (10 ** (gain_db/20.0)), -1.0, 1.0)
    return y.astype(np.float32, copy=False)

def to_wav16k_enhanced(path, enhance=False, whisper_mode="normal", target_sr=16000):
    wav = to_wav16k(path, target_sr)
    if not enhance:
        return wav
    y, sr = _wav_read_mono(wav, target_sr)
    strong = (whisper_mode == "whisper")
    y = enhance_audio(y, sr, strong=strong, gain_db=6.0 if strong else 4.0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    sf.write(tmp, (y*32767).astype(np.int16), sr, subtype="PCM_16")
    return tmp

# -------- Whisper --------
def run_asr(wav_path, model_obj, whisper_mode="normal"):
    segments, info = model_obj.transcribe(
        wav_path,
        language="ar",
        task="transcribe",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=150 if whisper_mode=="whisper" else 250),
        # فك ترميز أكثر صرامة لتفادي الترديد
        condition_on_previous_text=False,
        temperature=[0.0, 0.2, 0.4],
        beam_size=5,
        best_of=5,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-0.3,
        no_speech_threshold=0.6 if whisper_mode=="whisper" else 0.55,
    )
    seglist = [s for s in segments]
    lines = [f"[{s.start:.2f}→{s.end:.2f}] {s.text.strip()}" for s in seglist]
    meta = f"المدة: {getattr(info,'duration',0):.1f}s | اللغة: {info.language} | ثقة: {getattr(info,'language_probability',0):.2f}"
    return meta + "\n\n" + "\n".join(lines), seglist

# -------- Embeddings --------
def cosine(a, b):
    an = a / (np.linalg.norm(a)+1e-9)
    bn = b / (np.linalg.norm(b)+1e-9)
    return float(np.dot(an, bn))

def _to1d(emb):
    if isinstance(emb, torch.Tensor):
        emb = emb.detach().cpu().numpy()
    arr = np.asarray(emb)
    if arr.ndim == 1:
        return arr
    if arr.shape[-1] == 192:
        return arr.reshape(-1, 192).mean(axis=0)
    return arr.reshape(-1)[:192]

def _embed_file(path):
    rec = get_spkrec()
    wav, sr = _wav_read_mono(path, 16000)
    t = torch.from_numpy(wav).float().unsqueeze(0)
    with torch.no_grad():
        emb = _to1d(rec.encode_batch(t))
    return emb

# ===== إدارة المتكلمين =====
def list_speakers():
    names = []
    for p in sorted(SPK_DIR.iterdir()):
        if p.is_dir() and (p / "embedding.npy").exists():
            names.append(p.name)
    return names

def load_enrolled():
    _ENROLLED.clear()
    for p in SPK_DIR.iterdir():
        if p.is_dir():
            emb = p / "embedding.npy"
            if emb.exists():
                _ENROLLED[p.name] = np.load(emb)
    return list(_ENROLLED.keys())

def get_speaker_files(name: str):
    if not name:
        return []
    d = SPK_DIR / name
    if not d.exists():
        return []
    out = []
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in (".wav", ".mp3", ".m4a", ".flac"):
            out.append(f.as_posix())
    return out

def delete_speaker(name: str):
    if not name:
        return False, "اختر اسمًا."
    d = SPK_DIR / name
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    _ENROLLED.pop(name, None)
    return True, f"تم حذف {name}."

def enroll_voice(name: str, files: list):
    name = (name or "").strip()
    if not name or not files:
        return False, "أدخل اسمًا ورفَع/سجّل ملفات صوتية."
    user_dir = SPK_DIR / name
    if user_dir.exists():
        shutil.rmtree(user_dir)
    user_dir.mkdir(parents=True, exist_ok=True)
    embs = []
    copied = 0
    for f in files:
        fpath = f["name"] if isinstance(f, dict) and "name" in f else (f.name if hasattr(f, "name") else f)
        if not fpath or not os.path.exists(fpath):
            continue
        dst = user_dir / pathlib.Path(fpath).name
        shutil.copyfile(fpath, dst)
        embs.append(_embed_file(str(dst)))
        copied += 1
    if not embs:
        shutil.rmtree(user_dir, ignore_errors=True)
        return False, "تعذر قراءة أي ملف."
    mean_emb = np.mean(np.stack(embs, axis=0), axis=0)
    np.save(user_dir / "embedding.npy", mean_emb)
    _ENROLLED[name] = mean_emb
    return True, f"تم تسجيل {name} ({copied} ملف)."

# -------- ديازة + ربط أسماء --------
def label_speakers(wav_path, seglist, threshold=0.65):
    if not _ENROLLED:
        load_enrolled()
    y, sr = _wav_read_mono(wav_path, 16000)
    win = int(DIAR_WIN * sr); hop = int(DIAR_HOP * sr)

    frames, tcur, i = [], 0.0, 0
    while i + win <= len(y):
        frames.append((tcur, tcur + DIAR_WIN, y[i:i+win]))
        i += hop; tcur += DIAR_HOP
    if not frames:
        return ["غير معروف"] * len(seglist)

    rec = get_spkrec()
    X = []
    with torch.no_grad():
        for (_, _, chunk) in frames:
            t = torch.from_numpy(chunk).float().unsqueeze(0)
            v = _to1d(rec.encode_batch(t))
            X.append(v)
    X = np.stack(X, axis=0)

    def _cluster_with_k(k):
        model = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
        labels = model.fit_predict(X)
        score = -1.0
        if k > 1:
            try:
                score = silhouette_score(X, labels, metric="cosine")
            except Exception:
                score = -1.0
        return labels, score

    k_best = max(1, int(getattr(label_speakers, "_k", 2)))
    auto_k = bool(getattr(label_speakers, "_auto_k", True))

    if auto_k:
        labels_best, score_best = None, -1.0
        for k in range(AUTO_K_MIN, min(AUTO_K_MAX, len(X)) + 1):
            lbls, sc = _cluster_with_k(k)
            if sc > score_best:
                score_best, labels_best, k_best = sc, lbls, k
        z = labels_best
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
            labels_out.append("غير معروف")
            continue
        name = cluster_names.get(best_c)
        if name:
            labels_out.append(name)
        else:
            if best_c not in anon_map:
                anon_map[best_c] = f"متكلم {anon_counter}"; anon_counter += 1
            labels_out.append(anon_map[best_c])
    return labels_out

# ==================== تلخيص ====================
def summarize(text):
    """تغليف بسيط يستدعي المُلخص التجميلي مع التنظيف وفرض العربية."""
    s, _ = summarize_abstractive(text, device_hint=("cuda" if _HAS_CUDA else "cpu"), target_len=200)
    return s

def _clean_transcript(text: str) -> str:
    """ينظّف التفريغ من التوقيت/المتكلّم والتكرارات وكلمات الحشو."""
    t = _STAMP_RE.sub(" ", text)
    t = _SPEAKER_RE.sub(" ", t)
    # أسطر الكلام فقط إن وُجد رأس metadata
    parts = t.split("\n\n", 1)
    body = parts[1] if len(parts) > 1 else t
    # حذف كلمات الحشو المفردة والتكرارات الطويلة لكلمة واحدة
    words = body.split()
    out = []
    prev, run = None, 0
    for w in words:
        w0 = w.strip("،,.!؟").lower()
        if w0 in FILLERS:
            continue
        if w0 == prev:
            run += 1
            if run > 3:
                continue
        else:
            prev, run = w0, 1
        out.append(w)
    t = " ".join(out)
    t = _MULTI_SPACE.sub(" ", t).strip()
    return t


def summarize_extractive(text: str, max_sentences: int = 5, top_k_terms: int = 10):
    if not text or not text.strip():
        return "لا يوجد نص.", "—"
    body = _clean_transcript(text)
    sents = [s.strip() for s in _AR_SPLIT.split(body) if s.strip()]
    if not sents:
        return "تعذّر تلخيص النص.", "—"

    vec = TfidfVectorizer(token_pattern=_AR_TOKEN, ngram_range=(1,2))
    if len(sents) <= max_sentences:
        X = vec.fit_transform(sents)
        term_scores = X.sum(axis=0).A1
        vocab = vec.get_feature_names_out()
        keywords = ", ".join(vocab[term_scores.argsort()[::-1]][:top_k_terms])
        return " ".join(sents), keywords

    X = vec.fit_transform(sents)
    sent_scores = X.mean(axis=1).A1
    top_idx = sent_scores.argsort()[::-1][:max_sentences]
    top_idx.sort()
    summary = " ".join([sents[i] for i in top_idx])
    term_scores = X[top_idx].sum(axis=0).A1
    vocab = vec.get_feature_names_out()
    keywords = ", ".join(vocab[term_scores.argsort()[::-1]][:top_k_terms])
    return summary, keywords

# ==================== تلخيص عبر Ollama ====================
def _ollama_available() -> bool:
    if not ENABLE_OLLAMA:
        return False
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return r.ok
    except Exception:
        return False

def summarize_ollama(text: str, model: str = "gemma:2b-instruct", target_len: int = 220):
    if not text or not text.strip():
        return "لا يوجد نص.", "—"

    body = _clean_transcript(text)
    system = "أنت مساعد تلخيص عربي. اكتب بالعربية الفصحى فقط. جمل قصيرة. دون ترجمة أو تعليق."
    user = f"لخّص النص التالي في ≈{target_len} حرفًا:\n\n{body}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": 1536,
            "repeat_penalty": 1.6,
            "num_predict": 256,
        },
    }

    try:
        last_err = None
        for _ in range(2):  # محاولتان
            try:
                r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=OLLAMA_TIMEOUT)
                r.raise_for_status()
                out = (r.json().get("message") or {}).get("content", "").strip()
                if not out:
                    # احتياط إن رجع شكل generate
                    out = r.json().get("response", "").strip()
                if out:
                    vec = TfidfVectorizer(token_pattern=_AR_TOKEN, ngram_range=(1, 2))
                    X = vec.fit_transform([out])
                    vocab = vec.get_feature_names_out()
                    scores = X.toarray()[0]
                    keywords = ", ".join(vocab[np.argsort(scores)[::-1]][:10]) if len(vocab) else ""
                    return out, keywords
                last_err = ValueError("استجابة فارغة من Ollama")
            except requests.exceptions.ReadTimeout as e:
                last_err = e
                continue
        raise last_err or Exception("Ollama timeout")
    except Exception:
        # سقوط تلقائي على Transformers
        summ, kw = summarize_abstractive(text, target_len=200)
        return f"[Fallback] {summ}", kw

def _load_abstractive_pipe(device_hint: str = None):
    if _SUMM_CACHE["pipe"] is not None:
        return _SUMM_CACHE["pipe"]
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
    model_name = "csebuetnlp/mT5_multilingual_XLSum"
    dev = device_hint or ("cuda" if _HAS_CUDA else "cpu")
    pipe = pipeline(
        "summarization",
        model=AutoModelForSeq2SeqLM.from_pretrained(model_name),
        tokenizer=AutoTokenizer.from_pretrained(model_name),
        device=0 if (dev == "cuda") else -1,
    )
    _SUMM_CACHE["pipe"] = pipe
    _SUMM_CACHE["device"] = dev
    return pipe

def summarize_abstractive(text: str, device_hint: str = None, target_len: int = 200):
    if not text or not text.strip():
        return "لا يوجد نص.", "—"
    body = _clean_transcript(text)

    # تقطيع ذكي حسب طول الأحرف
    chunks, char_limit = [], 1800
    tokens = re.split(r'(\s+)', body)
    acc = ""
    for tk in tokens:
        if len(acc) + len(tk) > char_limit:
            if acc.strip():
                chunks.append(acc.strip())
            acc = tk
        else:
            acc += tk
    if acc.strip(): chunks.append(acc.strip())

    pipe = _load_abstractive_pipe(device_hint=device_hint)

    def _do_sum(txt, max_len):
        # فرض العربية عبر توجيه واضح
        prompt = (
            "لخّص النص العربي التالي بجمل قصيرة وواضحة وبالعربية فقط.\n\n"
            f"النص:\n{txt}\n"
        )
        out = pipe(
            prompt,
            max_length=max_len,
            min_length=max(40, max_len // 3),
            no_repeat_ngram_size=3,
            num_beams=4,
            repetition_penalty=1.7,
            length_penalty=1.0,
            early_stopping=True,
        )[0]["summary_text"]
        return out.strip()

    if len(chunks) == 1:
        summary = _do_sum(chunks[0], target_len)
    else:
        partials = [_do_sum(ch, target_len // 2) for ch in chunks]
        summary = _do_sum(" ".join(partials), target_len)

    vec = TfidfVectorizer(token_pattern=_AR_TOKEN, ngram_range=(1,2))
    X = vec.fit_transform([summary])
    vocab = vec.get_feature_names_out()
    scores = X.toarray()[0]
    keywords = ", ".join(vocab[np.argsort(scores)[::-1]][:10])

    return summary, keywords

def smart_summarize(text: str, mode: str = "fast", device_hint: str = None, engine: str = "transformers", ollama_model: str = "phi"):
    mode = (mode or "best").lower()
    engine = (engine or "transformers").lower()
    if mode == "off" or engine == "off":
        return "", ""
    if engine == "ollama" and _ollama_available():
        try:
            return summarize_ollama(text, model=ollama_model, target_len=220)
        except Exception:
            pass  # سنسقط إلى المسار التقليدي عند الفشل
    if mode == "fast":
        summary, keywords = summarize_extractive(text, max_sentences=5, top_k_terms=10)
    else:
        try:
            summary, keywords = summarize_abstractive(text, device_hint=device_hint, target_len=220)
        except Exception:
            summary, keywords = summarize_extractive(text, max_sentences=6, top_k_terms=12)

    # صياغة وصف وصفي
    if keywords:
        desc = f"النص يتحدث بشكل أساسي عن: {keywords}."
        summary = desc + "\n\n" + summary
    else:
        summary = "النص يناقش موضوعًا عامًا.\n\n" + summary

    return summary, keywords

# ==================== أدوات مساعدة ====================
def _safe_filename(p):
    base = pathlib.Path(p).stem if p else "audio"
    base = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in base)
    return base or "audio"

def _normalize_single_file_input(file_path):
    if isinstance(file_path, dict):
        file_path = file_path.get("name") or file_path.get("path")
    return file_path

def _persist_recording(file_path, prefix="recording"):
    """حفظ تسجيل الميكروفون في outputs/recordings باسم واضح."""
    if not file_path or not os.path.exists(file_path):
        return None
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe = f"{prefix}_{ts}{pathlib.Path(file_path).suffix or '.wav'}"
    dst = REC_DIR / safe
    try:
        shutil.copyfile(file_path, dst)
        return dst.as_posix()
    except Exception:
        return None

# ==================== المعالجة الرئيسية ====================
def process(file_path, model_name, enhance, whisper_mode, diarize, auto_k, max_speakers, enroll_threshold,
            device_sel, compute_sel, summary_mode, summary_engine, ollama_model, defer_sum):
    file_path = _normalize_single_file_input(file_path)
    if not file_path:
        return "الرجاء رفع/تسجيل ملف.", None, None, "", "", None
    if not os.path.exists(file_path):
        return f"لم أجد الملف: {file_path}", None, None, "", "", None

    # إذا كان من الميكروفون، احفظ نسخة في recordings
    _persist_recording(file_path, prefix="main_input")

    if (device_sel or "auto") == "auto":
        device_sel = "cuda" if _HAS_CUDA else "cpu"
    if (compute_sel or "auto") == "auto":
        compute_sel = "float16" if device_sel == "cuda" else "int8_float32"

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

    device_hint = device_sel if device_sel in ("cpu","cuda") else ("cuda" if _HAS_CUDA else "cpu")
    if defer_sum:
        summary_text, keywords, sum_path = "", "", None
    else:
        summary_text, keywords = smart_summarize(full_txt, mode=summary_mode, device_hint=device_hint,
                                                 engine=summary_engine, ollama_model=ollama_model)
        sum_path = None
        if summary_text:
            sum_path = (OUT_DIR / f"{_safe_filename(file_path)}_summary.txt").as_posix()
            with open(sum_path, "w", encoding="utf-8") as f:
                f.write(summary_text + ("\n\n# كلمات مفتاحية:\n" + keywords if keywords else ""))

    OUT_DIR.mkdir(exist_ok=True)
    out_path = (OUT_DIR / f"{_safe_filename(file_path)}_transcript.txt").as_posix()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_txt)

    return full_txt, out_path, out_path, summary_text, keywords, sum_path, full_txt, out_path, device_hint

def process_many(file_paths, model_name, enhance, whisper_mode, diarize, auto_k, max_speakers, enroll_threshold,
                 device_sel, compute_sel, summary_mode, summary_engine, ollama_model, defer_sum):
    if not file_paths:
        return "الرجاء رفع ملفات.", None, None, "", "", None

    if isinstance(file_paths, dict):
        fp = file_paths.get("name") or file_paths.get("path")
        file_paths = [fp] if fp else []
    if not isinstance(file_paths, (list, tuple)):
        file_paths = [file_paths]

    norm_paths = []
    for fp in file_paths:
        if not fp:
            continue
        if isinstance(fp, dict):
            p = fp.get("name") or fp.get("path")
            if p: norm_paths.append(p)
        else:
            norm_paths.append(str(fp))

    if not norm_paths:
        return "لم أتعرف على مسارات صالحة.", None, None, "", "", None

    if (device_sel or "auto") == "auto":
        device_sel = "cuda" if _HAS_CUDA else "cpu"
    if (compute_sel or "auto") == "auto":
        compute_sel = "float16" if device_sel == "cuda" else "int8_float32"

    all_texts = []
    summaries = []

    for fp in norm_paths:
        try:
            txt, _, _, sumtxt, _, _, _, _, _ = process(
                fp, model_name, enhance, whisper_mode, diarize, auto_k, max_speakers, enroll_threshold,
                device_sel, compute_sel, summary_mode, summary_engine, ollama_model, defer_sum
            )
            name = pathlib.Path(fp).name
            all_texts.append(f"### ملف: {name}\n{txt}\n")
            if sumtxt:
                summaries.append(f"### {name}\n{sumtxt}\n")
        except Exception as e:
            all_texts.append(f"### ملف: {fp}\nحدث خطأ أثناء المعالجة: {e}\n")

    merged_text = "\n\n".join(all_texts).strip()
    merged_sum = "\n\n".join(summaries).strip() if summaries else ""

    OUT_DIR.mkdir(exist_ok=True)
    merged_path = (OUT_DIR / "batch_transcripts.txt").as_posix()
    with open(merged_path, "w", encoding="utf-8") as f:
        f.write(merged_text)

    merged_sum_path = None
    if merged_sum:
        merged_sum_path = (OUT_DIR / "batch_summaries.txt").as_posix()
        with open(merged_sum_path, "w", encoding="utf-8") as f:
            f.write(merged_sum)

    return merged_text, merged_path, merged_path, merged_sum, "", merged_sum_path, merged_text, merged_path, ("cuda" if _HAS_CUDA else "cpu")

def summarize_later(last_text, last_path, device_hint, summary_mode, summary_engine, ollama_model):
    text = (last_text or "").strip()
    if not text and last_path and os.path.exists(last_path):
        text = open(last_path, "r", encoding="utf-8").read()
    if not text:
        return gr.update(value="لا يوجد نص لتلخيصه."), gr.update(value=""), None
    summary_text, keywords = smart_summarize(text, mode=summary_mode, device_hint=device_hint,
                                             engine=summary_engine, ollama_model=ollama_model)
    sum_path = None
    if summary_text:
        base = pathlib.Path(last_path).with_suffix("").as_posix() if last_path else (OUT_DIR / "summary").as_posix()
        sum_path = f"{base}_summary.txt"
        with open(sum_path, "w", encoding="utf-8") as f:
            f.write(summary_text + ("\n\n# كلمات مفتاحية:\n" + keywords if keywords else ""))
    return gr.update(value=summary_text), gr.update(value=keywords), sum_path

# ==================== الواجهة ====================
custom_css = """
:root { --radius: 14px; }
* { font-family: "Cairo", system-ui, -apple-system, Segoe UI, Roboto, "Noto Kufi Arabic", Arial, sans-serif; }
.gradio-container { direction: rtl; }
"""

with gr.Blocks(title="🎙️ Arabic ASR Pro (SpeechBrain)", css=custom_css) as demo:
    gr.HTML("<h1>🎙️ Arabic ASR Pro</h1><p>تفريغ عربي + تمييز متكلمين + تلخيص ذكي</p>")

    with gr.Row():
        with gr.Column(scale=5):
            gr.Markdown("#### 📥 إدخال الصوت")
            # رفع ملف أو تسجيل
            model_dd = gr.Dropdown(MODEL_CHOICES, value=DEFAULT_MODEL, label="نموذج Whisper")
            file_in = gr.File(label="رفع ملف واحد", type="filepath")
            mic_in = gr.Audio(sources=["microphone"], type="filepath", label="🎙️ تسجيل مباشر")
            multi_files = gr.Files(label="رفع عدة ملفات", type="filepath", file_count="multiple")

            gr.Markdown("#### ⚙️ الإعدادات")
            whisper_mode = gr.Radio(["normal","whisper"], value="normal", label="وضع الحساسية")
            enhance_cb = gr.Checkbox(value=True, label="تحسين الصوت")
            diarize_cb = gr.Checkbox(value=True, label="تفعيل تمييز المتكلمين")
            auto_k_cb = gr.Checkbox(value=True, label="تقدير عدد المتكلمين تلقائيًا")
            max_k_dd = gr.Dropdown([1,2,3,4,5], value=2, label="عدد المتكلمين (إن عطّلت التلقائي)")
            thr_slider = gr.Slider(0.5,0.9,0.65,0.01,label="عتبة ربط البصمة")
            device_dd = gr.Dropdown(["auto","cpu","cuda"], value=("cuda" if _HAS_CUDA else "auto"), label="الجهاز")
            compute_dd = gr.Dropdown(["auto","int8","int8_float32","float16","float32"],
                                     value=("float16" if _HAS_CUDA else "auto"), label="الدقة")

            gr.Markdown("#### 🧠 التلخيص")
            summary_engine = gr.Dropdown(["transformers","ollama","off"], value="transformers",
                                         label="محرك التلخيص")
            ollama_model_in = gr.Textbox(value="gemma:2b-instruct", label="نموذج Ollama", 
                                         info="مثال: gemma:2b-instruct أو qwen2.5:3b-instruct أو llama3.1:8b")
            summary_dd = gr.Dropdown(["fast","best","off"], value="fast",
                                     label="وضع التلخيص (Transformers)")
            defer_sum = gr.Checkbox(value=True, label="تلخيص لاحقًا لتخفيف الحمل")

            btn_file = gr.Button("🚀 حوّل الملف المرفوع")
            btn_mic  = gr.Button("🎤 حوّل التسجيل المباشر")
            multi_btn = gr.Button("🚀 حوّل عدة ملفات (مع تلخيص)")

        with gr.Column(scale=7):
            out_txt = gr.Textbox(label="الناتج (تفريغ + أسماء المتكلمين)", lines=18)
            out_file = gr.File(label="تحميل TXT", interactive=False)
            dl_btn = gr.DownloadButton(label="⬇️ تنزيل التفريغ", value=None)

            gr.Markdown("### 📌 الملخص")
            summary_box = gr.Textbox(label="ملخص موجز", lines=8)
            keywords_box = gr.Textbox(label="كلمات مفتاحية / مواضيع", lines=2)
            summary_file = gr.File(label="تحميل الملخص", interactive=False)
            dl_sum_btn = gr.DownloadButton(label="⬇️ تنزيل الملخص", value=None)
            summarize_now_btn = gr.Button("🧠 لخّص الآن", variant="secondary")
        # حالة للاحتفاظ بآخر تفريغ وملفه
    st_text = gr.State("")      # آخر نص كامل
    st_out_path = gr.State("")  # مسار نص التفريغ
    st_device = gr.State("")    # تلميح الجهاز للتلخيص        

    gr.Markdown("---\n### 👤 تسجيل بصمة صوت (Enroll)")
    with gr.Row():
        spk_name = gr.Textbox(label="اسم المتكلم", placeholder="مثال: خالد")
    with gr.Row():
        spk_files = gr.Files(label="حمّل 3–5 مقاطع قصيرة للمتكلم (WAV/MP3/MP4...)", type="filepath")
        spk_mic = gr.Audio(sources=["microphone"], type="filepath", label="🎙️ سجّل مقطع للمتكلم")
    enroll_btn = gr.Button("تسجيل/تحديث البصمة")
    enroll_out = gr.Textbox(label="نتيجة التسجيل", interactive=False)

    gr.Markdown("---\n### 🗂️ إدارة المتكلمين")
    with gr.Row():
        refresh_btn = gr.Button("📃 تحديث قائمة الأسماء")
        del_btn = gr.Button("🗑️ حذف المتكلم المحدد")
    with gr.Row():
        spk_list = gr.Dropdown(choices=[], label="الأسماء المسجّلة", value=None)
        spk_files_list = gr.Dropdown(choices=[], label="ملفات المتكلم", value=None, interactive=True)
    with gr.Row():
        spk_audio = gr.Audio(label="تشغيل عيّنة", interactive=False)

    # ===== ربط الأزرار والدوال =====
    def _enroll(name, files, mic_path):
        file_list = list(files or [])
        if mic_path:
            # احفظ تسجيل الـEnroll وضمّه
            saved = _persist_recording(mic_path, prefix=f"enroll_{_safe_filename(name) or 'speaker'}")
            file_list.append(saved or mic_path)
        ok, msg = enroll_voice(name, file_list)
        return msg

    def _refresh_names():
        names = list_speakers()
        return gr.update(choices=names, value=(names[0] if names else None))

    def _load_speaker_files(name):
        files = get_speaker_files(name)
        return gr.update(choices=files, value=(files[0] if files else None)), (files[0] if files else None)

    def _delete_selected(name):
        ok, msg = delete_speaker(name)
        names = list_speakers()
        return msg, gr.update(choices=names, value=(names[0] if names else None)), gr.update(choices=[], value=None), None

    def _play_selected(file_path):
        return file_path or None

    enroll_btn.click(_enroll, [spk_name, spk_files, spk_mic], [enroll_out])
    refresh_btn.click(_refresh_names, [], [spk_list])
    spk_list.change(_load_speaker_files, [spk_list], [spk_files_list, spk_audio])
    spk_files_list.change(_play_selected, [spk_files_list], [spk_audio])
    del_btn.click(_delete_selected, [spk_list], [enroll_out, spk_list, spk_files_list, spk_audio])

    # ملف مرفوع
    btn_file.click(
        process,
        [file_in, model_dd, enhance_cb, whisper_mode, diarize_cb, auto_k_cb, max_k_dd, thr_slider,
         device_dd, compute_dd, summary_dd, summary_engine, ollama_model_in, defer_sum],
        [out_txt, out_file, dl_btn, summary_box, keywords_box, summary_file, st_text, st_out_path, st_device]
     )
    # تسجيل ميكروفون
    btn_mic.click(
        process,
        [mic_in, model_dd, enhance_cb, whisper_mode, diarize_cb, auto_k_cb, max_k_dd, thr_slider,
         device_dd, compute_dd, summary_dd, summary_engine, ollama_model_in, defer_sum],
        [out_txt, out_file, dl_btn, summary_box, keywords_box, summary_file, st_text, st_out_path, st_device]
     )
    # دفعات + تلخيص
    multi_btn.click(
        process_many,
        [multi_files, model_dd, enhance_cb, whisper_mode, diarize_cb, auto_k_cb, max_k_dd, thr_slider,
         device_dd, compute_dd, summary_dd, summary_engine, ollama_model_in, defer_sum],
        [out_txt, out_file, dl_btn, summary_box, keywords_box, summary_file, st_text, st_out_path, st_device]
    )

    summarize_now_btn.click(
        summarize_later,
        [st_text, st_out_path, st_device, summary_dd, summary_engine, ollama_model_in],
        [summary_box, keywords_box, summary_file]
    )

        # تحديث أزرار التنزيل عند تغيّر المسارات
    def _update_dl_buttons(txt_path, sum_path):
        return gr.update(value=txt_path), gr.update(value=sum_path or None)
    out_file.change(_update_dl_buttons, [out_file, summary_file], [dl_btn, dl_sum_btn])
    summary_file.change(_update_dl_buttons, [out_file, summary_file], [dl_btn, dl_sum_btn])

if __name__ == "__main__":
    try:
        demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=False)
    except Exception as e:
        print("[INFO] Localhost غير متاح، سننشئ رابط مشاركة:", e)
        demo.launch(server_name="0.0.0.0", server_port=7860, share=True, inbrowser=False)
