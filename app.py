import os, pathlib, tempfile, subprocess, shutil

os.environ["SPEECHBRAIN_LOCAL_FILE_STRATEGY"] = "copy"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

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

# خزّن النسخ الأصلية
_original_fetch_fetching = sb_fetch.fetch
_original_fetch_interfaces = sb_interfaces.fetch

# --- helper: حدّد وسيط الاسم الذي يتوقعه الأصل
def _expected_name_key(func):
    try:
        names = func.__code__.co_varnames
        if "filename" in names:
            return "filename"
        else:
            return "save_filename"
    except Exception:
        return "save_filename"

# --- ترقيع fetch: إن لم يُمرَّر اسم ملف، استخدم DUMMY_FILE
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

# سكِلرن للتعنقد
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

# ---------- إعدادات عامة ----------
MODEL_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]

_HAS_CUDA = torch.cuda.is_available()
DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "large-v3" if _HAS_CUDA else "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cuda" if _HAS_CUDA else "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE", "float16" if DEVICE == "cuda" else "int8")
_MODEL_CACHE = {}

SPK_DIR = pathlib.Path("voices")
SPK_DIR.mkdir(exist_ok=True)
_SPKRECOG = None
_ENROLLED = {}  # {name: np.ndarray(192,)}

# ديازة
DIAR_WIN = 1.5   # seconds
DIAR_HOP = 0.75  # seconds
AUTO_K_MAX = 5
AUTO_K_MIN = 1

# ---------- أدوات ----------
def get_model(name: str, device: str = None, compute_type: str = None):
    dev = (device or DEVICE).lower()
    ctp = (compute_type or COMPUTE_TYPE).lower()
    key = (name, dev, ctp)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = WhisperModel(name, device=dev, compute_type=ctp)
    return _MODEL_CACHE[key]

def get_spkrec():
    """تحميل ECAPA (SpeechBrain) محليًا بدون symlink وبدون custom.py."""
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

# ---------- تحسين الصوت ----------
def enhance_audio(y, sr, strong=False, gain_db=6.0):
    y = librosa.effects.preemphasis(y, coef=0.85)
    y = noisereduce(y, sr, strong=strong)  # wrapper بالأسفل
    rms = float(np.sqrt(np.mean(y**2) + 1e-9)); target_rms = 0.08
    if rms > 0:
        y *= (target_rms / rms)
    y = np.clip(y * (10 ** (gain_db/20.0)), -1.0, 1.0)
    return y.astype(np.float32, copy=False)

def noisereduce(y, sr, strong=False):
    return nr.reduce_noise(y=y, sr=sr, prop_decrease=0.9 if strong else 0.6, stationary=False)

def to_wav16k_enhanced(path, enhance=False, whisper_mode="normal", target_sr=16000):
    wav = to_wav16k(path, target_sr)
    if not enhance:
        return wav
    y, sr = _wav_read_mono(wav, target_sr)
    strong = (whisper_mode == "whisper")
    y = enhance_audio(y, sr, strong=strong, gain_db=8.0 if strong else 5.0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    sf.write(tmp, (y*32767).astype(np.int16), sr, subtype="PCM_16")
    return tmp

# ---------- Whisper ----------
def run_asr(wav_path, model_obj, whisper_mode="normal"):
    segments, info = model_obj.transcribe(
        wav_path, language="ar", task="transcribe",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=200 if whisper_mode=="whisper" else 300),
        beam_size=5, best_of=5, temperature=0.0, log_prob_threshold=-1.2,
        no_speech_threshold=0.25 if whisper_mode=="whisper" else 0.5,
    )
    seglist = [s for s in segments]
    lines = [f"[{s.start:.2f}→{s.end:.2f}] {s.text.strip()}" for s in seglist]
    meta = f"المدة: {getattr(info,'duration',0):.1f}s | اللغة: {info.language} | ثقة: {getattr(info,'language_probability',0):.2f}"
    return meta + "\n\n" + "\n".join(lines), seglist

# ---------- Embeddings ----------
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

