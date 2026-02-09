# app_api_proxy.py — تشغيل واجهة Gradio
import warnings

warnings.filterwarnings("ignore", message=".*torchaudio.*")
warnings.filterwarnings("ignore", message=".*deprecated.*")

from web.ui import demo

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)
