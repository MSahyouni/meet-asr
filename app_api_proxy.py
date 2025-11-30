import os
import json
import warnings
from pathlib import Path
from typing import Tuple, Optional, Any, Dict, List
import gradio as gr
import requests
import time

# قمع تحذيرات pyannote.audio و torchaudio
warnings.filterwarnings("ignore", message=".*torchaudio.backend.common.AudioMetaData.*")
warnings.filterwarnings("ignore", message=".*torchaudio._backend.*")
warnings.filterwarnings("ignore", message=".*deprecated.*")

# عناوين خادم الـ API (يمكن تعديلها من الواجهة أو عبر المتغيرات)
DEFAULT_API_URL = os.getenv("ASR_API_URL", "http://127.0.0.1:8000/transcribe")
DEFAULT_SUMMARY_URL = os.getenv("ASR_SUMMARY_URL", "http://127.0.0.1:8000/summarize")
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "50"))
ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac", ".webm", ".aac", ".3gp", ".opus"}
DEFAULT_TIMEOUT = int(os.getenv("ASR_HTTP_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("ASR_HTTP_RETRIES", "2"))
DEFAULT_BATCH_URL = os.getenv("ASR_BATCH_URL", DEFAULT_API_URL.replace("/transcribe", "/transcribe-batch"))

CUSTOM_CSS = """
:root { --radius: 14px; }
* { font-family: "Cairo", system-ui, -apple-system, Segoe UI, Roboto, "Noto Kufi Arabic", Arial, sans-serif; }
.gradio-container { direction: rtl; }
"""
def _normalize_mode(m: str) -> str:
    """توافق أسماء الأوضاع: medium ⇒ lite. أبقِ غير ذلك كما هو."""
    mm = (m or "").strip().lower()
    return {"medium": "lite"}.get(mm, mm)

def _normalize_keywords(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple)):
        return ", ".join(map(str, val))
    return str(val)

def _pick_input_path(source: str, file_path: Optional[str], mic_path: Optional[str]) -> Optional[str]:
    source = (source or "file").lower()
    if source == "mic":
        return mic_path
    return file_path

def call_api(
    api_url: str,
    source: str,
    file_path: Optional[str],
    mic_path: Optional[str],
    model_name: str,
    enhance: bool,
    enhance_level: str,
    whisper_mode: str,
    diarize: bool,
    auto_k: bool,
    max_speakers: int,
    enroll_threshold: float,
    device_sel: str,
    compute_sel: str,
    summary_mode: str,
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> Tuple[str, str, str, str, str, str, str, str]:
    """يرسل الملف وإعداداته إلى FastAPI ويعيد:
    النص، الملخص، الكلمات المفتاحية، JSON المقاطع، مسار SRT، مسار VTT، روابط التنزيل (JSON)، ومسار نص التفريغ.
    """
    api_url = (api_url or DEFAULT_API_URL).strip()
    chosen = _pick_input_path(source, file_path, mic_path)
    if not chosen:
        return "لم يتم تحديد مدخل صالح (ملف أو تسجيل).", "", "", "", "", "", "", ""
    # فحص مسبق للملف من جهة العميل
    try:
        p = Path(chosen)
        if not p.exists() or not p.is_file():
            return "المسار المحدد غير صالح.", "", "", "", "", "", "", ""
        if p.suffix.lower() not in ALLOWED_EXT:
            return f"امتداد غير مدعوم: {p.suffix.lower()}", "", "", "", "", "", "", ""
        if p.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
            return f"حجم الملف يتجاوز الحد المسموح {int(MAX_UPLOAD_MB)}MB.", "", "", "", "", "", "", ""
    except Exception as e:
        return f"تعذّر فحص الملف: {e}", "", "", "", "", "", "", ""

    try:
        with open(chosen, "rb") as f:
            def build_files():
                f.seek(0)
                name = Path(chosen).name
                # أرسل حقلاً واحدًا فقط كما يتوقع الـ API
                return {"file": (name, f, "application/octet-stream")
                }
            data: Dict[str, str] = {
                "model_name": model_name,
                "enhance": str(enhance).lower(),
                "enhance_level": enhance_level,
                "whisper_mode": whisper_mode,
                "diarize": str(diarize).lower(),
                "auto_k": str(auto_k).lower(),
                "max_speakers": str(max_speakers),
                "enroll_threshold": str(enroll_threshold),
                "device_sel": device_sel,
                "compute_sel": compute_sel,
                "summary_mode": _normalize_mode(summary_mode),
            }
            headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
            # إذا كان defer_sum مفعّل، اجعل summary_mode = "off"
            # (سيتم التعامل معه في الواجهة)
            if (data.get("summary_mode") or "").lower() == "off":
                data.pop("summary_mode", None)

            last_err = None
            for attempt in range(MAX_RETRIES + 1):
                try:
                    resp = requests.post(api_url, files=build_files(), data=data, headers=headers, timeout=timeout_s)
                    break
                except requests.Timeout as e:
                    last_err = e
                    if attempt < MAX_RETRIES:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise

            if resp.status_code != 200:
                # تنسيق خطأ مختصر ومقروء
                try:
                    j = resp.json()
                    err = j.get("error") or ""
                    det = j.get("detail") or ""
                    if resp.status_code == 413: det = det or "الملف أكبر من الحد المسموح."
                    if resp.status_code == 415: det = det or "امتداد غير مدعوم."
                    if resp.status_code == 401: det = det or "مفتاح API غير صالح."
                    rid = j.get("request_id") or ""
                    rid_s = f" | rid={rid}" if rid else ""
                    msg = f"HTTP {resp.status_code}: {err} {('| ' + det) if det else ''}{rid_s}".strip()
                except Exception:
                    msg = f"HTTP {resp.status_code}: {resp.text[:160]}"
                return msg, "", "", "", "", "", "", ""

            res = resp.json()
            txt = res.get("text", "") or ""
            summary = res.get("summary", "") or ""
            keywords = _normalize_keywords(res.get("keywords"))
            segs = res.get("segments") or []
            srt = res.get("srt_path") or ""
            vtt = res.get("vtt_path") or ""
            dl = res.get("download_urls") or {}
            txt_path = res.get("txt_path") or ""

            return (
                txt,
                summary,
                keywords,
                json.dumps(segs, ensure_ascii=False, indent=2),
                srt,
                vtt,
                json.dumps(dl, ensure_ascii=False, indent=2),
                txt_path,
            )

    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout).", "", "", "", "", "", "", ""
    except Exception as e:
        return f"حدث خطأ: {e}", "", "", "", "", "", "", ""

def call_api_batch(
    api_url_batch: str,
    files_list: Optional[List[str]],
    model_name: str,
    enhance: bool,
    enhance_level: str,
    whisper_mode: str,
    diarize: bool,
    auto_k: bool,
    max_speakers: int,
    enroll_threshold: float,
    device_sel: str,
    compute_sel: str,
    summary_mode: str,
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> Tuple[str, str, str, str, str, str, str, str]:
    """يرسل عدة ملفات إلى /transcribe-batch ويعيد نفس البُنى."""
    api_url_batch = (api_url_batch or DEFAULT_BATCH_URL).strip()
    paths = [p for p in (files_list or []) if p]
    if not paths:
        return "لم يتم اختيار ملفات.", "", "", "", "", "", "", ""
    # تحقق من كل ملف
    try:
        for pth in paths:
            p = Path(pth)
            if not p.exists() or not p.is_file():
                return f"مسار غير صالح: {pth}", "", "", "", "", "", "", ""
            if p.suffix.lower() not in ALLOWED_EXT:
                return f"امتداد غير مدعوم: {p.suffix.lower()}", "", "", "", "", "", "", ""
            if p.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
                return f"حجم كبير: {p.name} يتجاوز {int(MAX_UPLOAD_MB)}MB.", "", "", "", "", "", "", ""
    except Exception as e:
        return f"تعذّر فحص الملفات: {e}", "", "", "", "", "", "", ""

    data: Dict[str, str] = {
        "model_name": model_name,
        "enhance": str(enhance).lower(),
        "enhance_level": enhance_level,
        "whisper_mode": whisper_mode,
        "diarize": str(diarize).lower(),
        "auto_k": str(auto_k).lower(),
        "max_speakers": str(max_speakers),
        "enroll_threshold": str(enroll_threshold),
        "device_sel": device_sel,
        "compute_sel": compute_sel,
        "summary_mode": _normalize_mode(summary_mode),
    }
    if (data.get("summary_mode") or "").lower() == "off":
        data.pop("summary_mode", None)
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}

    # جهّز الـ multipart
    file_handles = []
    try:
        for pth in paths:
            fh = open(pth, "rb")
            file_handles.append(fh)

        last_err = None
        def build_files():
            built = []
            for fh, pth in zip(file_handles, paths):
                fh.seek(0)
                built.append(("files", (Path(pth).name, fh, "application/octet-stream")))
            return built

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.post(api_url_batch, files=build_files(), data=data, headers=headers, timeout=timeout_s)
                break
            except requests.Timeout as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise

        if resp.status_code != 200:
            try:
                j = resp.json(); err = j.get("error") or ""; det = j.get("detail") or ""; rid = j.get("request_id") or ""
                msg = f"HTTP {resp.status_code}: {err} {('| ' + det) if det else ''}{(' | rid=' + rid) if rid else ''}".strip()
            except Exception:
                msg = f"HTTP {resp.status_code}: {resp.text[:160]}"
            return msg, "", "", "", "", "", "", ""

        res = resp.json()
        txt = res.get("text", "") or ""
        summary = res.get("summary", "") or ""
        keywords = _normalize_keywords(res.get("keywords"))
        segs = res.get("segments") or []
        srt = res.get("srt_path") or ""
        vtt = res.get("vtt_path") or ""
        dl  = res.get("download_urls") or {}
        txt_path = res.get("txt_path") or ""
        return (
            txt,
            summary,
            keywords,
            json.dumps(segs, ensure_ascii=False, indent=2),
            srt,
            vtt,
            json.dumps(dl, ensure_ascii=False, indent=2),
            txt_path,
        )
    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout).", "", "", "", "", "", "", ""
    except Exception as e:
        return f"حدث خطأ: {e}", "", "", "", "", "", "", ""
    finally:
        for fh in file_handles:
            try: fh.close()
            except Exception: pass

