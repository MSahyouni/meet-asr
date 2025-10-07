import os
import json
from pathlib import Path
from typing import Tuple, Optional, Any, Dict

import gradio as gr
import requests

# عنوان خادم الـ API (قابل للتعديل من الواجهة أو من متغير بيئة)
DEFAULT_API_URL = os.getenv("ASR_API_URL", "http://127.0.0.1:8000/transcribe")

CUSTOM_CSS = """
:root { --radius: 14px; }
* { font-family: "Cairo", system-ui, -apple-system, Segoe UI, Roboto, "Noto Kufi Arabic", Arial, sans-serif; }
.gradio-container { direction: rtl; }
"""

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
    whisper_mode: str,
    diarize: bool,
    auto_k: bool,
    max_speakers: int,
    enroll_threshold: float,
    device_sel: str,
    compute_sel: str,
    summary_mode: str,
    api_key: str,
) -> Tuple[str, str, str, str, str, str, Dict[str, Any]]:
    """يرسل الملف وإعداداته إلى FastAPI ويعيد:
    النص، الملخص، الكلمات المفتاحية، JSON المقاطع، مسار SRT، مسار VTT، وروابط التنزيل.
    """
    api_url = (api_url or DEFAULT_API_URL).strip()
    chosen = _pick_input_path(source, file_path, mic_path)
    if not chosen:
        return "لم يتم تحديد مدخل صالح (ملف أو تسجيل).", "", "", "", "", "", {}

    try:
        with open(chosen, "rb") as f:
            files = {"file": (Path(chosen).name, f, "application/octet-stream")}
            data: Dict[str, str] = {
                "model_name": model_name,
                "enhance": str(enhance).lower(),
                "whisper_mode": whisper_mode,
                "diarize": str(diarize).lower(),
                "auto_k": str(auto_k).lower(),
                "max_speakers": str(max_speakers),
                "enroll_threshold": str(enroll_threshold),
                "device_sel": device_sel,
                "compute_sel": compute_sel,
                "summary_mode": summary_mode,
            }

            headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
            resp = requests.post(api_url, files=files, data=data, headers=headers, timeout=300)
            if resp.status_code != 200:
                return f"فشل الطلب (HTTP {resp.status_code}): {resp.text[:300]}", "", "", "", "", "", {}

            res = resp.json()
            txt = res.get("text", "") or ""
            summary = res.get("summary", "") or ""
            keywords = _normalize_keywords(res.get("keywords"))
            segs = res.get("segments") or []
            srt = res.get("srt_path") or ""
            vtt = res.get("vtt_path") or ""
            return (
                txt,
                summary,
                _normalize_keywords(res.get("keywords")),
                json.dumps(segs, ensure_ascii=False),
                srt,
                vtt,
                (res.get("download_urls") or {})
            )

    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout).", "", "", "", "", "", {}
    except Exception as e:
        return f"حدث خطأ: {e}", "", "", "", "", "", {}


with gr.Blocks(title="🎙️ Arabic ASR Pro API Proxy", css=CUSTOM_CSS, theme=gr.themes.Soft()) as demo:
    gr.HTML("<h2>🎙️ Arabic ASR Pro API Proxy</h2><p>ارفع ملفًا أو سجّل صوتًا وأرسله إلى FastAPI</p>")

    with gr.Row():
        with gr.Column(scale=5):
            # عنوان API قابل للتعديل
            api_url_in = gr.Textbox(value=DEFAULT_API_URL, label="رابط خادم الـAPI", info="مثال: http://127.0.0.1:8000/transcribe")
            api_key_in = gr.Textbox(value="", label="X-API-Key", type="password")
            # مصدر الإدخال: ملف أو ميكروفون
            source_radio = gr.Radio(
                choices=[("رفع ملف","file"), ("🎙️ تسجيل من الميكروفون","mic")],
                value="file", label="المصدر"
            )
            file_in = gr.File(label="ملف صوتي واحد", type="filepath", visible=True)
            mic_in = gr.Audio(sources=["microphone"], type="filepath", label="🎙️ تسجيل مباشر", visible=False)

            # اختيار النموذج (بدون base)
            model_dd = gr.Dropdown(["tiny", "small", "medium", "large-v3"], value="small", label="نموذج Whisper")

            whisper_mode = gr.Radio(["normal", "whisper"], value="normal", label="وضع الحساسية")
            enhance_cb = gr.Checkbox(value=True, label="تحسين الصوت")
            diarize_cb = gr.Checkbox(value=True, label="تمييز المتكلمين (ديازة)")
            auto_k_cb = gr.Checkbox(value=True, label="تقدير عدد المتكلمين تلقائيًا")
            max_k_dd = gr.Dropdown([1, 2, 3, 4, 5], value=2, label="عدد المتكلمين (إذا عطّلت التقدير التلقائي)")
            thr_slider = gr.Slider(0.5, 0.9, 0.65, 0.01, label="عتبة ربط البصمة")

            device_dd = gr.Dropdown(["auto", "cpu", "cuda"], value="auto", label="الجهاز")
            compute_dd = gr.Dropdown(["auto", "int8", "int8_float32", "float16", "float32"], value="auto", label="الدقة")

            # أوضاع التلخيص تشمل Ollama إذا كان API يدعمه
            summary_dd = gr.Dropdown(
                ["fast", "best", "off", "lite", "medium", "heavy", "xlarge"],
                value="fast",
                label="وضع التلخيص (fast/best من Transformers، وlite..xlarge من Ollama إن كانت مفعّلة في API)"
            )

            btn = gr.Button("🚀 إرسال إلى API", variant="primary")

        with gr.Column(scale=7):
            out_txt = gr.Textbox(label="النص الكامل", lines=14, show_copy_button=True)
            out_summary = gr.Textbox(label="الملخص", lines=6, show_copy_button=True)
            out_keywords = gr.Textbox(label="الكلمات المفتاحية", lines=2, show_copy_button=True)
            segs_json = gr.Textbox(label="segments.json", lines=6, show_copy_button=True)
            srt_path = gr.Textbox(label="SRT path")
            vtt_path = gr.Textbox(label="VTT path")
            dl_urls = gr.Textbox(label="روابط التنزيل", lines=2)

    # تبديل الظهور حسب المصدر
    def _toggle_inputs(src):
        return (
            gr.update(visible=(src == "file")),
            gr.update(visible=(src == "mic")),
        )

    source_radio.change(_toggle_inputs, [source_radio], [file_in, mic_in])

    btn.click(
        call_api,
        inputs=[
            api_url_in, source_radio, file_in, mic_in,
            model_dd, enhance_cb, whisper_mode, diarize_cb, auto_k_cb,
            max_k_dd, thr_slider, device_dd, compute_dd, summary_dd,
            api_key_in
        ],
        outputs=[out_txt, out_summary, out_keywords, segs_json, srt_path, vtt_path, dl_urls],
        api_name="send_to_api"
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, inbrowser=True)
