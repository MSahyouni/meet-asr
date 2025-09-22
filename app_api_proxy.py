# app_api_proxy.py — واجهة Gradio ترسل الملفات إلى FastAPI
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from typing import Tuple, Optional, Any, Dict

import gradio as gr
import requests

# عنوان خادم الـ API (يمكن ضبطه من متغير بيئة)
API_URL = os.getenv("ASR_API_URL", "http://127.0.0.1:8000/transcribe")

CUSTOM_CSS = """
:root { --radius: 14px; }
* { font-family: "Cairo", system-ui, -apple-system, Segoe UI, Roboto, "Noto Kufi Arabic", Arial, sans-serif; }
.gradio-container { direction: rtl; }
"""

def _normalize_keywords(val: Any) -> str:
    """يُرجع الكلمات المفتاحية كسلسلة مفصولة بفواصل سواء وصلت كسلسلة أو قائمة."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple)):
        # تأكد أنها نصوص
        return ", ".join(map(str, val))
    return str(val)

def call_api(
    file_path: Optional[str],
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
) -> Tuple[str, Optional[str], Optional[str]]:
    """يرسل الملف وإعداداته إلى FastAPI ويعيد (النص، الملخص، الكلمات المفتاحية)."""
    if not file_path:
        return "لم يتم اختيار ملف.", None, None

    try:
        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f, "application/octet-stream")}
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

            resp = requests.post(API_URL, files=files, data=data, timeout=180)
            if resp.status_code != 200:
                return f"فشل الطلب (HTTP {resp.status_code}): {resp.text[:200]}", None, None

            res = resp.json()
            txt = res.get("text", "") or ""
            summary = res.get("summary", "") or ""
            keywords = _normalize_keywords(res.get("keywords"))
            return txt, summary, keywords

    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout).", None, None
    except Exception as e:
        return f"حدث خطأ: {e}", None, None


with gr.Blocks(title="🎙️ Arabic ASR Pro API Proxy", css=CUSTOM_CSS, theme=gr.themes.Soft()) as demo:
    gr.HTML("<h2>🎙️ Arabic ASR Pro API Proxy</h2><p>اختبار إرسال ملف صوتي إلى FastAPI</p>")
    with gr.Row():
        with gr.Column(scale=5):
            model_dd = gr.Dropdown(
                ["tiny", "base", "small", "medium", "large-v3"],
                value="base", label="نموذج Whisper"
            )
            file_in = gr.File(label="ملف صوتي واحد", type="filepath")
            whisper_mode = gr.Radio(["normal", "whisper"], value="normal", label="وضع الحساسية")
            enhance_cb = gr.Checkbox(value=True, label="تحسين الصوت")
            diarize_cb = gr.Checkbox(value=True, label="تفعيل الديازة")
            auto_k_cb = gr.Checkbox(value=True, label="تقدير عدد المتكلمين تلقائيًا")
            max_k_dd = gr.Dropdown([1, 2, 3, 4, 5], value=2, label="عدد المتكلمين")
            thr_slider = gr.Slider(0.5, 0.9, 0.65, 0.01, label="عتبة ربط البصمة")
            device_dd = gr.Dropdown(["auto", "cpu", "cuda"], value="auto", label="الجهاز")
            compute_dd = gr.Dropdown(["auto", "int8", "float16", "float32"], value="auto", label="الدقة")
            summary_dd = gr.Dropdown(["best", "fast", "off"], value="best", label="وضع التلخيص")
            btn = gr.Button("🚀 إرسال إلى API", variant="primary")
        with gr.Column(scale=7):
            out_txt = gr.Textbox(label="النص الكامل", lines=12, show_copy_button=True)
            out_summary = gr.Textbox(label="الملخص", lines=6, show_copy_button=True)
            out_keywords = gr.Textbox(label="الكلمات المفتاحية", lines=2, show_copy_button=True)

    btn.click(
        call_api,
        inputs=[
            file_in, model_dd, enhance_cb, whisper_mode, diarize_cb, auto_k_cb,
            max_k_dd, thr_slider, device_dd, compute_dd, summary_dd
        ],
        outputs=[out_txt, out_summary, out_keywords],
    )

if __name__ == "__main__":
    # غيّر 0.0.0.0 و/أو المنفذ عند الحاجة كي يعمل على الشبكة المحلية
    demo.launch(server_name="0.0.0.0", server_port=7860, inbrowser=True)