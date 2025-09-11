# app.py
import gradio as gr
from asr_core import (
    MODEL_CHOICES, DEFAULT_MODEL, process, process_many,
    _HAS_CUDA
)

custom_css = """
:root { --radius: 14px; }
* { font-family: "Cairo", system-ui, -apple-system, Segoe UI, Roboto, "Noto Kufi Arabic", Arial, sans-serif; }
.gradio-container { direction: rtl; }
"""

with gr.Blocks(title="🎙️ Arabic ASR Pro", css=custom_css) as demo:
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
        demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=False)
    except Exception as e:
        print("[INFO] Localhost غير متاح، سننشئ رابط مشاركة:", e)
        demo.launch(server_name="0.0.0.0", server_port=7860, share=True, inbrowser=False)
