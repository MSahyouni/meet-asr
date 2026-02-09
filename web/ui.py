# web/ui.py — واجهة Gradio لـ Arabic ASR Pro API Proxy
import json
import warnings

import gradio as gr

from web.api_client import (
    DEFAULT_API_URL,
    DEFAULT_SUMMARY_URL,
    DEFAULT_TIMEOUT,
    DEFAULT_BATCH_URL,
    call_api,
    call_api_batch,
    enroll_speaker_api,
    list_speakers_api,
    delete_speaker_api,
    get_speaker_files_api,
    summarize_now,
    get_tts_voices_api,
    call_tts_api,
)

warnings.filterwarnings("ignore", message=".*torchaudio.*")
warnings.filterwarnings("ignore", message=".*deprecated.*")

CUSTOM_CSS = """
:root { --radius: 14px; }
* { font-family: "Cairo", system-ui, -apple-system, Segoe UI, Roboto, "Noto Kufi Arabic", Arial, sans-serif; }
.gradio-container { direction: rtl; }
"""

with gr.Blocks(title="🎙️ Arabic ASR Pro API Proxy", css=CUSTOM_CSS, theme=gr.themes.Soft()) as demo:
    gr.HTML("<h2>🎙️ Arabic ASR Pro API Proxy</h2><p>ارفع ملفًا أو سجّل صوتًا وأرسله إلى FastAPI</p>")
    with gr.Row():
        api_key_in = gr.Textbox(value="", label="X-API-Key", type="password")
        timeout_in = gr.Slider(30, 600, DEFAULT_TIMEOUT, 5, label="HTTP Timeout (sec)")
    api_url_state = gr.State(DEFAULT_API_URL)
    api_summary_state = gr.State(DEFAULT_SUMMARY_URL)
    api_batch_state = gr.State(DEFAULT_BATCH_URL)

    with gr.Tabs():
        with gr.TabItem("استماع/تحويل"):
            with gr.Row():
                with gr.Column(scale=5):
                    source_radio = gr.Radio(
                        choices=[("رفع ملف", "file"), ("🎙️ تسجيل من الميكروفون", "mic")],
                        value="file", label="المصدر"
                    )
                    file_in = gr.File(label="ملف صوتي واحد", type="filepath", visible=True, file_count="single", file_types=["audio", ".m4a", ".mp4", ".webm", ".3gp"])
                    mic_in = gr.Audio(sources=["microphone"], type="filepath", label="🎙️ تسجيل مباشر", visible=False)
                    files_in = gr.Files(label="رفع عدة ملفات", type="filepath", file_count="multiple")
                    model_dd = gr.Dropdown(["light", "heavy"], value="light", label="Whisper model", info="light = medium, heavy = large-v3")
                    whisper_mode = gr.Radio(["normal", "whisper"], value="normal", label="وضع الحساسية")
                    enhance_mode_dd = gr.Dropdown(
                        choices=[("بدون", "off"), ("خفيف (normalize + highpass)", "light"), ("كامل (noise reduce + filters)", "full")],
                        value="off",
                        label="تحسين الصوت (enhance_mode)",
                        info="off = بدون | light = سريع | full = تحسين كامل"
                    )
                    enhance_level_dd = gr.Dropdown(
                        ["light", "medium", "strong", "aggressive"], value="medium",
                        label="مستوى تحسين (للوضع full فقط)",
                        info="light = خفيف | medium = متوسط | strong = قوي | aggressive = قوي جداً"
                    )
                    diarize_cb = gr.Checkbox(value=True, label="تمييز المتكلمين (ديازة)")
                    auto_k_cb = gr.Checkbox(value=True, label="تقدير عدد المتكلمين تلقائيًا")
                    max_k_dd = gr.Dropdown([1, 2, 3, 4, 5], value=2, label="عدد المتكلمين (إذا عطّلت التقدير التلقائي)")
                    thr_slider = gr.Slider(0.5, 0.9, 0.65, 0.01, label="عتبة ربط البصمة")
                    device_dd = gr.Dropdown(["auto", "cpu", "cuda"], value="auto", label="الجهاز")
                    compute_dd = gr.Dropdown(["auto", "int8", "float16", "float32"], value="auto", label="الدقة")
                    gr.Markdown("#### 🧠 التلخيص")
                    later_mode = gr.Dropdown(
                        ["off", "lite", "ultra"], value="off",
                        label="وضع التلخيص", info="off = بدون | lite = mT5 | ultra = Jais-13B"
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
            txt_path_state = gr.State("")

        with gr.TabItem("Text → Speech (TTS)"):
            with gr.Row():
                with gr.Column(scale=1):
                    tts_text_in = gr.Textbox(label="النص", lines=8, placeholder="أدخل النص بالعربية أو الإنجليزية...", max_lines=20)
                    tts_voice_dd = gr.Dropdown(choices=["af_heart"], value="af_heart", label="الصوت")
                    tts_refresh_voices_btn = gr.Button("تحديث قائمة الأصوات", variant="secondary")
                    tts_speed_slider = gr.Slider(0.5, 2.0, 1.0, 0.1, label="السرعة")
                    tts_fmt_dd = gr.Dropdown(choices=["wav"], value="wav", label="التنسيق")
                    tts_btn = gr.Button("🔊 Synthesize", variant="primary")
                with gr.Column(scale=1):
                    tts_error_out = gr.Textbox(label="خطأ", interactive=False, visible=True)
                    tts_audio_out = gr.Audio(label="تشغيل", interactive=False, type="filepath")
                    tts_dl_md = gr.Markdown("")

    def _enroll_speaker(name, files, mic_path, api_key, timeout):
        files_list = list(files or []) if files else []
        base_url = DEFAULT_API_URL.replace("/transcribe", "")
        return enroll_speaker_api(base_url, name or "", files_list, mic_path, api_key or "", timeout or DEFAULT_TIMEOUT)

    def _refresh_speakers(api_key, timeout):
        base_url = DEFAULT_API_URL.replace("/transcribe", "")
        names = list_speakers_api(base_url, api_key or "", timeout or DEFAULT_TIMEOUT)
        return gr.update(choices=names, value=(names[0] if names else None))

    def _load_speaker_files(name, api_key, timeout):
        if not name:
            return gr.update(choices=[], value=None), None
        base_url = DEFAULT_API_URL.replace("/transcribe", "")
        files = get_speaker_files_api(base_url, name, api_key or "", timeout or DEFAULT_TIMEOUT)
        return gr.update(choices=files, value=(files[0] if files else None)), (files[0] if files else None)

    def _delete_speaker(name, api_key, timeout):
        if not name:
            return "الرجاء تحديد متحدث.", gr.update(choices=[], value=None), gr.update(choices=[], value=None), None
        base_url = DEFAULT_API_URL.replace("/transcribe", "")
        msg = delete_speaker_api(base_url, name, api_key or "", timeout or DEFAULT_TIMEOUT)
        names = list_speakers_api(base_url, api_key or "", timeout or DEFAULT_TIMEOUT)
        return msg, gr.update(choices=names, value=(names[0] if names else None)), gr.update(choices=[], value=None), None

    def _play_speaker_file(file_path):
        return file_path if file_path else None

    enroll_btn.click(_enroll_speaker, inputs=[spk_name_in, spk_files_in, spk_mic_in, api_key_in, timeout_in], outputs=[enroll_out])
    refresh_spk_btn.click(_refresh_speakers, inputs=[api_key_in, timeout_in], outputs=[spk_list_dd])
    spk_list_dd.change(_load_speaker_files, inputs=[spk_list_dd, api_key_in, timeout_in], outputs=[spk_files_list_dd, spk_audio_player])
    spk_files_list_dd.change(_play_speaker_file, inputs=[spk_files_list_dd], outputs=[spk_audio_player])
    del_spk_btn.click(_delete_speaker, inputs=[spk_list_dd, api_key_in, timeout_in], outputs=[enroll_out, spk_list_dd, spk_files_list_dd, spk_audio_player])

    def _toggle_inputs(src):
        return gr.update(visible=(src == "file")), gr.update(visible=(src == "mic"))

    source_radio.change(_toggle_inputs, [source_radio], [file_in, mic_in])

    def _links_md(dl_json: str):
        try:
            d = json.loads(dl_json or "{}")
            mk = []
            if d.get("txt"):
                mk.append(f"[تحميل TXT]({d['txt']})")
            if d.get("srt"):
                mk.append(f"[تحميل SRT]({d['srt']})")
            if d.get("vtt"):
                mk.append(f"[تحميل VTT]({d['vtt']})")
            if d.get("summary"):
                mk.append(f"[تحميل الملخص]({d['summary']})")
            return " | ".join(mk) if mk else ""
        except Exception:
            return ""

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
            model_dd, enhance_mode_dd, enhance_level_dd, whisper_mode, diarize_cb, auto_k_cb,
            max_k_dd, thr_slider, device_dd, compute_dd, defer_sum_cb, later_mode,
            api_key_in, timeout_in
        ],
        outputs=[out_txt, out_summary, out_keywords, segs_json, srt_path, vtt_path, dl_urls, txt_path_state],
        api_name="send_to_api"
    ).then(_links_md, [dl_urls], [dl_md])

    btn_multi.click(
        _call_api_batch_with_defer,
        inputs=[
            api_batch_state, files_in, model_dd, enhance_mode_dd, enhance_level_dd, whisper_mode, diarize_cb, auto_k_cb,
            max_k_dd, thr_slider, device_dd, compute_dd, defer_sum_cb, later_mode, api_key_in, timeout_in
        ],
        outputs=[out_txt, out_summary, out_keywords, segs_json, srt_path, vtt_path, dl_urls, txt_path_state],
        api_name="send_to_api_batch"
    ).then(_links_md, [dl_urls], [dl_md])

    later_btn.click(
        summarize_now,
        inputs=[api_summary_state, txt_path_state, out_txt, later_mode, api_key_in, timeout_in],
        outputs=[out_summary, out_keywords, sum_file_path],
        api_name="summarize_now"
    )

    def _fetch_tts_voices(api_url, api_key, timeout):
        base = (api_url or DEFAULT_API_URL).replace("/transcribe", "").strip()
        voices = get_tts_voices_api(base, api_key or "", timeout or DEFAULT_TIMEOUT)
        if not voices:
            return gr.update(choices=["af_heart"], value="af_heart")
        return gr.update(choices=voices, value=voices[0] if voices else "af_heart")

    def _call_tts(api_url, text, voice, speed, fmt, api_key, timeout):
        base = (api_url or DEFAULT_API_URL).replace("/transcribe", "").strip()
        err_msg, download_url, dur_s = call_tts_api(base, text or "", voice or "af_heart", float(speed or 1.0), fmt or "wav", api_key or "", timeout or DEFAULT_TIMEOUT)
        if err_msg:
            return err_msg, None, ""
        md = f"[تحميل الملف]({download_url}){dur_s}" if download_url else ""
        return "", download_url, md

    tts_refresh_voices_btn.click(
        _fetch_tts_voices,
        inputs=[api_url_state, api_key_in, timeout_in],
        outputs=[tts_voice_dd],
    )
    tts_btn.click(
        _call_tts,
        inputs=[api_url_state, tts_text_in, tts_voice_dd, tts_speed_slider, tts_fmt_dd, api_key_in, timeout_in],
        outputs=[tts_error_out, tts_audio_out, tts_dl_md],
        api_name="tts_synthesize",
    )
    demo.load(
        _fetch_tts_voices,
        inputs=[api_url_state, api_key_in, timeout_in],
        outputs=[tts_voice_dd],
    )