def enroll_speaker_api(
    api_base_url: str,
    name: str,
    files_list: Optional[List[str]],
    mic_path: Optional[str],
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> str:
    """يسجل بصمة صوت لمتكلم جديد عبر API."""
    if not name or not name.strip():
        return "الرجاء إدخال اسم المتكلم."
    
    api_url = f"{api_base_url.rstrip('/')}/enroll-speaker"
    file_paths = [p for p in (files_list or []) if p]
    if mic_path:
        file_paths.append(mic_path)
    
    if not file_paths:
        return "الرجاء رفع ملفات صوتية أو تسجيل صوت."
    
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    
    file_handles = []
    try:
        for pth in file_paths:
            if not os.path.exists(pth):
                continue
            fh = open(pth, "rb")
            file_handles.append((fh, pth))
        
        if not file_handles:
            return "لم يتم العثور على ملفات صالحة."
        
        def build_files():
            built = []
            for fh, pth in file_handles:
                fh.seek(0)
                built.append(("files", (Path(pth).name, fh, "application/octet-stream")))
            return built
        
        data = {"name": name.strip()}
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.post(api_url, files=build_files(), data=data, headers=headers, timeout=timeout_s)
                break
            except requests.Timeout as e:
                if attempt < MAX_RETRIES:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        
        if resp.status_code != 200:
            try:
                j = resp.json()
                err = j.get("error") or ""
                det = j.get("detail") or ""
                msg = f"HTTP {resp.status_code}: {err} {('| ' + det) if det else ''}".strip()
            except Exception:
                msg = f"HTTP {resp.status_code}: {resp.text[:160]}"
            return msg
        
        res = resp.json()
        success = res.get("success", False)
        message = res.get("message", "")
        return message if success else f"فشل التسجيل: {message}"
    
    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout)."
    except Exception as e:
        return f"حدث خطأ: {e}"
    finally:
        for fh, _ in file_handles:
            try:
                fh.close()
            except Exception:
                pass