def load_enrolled():
    _ENROLLED.clear()
    for p in SPK_DIR.iterdir():
        if p.is_dir():
            emb = p / "embedding.npy"
            if emb.exists():
                _ENROLLED[p.name] = np.load(emb)
    return list(_ENROLLED.keys())

def enroll_voice(name: str, files: list):
    name = (name or "").strip()
    if not name or not files:
        return False, "أدخل اسمًا ورفَع ملفات صوتية."
    user_dir = SPK_DIR / name
    if user_dir.exists():
        shutil.rmtree(user_dir)
    user_dir.mkdir(parents=True, exist_ok=True)
    embs = []
    for f in files:
        fpath = f["name"] if isinstance(f, dict) and "name" in f else (f.name if hasattr(f, "name") else f)
        dst = user_dir / pathlib.Path(fpath).name
        shutil.copyfile(fpath, dst)
        embs.append(_embed_file(str(dst)))
    mean_emb = np.mean(np.stack(embs, axis=0), axis=0)
    np.save(user_dir / "embedding.npy", mean_emb)
    _ENROLLED[name] = mean_emb
    return True, f"تم تسجيل {name} ({len(files)} ملف)."

# ---------- ديازة + ربط أسماء ----------
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

def _safe_filename(p):
    base = pathlib.Path(p).stem if p else "audio"
    base = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in base)
    return base or "audio"

def _normalize_single_file_input(file_path):
    """تطبيع قيمة ملف واحد من Gradio: string أو dict أو None."""
    if isinstance(file_path, dict):
        file_path = file_path.get("name") or file_path.get("path")
    return file_path

def process(file_path, model_name, enhance, whisper_mode, diarize, auto_k, max_speakers, enroll_threshold,
            device_sel, compute_sel):
    # تطبيع الإدخال
    file_path = _normalize_single_file_input(file_path)
    if not file_path:
        return "الرجاء رفع ملف.", None, None
    if not os.path.exists(file_path):
        return f"لم أجد الملف: {file_path}", None, None

    # تطبيع خيارات الجهاز/الدقة عند اختيار 'auto'
    if (device_sel or "auto") == "auto":
        device_sel = "cuda" if _HAS_CUDA else "cpu"
    if (compute_sel or "auto") == "auto":
        compute_sel = "float16" if device_sel == "cuda" else "int8"

    # تحويل + تحسين
    wav = to_wav16k_enhanced(file_path, enhance=enhance, whisper_mode=whisper_mode)

    # ASR
    model = get_model(model_name or DEFAULT_MODEL, device_sel, compute_sel)
    header_txt, seglist = run_asr(wav, model, whisper_mode=whisper_mode)

    # ديازة/تعيين متكلم
    if diarize:
        label_speakers._auto_k = bool(auto_k)
        label_speakers._k = int(max(1, int(max_speakers or 2)))
        spk_labels = label_speakers(wav, seglist, threshold=float(enroll_threshold or 0.65))
    else:
        spk_labels = ["غير معروف"] * len(seglist)

    # تجميع الخرج
    lines = []
    for s, who in zip(seglist, spk_labels):
        st = float(s.start); en = float(s.end)
        lines.append(f"[{st:.2f}→{en:.2f}] ({who}) {s.text.strip()}")
    full_txt = header_txt.split("\n\n", 1)[0] + "\n\n" + "\n".join(lines)

    # حفظ داخل مجلّد outputs بإسم واضح
    out_dir = pathlib.Path("outputs"); out_dir.mkdir(exist_ok=True)
    fname = f"{_safe_filename(file_path)}_transcript.txt"
    out_path = (out_dir / fname).as_posix()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_txt)

    return full_txt, out_path, out_path

