# app_api_proxy.py - نسخة معدلة لإرسال الملفات إلى FastAPI
import gradio as gr
import requests
from pathlib import Path

# إعداد رابط السيرفر
API_URL = "http://127.0.0.1:8000/transcribe"  # استبدل بالـ IP إذا تريد الهاتف

custom_css = """
:root { --radius: 14px; }
* { font-family: "Cairo", system-ui, -apple-system, Segoe UI, Roboto, "Noto Kufi Arabic", Arial, sans-serif; }
.gradio-container { direction: rtl; }
"""

def call_api(file_path, model_name, enhance, whisper_mode, diarize, auto_k, max_speakers,
             enroll_threshold, device_sel, compute_sel, summary_mode):
    if not file_path:
        return "لم يتم اختيار ملف", None, None

    with open(file_path, "rb") as f:
        files = {"file": (Path(file_path).name, f, "audio/wav")}
        data = {
            "model_name": model_name,
            "enhance": str(enhance).lower(),
            "whisper_mode": whisper_mode,
            "diarize": str(diarize).lower(),
            "auto_k": str(auto_k).lower(),
            "max_speakers": str(max_speakers),
            "enroll_threshold": str(enroll_threshold),
            "device_sel": device_sel,
            "compute_sel": compute_sel,
            "summary_mode": summary_mode
        }
        try:
            resp = requests.post(API_URL, files=files, data=data)
            if resp.status_code == 200:
                res = resp.json()
                txt = res.get("text", "")
                summary = res.get("summary", "")
                keywords = ", ".join(res.get("keywords", []))
                return txt, summary, keywords
            else:
                return f"فشل الطلب: {resp.status_code}", None, None
        except Exception as e:
            return f"حدث خطأ: {e}", None, None

with gr.Blocks(title="🎙️ Arabic ASR Pro API Proxy", css=custom_css) as demo:
    gr.HTML("<h1>🎙️ Arabic ASR Pro API Proxy</h1><p>اختبار FastAPI عبر Gradio</p>")
    with gr.Row():
        with gr.Column(scale=5):
            model_dd = gr.Dropdown(["tiny","base","small","medium","large-v3"], value="base", label="نموذج Whisper")
            file_in = gr.File(label="ملف واحد", type="filepath")
            whisper_mode = gr.Radio(["normal","whisper"], value="normal", label="وضع الحساسية")
            enhance_cb = gr.Checkbox(value=True, label="تحسين الصوت")
            diarize_cb = gr.Checkbox(value=True, label="تفعيل الديازة")
            auto_k_cb = gr.Checkbox(value=True, label="تقدير عدد المتكلمين تلقائيًا")
            max_k_dd = gr.Dropdown([1,2,3,4,5], value=2, label="عدد المتكلمين")
            thr_slider = gr.Slider(0.5,0.9,0.65,0.01,label="عتبة ربط البصمة")
            device_dd = gr.Dropdown(["auto","cpu","cuda"], value="auto", label="الجهاز")
            compute_dd = gr.Dropdown(["auto","int8","float16","float32"], value="auto", label="الدقة")
            summary_dd = gr.Dropdown(["best","fast","off"], value="best", label="وضع التلخيص")
            btn = gr.Button("🚀 إرسال إلى API")
        with gr.Column(scale=7):
            out_txt = gr.Textbox(label="النص الكامل", lines=10)
            out_summary = gr.Textbox(label="الملخص", lines=5)
            out_keywords = gr.Textbox(label="الكلمات المفتاحية", lines=2)

    btn.click(
        call_api,
        [file_in, model_dd, enhance_cb, whisper_mode, diarize_cb, auto_k_cb, max_k_dd,
         thr_slider, device_dd, compute_dd, summary_dd],
        [out_txt, out_summary, out_keywords]
    )

if name == "main":
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)