def list_speakers_api(
    api_base_url: str,
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> List[str]:
    """يعيد قائمة بأسماء المتحدثين المسجلين."""
    api_url = f"{api_base_url.rstrip('/')}/enrolled-speakers"
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    
    try:
        resp = requests.get(api_url, headers=headers, timeout=timeout_s)
        if resp.status_code != 200:
            return []
        res = resp.json()
        return res.get("speakers", [])
    except Exception:
        return []

def delete_speaker_api(
    api_base_url: str,
    name: str,
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> str:
    """يحذف متحدثاً مسجلاً."""
    if not name or not name.strip():
        return "الرجاء تحديد اسم المتكلم."
    
    api_url = f"{api_base_url.rstrip('/')}/delete-speaker"
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    params = {"name": name.strip()}
    
    try:
        resp = requests.delete(api_url, headers=headers, params=params, timeout=timeout_s)
        if resp.status_code != 200:
            try:
                j = resp.json()
                err = j.get("error") or ""
                det = j.get("detail") or ""
                msg = f"HTTP {resp.status_code}: {err} {('| ' + det) if det else ''}".strip()
            except Exception:
                msg = f"HTTP {resp.status_code}: {resp.text[:160]}"
            return msg
        
        res = resp.json()
        success = res.get("success", False)
        message = res.get("message", "")
        return message if success else f"فشل الحذف: {message}"
    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout)."
    except Exception as e:
        return f"حدث خطأ: {e}"

def get_speaker_files_api(
    api_base_url: str,
    name: str,
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> List[str]:
    """يعيد قائمة بملفات متحدث مسجل."""
    if not name or not name.strip():
        return []
    
    api_url = f"{api_base_url.rstrip('/')}/speaker-files"
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    params = {"name": name.strip()}
    
    try:
        resp = requests.get(api_url, headers=headers, params=params, timeout=timeout_s)
        if resp.status_code != 200:
            return []
        res = resp.json()
        return res.get("files", [])
    except Exception:
        return []

def summarize_now(
    api_summary_url: str,
    txt_path_state: str,
    current_text: str,
    mode: str,
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> Tuple[str, str, str]:
    """ينادي /summarize سواء بتمرير path (أفضل) أو النص الحالي."""
    url = (api_summary_url or DEFAULT_SUMMARY_URL).strip()
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    data: Dict[str, str] = {"summary_mode": _normalize_mode(mode)}
    if txt_path_state:
        data["path"] = txt_path_state
    else:
        data["text"] = current_text or ""
    try:
        # لا ترسل summary_mode إذا كان "off"
        if (data.get("summary_mode") or "").lower() == "off":
            data.pop("summary_mode", None)
        r = requests.post(url, data=data, headers=headers, timeout=timeout_s)
        if r.status_code != 200:
            try:
                j = r.json()
                err = j.get("error") or ""
                det = j.get("detail") or ""
                if r.status_code == 413: det = det or "الملف أكبر من الحد المسموح."
                if r.status_code == 415: det = det or "امتداد غير مدعوم."
                if r.status_code == 401: det = det or "مفتاح API غير صالح."
                rid = j.get("request_id") or ""
                rid_s = f" | rid={rid}" if rid else ""
                msg = f"HTTP {r.status_code}: {err} {('| ' + det) if det else ''}{rid_s}".strip()
            except Exception:
                msg = f"HTTP {r.status_code}: {r.text[:160]}"
            return msg, "", ""
        js = r.json()
        return js.get("summary", "") or "", js.get("keywords", "") or "", js.get("summary_path", "") or ""
    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout).", "", ""
    except Exception as e:
        return f"حدث خطأ: {e}", "", ""

with gr.Blocks(title="🎙️ Arabic ASR Pro API Proxy", css=CUSTOM_CSS, theme=gr.themes.Soft()) as demo:
    gr.HTML("<h2>🎙️ Arabic ASR Pro API Proxy</h2><p>ارفع ملفًا أو سجّل صوتًا وأرسله إلى FastAPI</p>")

    with gr.Row():
        with gr.Column(scale=5):
            # استخدم ثوابت داخلية بدل عرض الحقول للمستخدم
            api_url_state = gr.State(DEFAULT_API_URL)
            api_summary_state = gr.State(DEFAULT_SUMMARY_URL)
            api_batch_state = gr.State(DEFAULT_BATCH_URL)
            summary_dd = gr.State("off")
            api_key_in = gr.Textbox(value="", label="X-API-Key", type="password")
            timeout_in = gr.Slider(30, 600, DEFAULT_TIMEOUT, 5, label="HTTP Timeout (sec)")
            # مصدر الإدخال: ملف أو ميكروفون
            source_radio = gr.Radio(
                choices=[("رفع ملف", "file"), ("🎙️ تسجيل من الميكروفون", "mic")],
                value="file", label="المصدر"
            )
            file_in = gr.File(label="ملف صوتي واحد", type="filepath", visible=True, file_count="single", file_types=["audio", ".m4a", ".mp4", ".webm", ".3gp"])
            mic_in = gr.Audio(sources=["microphone"], type="filepath", label="🎙️ تسجيل مباشر", visible=False)
            files_in = gr.Files(label="رفع عدة ملفات", type="filepath", file_count="multiple")

            model_dd = gr.Dropdown(["light", "heavy"], value="light",
                                   label="Whisper model",
                                   info="light = medium, heavy = large-v3")
            whisper_mode = gr.Radio(["normal", "whisper"], value="normal", label="وضع الحساسية")
            enhance_cb = gr.Checkbox(value=True, label="تحسين الصوت")
            enhance_level_dd = gr.Dropdown(
                ["light", "medium", "strong", "aggressive"],
                value="medium",
                label="مستوى تحسين الصوت",
                info="light = خفيف | medium = متوسط | strong = قوي | aggressive = قوي جداً (للملفات القديمة)"
            )
            diarize_cb = gr.Checkbox(value=True, label="تمييز المتكلمين (ديازة)")
            auto_k_cb = gr.Checkbox(value=True, label="تقدير عدد المتكلمين تلقائيًا")
            max_k_dd = gr.Dropdown([1, 2, 3, 4, 5], value=2, label="عدد المتكلمين (إذا عطّلت التقدير التلقائي)")
            thr_slider = gr.Slider(0.5, 0.9, 0.65, 0.01, label="عتبة ربط البصمة")

            device_dd = gr.Dropdown(["auto", "cpu", "cuda"], value="auto", label="الجهاز")
            compute_dd = gr.Dropdown(["auto", "int8", "float16", "float32"], value="auto", label="الدقة")

            # وضع التلخيص
            gr.Markdown("#### 🧠 التلخيص")
            later_mode = gr.Dropdown(
                ["off", "lite", "ultra"],
                value="off",
                label="وضع التلخيص",
                info="off = بدون | lite = mT5 | ultra = Jais-13B"
            )
            defer_sum_cb = gr.Checkbox(value=True, label="تلخيص لاحقًا لتخفيف الحمل", info="سيتم تعطيل التلخيص التلقائي ويمكنك التلخيص لاحقاً")
            btn = gr.Button("🚀 إرسال ملف واحد", variant="primary")
            btn_multi = gr.Button("📦 إرسال عدة ملفات", variant="secondary")
            later_btn = gr.Button("🧠 لخّص الآن", variant="secondary")

        with gr.Column(scale=7):
            out_txt = gr.Textbox(label="النص الكامل", lines=14, show_copy_button=True)
            out_summary = gr.Textbox(label="الملخص", lines=6, show_copy_button=True)
            out_keywords = gr.Textbox(label="الكلمات المفتاحية", lines=2, show_copy_button=True)
            segs_json = gr.Textbox(visible=False)
            srt_path = gr.Textbox(visible=False)
            vtt_path = gr.Textbox(visible=False)
            dl_urls = gr.Textbox(visible=False)
            dl_md = gr.Markdown(visible=True)
            sum_file_path = gr.Textbox(visible=False)

    # ===== قسم إدارة المتحدثين =====
    gr.Markdown("---\n### 👤 تسجيل بصمة صوت (Enroll)")
    with gr.Row():
        with gr.Column(scale=1):
            spk_name_in = gr.Textbox(label="اسم المتكلم", placeholder="مثال: خالد")
        with gr.Column(scale=1):
            spk_mic_in = gr.Audio(sources=["microphone"], type="filepath", label="🎙️ سجّل مقطع للمتكلم")
    with gr.Row():
        spk_files_in = gr.Files(label="حمّل 3–5 مقاطع قصيرة للمتكلم (WAV/MP3/MP4...)", type="filepath", file_count="multiple")
    enroll_btn = gr.Button("تسجيل/تحديث البصمة", variant="primary")
    enroll_out = gr.Textbox(label="نتيجة التسجيل", interactive=False, lines=2)

    gr.Markdown("---\n### 🗂️ إدارة المتكلمين")
    with gr.Row():
        refresh_spk_btn = gr.Button("📃 تحديث قائمة الأسماء", variant="secondary")
        del_spk_btn = gr.Button("🗑️ حذف المتكلم المحدد", variant="stop")
    with gr.Row():
        spk_list_dd = gr.Dropdown(choices=[], label="الأسماء المسجّلة", value=None, interactive=True)
        spk_files_list_dd = gr.Dropdown(choices=[], label="ملفات المتكلم", value=None, interactive=True)
    with gr.Row():
        spk_audio_player = gr.Audio(label="تشغيل عيّنة", interactive=False)

    # حالة لمسار نص التفريغ (ليُستخدم في التلخيص عند الطلب)
    txt_path_state = gr.State("")

    # ===== دوال المتحدثين =====
    def _enroll_speaker(name, files, mic_path, api_key, timeout):
        """تسجيل متحدث جديد."""
        files_list = list(files or []) if files else []
        base_url = DEFAULT_API_URL.replace("/transcribe", "")
        return enroll_speaker_api(base_url, name or "", files_list, mic_path, api_key or "", timeout or DEFAULT_TIMEOUT)
    
    def _refresh_speakers(api_key, timeout):
        """تحديث قائمة المتحدثين."""
        base_url = DEFAULT_API_URL.replace("/transcribe", "")
        names = list_speakers_api(base_url, api_key or "", timeout or DEFAULT_TIMEOUT)
        return gr.update(choices=names, value=(names[0] if names else None))
    
    def _load_speaker_files(name, api_key, timeout):
        """تحميل ملفات متحدث."""
        if not name:
            return gr.update(choices=[], value=None), None
        base_url = DEFAULT_API_URL.replace("/transcribe", "")
        files = get_speaker_files_api(base_url, name, api_key or "", timeout or DEFAULT_TIMEOUT)
        return gr.update(choices=files, value=(files[0] if files else None)), (files[0] if files else None)
    
    def _delete_speaker(name, api_key, timeout):
        """حذف متحدث."""
        if not name:
            return "الرجاء تحديد متحدث.", gr.update(choices=[], value=None), gr.update(choices=[], value=None), None
        base_url = DEFAULT_API_URL.replace("/transcribe", "")
        msg = delete_speaker_api(base_url, name, api_key or "", timeout or DEFAULT_TIMEOUT)
        names = list_speakers_api(base_url, api_key or "", timeout or DEFAULT_TIMEOUT)
        return msg, gr.update(choices=names, value=(names[0] if names else None)), gr.update(choices=[], value=None), None
    
    def _play_speaker_file(file_path):
        """تشغيل ملف متحدث."""
        return file_path if file_path else None

    # ===== ربط أزرار المتحدثين =====
    enroll_btn.click(
        _enroll_speaker,
        inputs=[spk_name_in, spk_files_in, spk_mic_in, api_key_in, timeout_in],
        outputs=[enroll_out]
    )
    refresh_spk_btn.click(
        _refresh_speakers,
        inputs=[api_key_in, timeout_in],
        outputs=[spk_list_dd]
    )
    spk_list_dd.change(
        _load_speaker_files,
        inputs=[spk_list_dd, api_key_in, timeout_in],
        outputs=[spk_files_list_dd, spk_audio_player]
    )
    spk_files_list_dd.change(
        _play_speaker_file,
        inputs=[spk_files_list_dd],
        outputs=[spk_audio_player]
    )
    del_spk_btn.click(
        _delete_speaker,
        inputs=[spk_list_dd, api_key_in, timeout_in],
        outputs=[enroll_out, spk_list_dd, spk_files_list_dd, spk_audio_player]
    )

    # حالة لمسار نص التفريغ (ليُستخدم في التلخيص عند الطلب)
    txt_path_state = gr.State("")

    # تبديل الظهور حسب المصدر
    def _toggle_inputs(src):
        return (
            gr.update(visible=(src == "file")),
            gr.update(visible=(src == "mic")),
        )

    source_radio.change(_toggle_inputs, [source_radio], [file_in, mic_in])

    # إرسال إلى /transcribe
    def _links_md(dl_json: str):
        try:
            d = json.loads(dl_json or "{}")
            mk = []
            if d.get("txt"):     mk.append(f"[تحميل TXT]({d['txt']})")
            if d.get("srt"):     mk.append(f"[تحميل SRT]({d['srt']})")
            if d.get("vtt"):     mk.append(f"[تحميل VTT]({d['vtt']})")
            if d.get("summary"): mk.append(f"[تحميل الملخص]({d['summary']})")
            return " | ".join(mk) if mk else ""
        except Exception:
            return ""
    
    # دالة لتحديد summary_mode بناءً على defer_sum
    def _get_summary_mode_for_api(defer_sum, later_mode):
        return "off" if defer_sum else later_mode
    
    def _call_api_with_defer(*args):
        summary_mode = _get_summary_mode_for_api(args[14], args[15])
        return call_api(
            args[0], args[1], args[2], args[3], args[4], args[5], args[6], args[7], args[8], args[9],
            args[10], args[11], args[12], args[13], summary_mode, args[16], args[17]
        )
    
    def _call_api_batch_with_defer(*args):
        summary_mode = _get_summary_mode_for_api(args[12], args[13])
        return call_api_batch(
            args[0], args[1], args[2], args[3], args[4], args[5], args[6], args[7],
            args[8], args[9], args[10], args[11], summary_mode, args[14], args[15]
        )

    btn.click(
        _call_api_with_defer,
        inputs=[
            api_url_state, source_radio, file_in, mic_in,
            model_dd, enhance_cb, enhance_level_dd, whisper_mode, diarize_cb, auto_k_cb,
            max_k_dd, thr_slider, device_dd, compute_dd, defer_sum_cb, later_mode,
            api_key_in, timeout_in
        ],
        outputs=[out_txt, out_summary, out_keywords, segs_json, srt_path, vtt_path, dl_urls, txt_path_state],
        api_name="send_to_api"
    ).then(
        _links_md, [dl_urls], [dl_md]
     )
    # إرسال عدة ملفات إلى /transcribe-batch
    btn_multi.click(
        _call_api_batch_with_defer,
        inputs=[
            api_batch_state, files_in, model_dd, enhance_cb, enhance_level_dd, whisper_mode, diarize_cb, auto_k_cb,
            max_k_dd, thr_slider, device_dd, compute_dd, defer_sum_cb, later_mode, api_key_in, timeout_in
        ],
        outputs=[out_txt, out_summary, out_keywords, segs_json, srt_path, vtt_path, dl_urls, txt_path_state],
        api_name="send_to_api_batch"
    ).then(_links_md, [dl_urls], [dl_md])

    # تلخيص لاحق عبر /summarize
    later_btn.click(
        summarize_now,
        inputs=[api_summary_state, txt_path_state, out_txt, later_mode, api_key_in, timeout_in],
        outputs=[out_summary, out_keywords, sum_file_path],
        api_name="summarize_now"
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)