def process_many(file_paths, model_name, enhance, whisper_mode, diarize, auto_k, max_speakers, enroll_threshold,
                 device_sel, compute_sel):
    """يعالج عدة ملفات ويُرجِع نصًا موحّدًا + ملف TXT موحّد للتنزيل."""
    if not file_paths:
        return "الرجاء رفع ملفات.", None, None

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
        return "لم أتعرف على مسارات صالحة.", None, None

    # تطبيع خيارات الجهاز/الدقة عند اختيار 'auto'
    if (device_sel or "auto") == "auto":
        device_sel = "cuda" if _HAS_CUDA else "cpu"
    if (compute_sel or "auto") == "auto":
        compute_sel = "float16" if device_sel == "cuda" else "int8"

    out_dir = pathlib.Path("outputs"); out_dir.mkdir(exist_ok=True)
    all_texts = []

    for fp in norm_paths:
        try:
            txt, _, _ = process(
                fp, model_name, enhance, whisper_mode, diarize, auto_k, max_speakers, enroll_threshold,
                device_sel, compute_sel
            )
            name = pathlib.Path(fp).name
            all_texts.append(f"### ملف: {name}\n{txt}\n")
        except Exception as e:
            all_texts.append(f"### ملف: {fp}\nحدث خطأ أثناء المعالجة: {e}\n")

    merged_text = "\n\n".join(all_texts).strip()
    merged_path = (out_dir / "batch_transcripts.txt").as_posix()
    with open(merged_path, "w", encoding="utf-8") as f:
        f.write(merged_text)

    return merged_text, merged_path, merged_path

# ============ الواجهة ============

custom_css = """
:root { --radius: 14px; }
* { font-family: "Cairo", system-ui, -apple-system, Segoe UI, Roboto, "Noto Kufi Arabic", Arial, sans-serif; }
.gradio-container { direction: rtl; }
"""

with gr.Blocks(title="🎙️ Arabic ASR Pro (SpeechBrain)", css=custom_css) as demo:
    with gr.Row():
        with gr.Column():
            gr.HTML("<h1>🎙️ Arabic ASR Pro</h1><p>تحويل صوت/فيديو إلى نص عربي + تمييز المتكلم</p>")

    with gr.Row():
        with gr.Column(scale=5):
            model_dd = gr.Dropdown(MODEL_CHOICES, value=DEFAULT_MODEL, label="نموذج Whisper")
            file_in = gr.File(label="ملف واحد", type="filepath")
            multi_files = gr.Files(label="عدة ملفات", type="filepath", file_count="multiple")
            whisper_mode = gr.Radio(["normal","whisper"], value="normal", label="وضع الحساسية")
            enhance_cb = gr.Checkbox(value=True, label="تحسين الصوت")
            diarize_cb = gr.Checkbox(value=True, label="تفعيل الديازة")
            auto_k_cb = gr.Checkbox(value=True, label="تقدير عدد المتكلمين تلقائيًا")
            max_k_dd = gr.Dropdown([1,2,3,4,5], value=2, label="عدد المتكلمين")
            thr_slider = gr.Slider(0.5,0.9,0.65,0.01,label="عتبة ربط البصمة")
            device_dd = gr.Dropdown(["auto","cpu","cuda"], value=("cuda" if _HAS_CUDA else "auto"), label="الجهاز")
            compute_dd = gr.Dropdown(["auto","int8","float16","float32"], value=("float16" if _HAS_CUDA else "auto"), label="الدقة")
            btn = gr.Button("🚀 حوّل ملف واحد")
            multi_btn = gr.Button("🚀 حوّل عدة ملفات")

        with gr.Column(scale=7):
            out_txt = gr.Textbox(label="الناتج", lines=20)
            out_file = gr.File(label="تحميل TXT", interactive=False)
            dl_btn = gr.DownloadButton(label="⬇️ تنزيل TXT", value=None)

    btn.click(
        process,
        [file_in, model_dd, enhance_cb, whisper_mode, diarize_cb, auto_k_cb, max_k_dd, thr_slider, device_dd, compute_dd],
        [out_txt, out_file, dl_btn]
    )
    multi_btn.click(
        process_many,
        [multi_files, model_dd, enhance_cb, whisper_mode, diarize_cb, auto_k_cb, max_k_dd, thr_slider, device_dd, compute_dd],
        [out_txt, out_file, dl_btn]
    )

if __name__ == "__main__":
    try:
        # جرّب تشغيل محلي على لوحة loopback
        demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=False)
    except Exception as e:
        print("[INFO] Localhost غير متاح، سننشئ رابط مشاركة:", e)
        demo.launch(server_name="0.0.0.0", server_port=7860, share=True, inbrowser=False)
