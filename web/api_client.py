# web/api_client.py — استدعاءات API للواجهة
import os
import json
import time
from pathlib import Path
from typing import Tuple, Optional, Any, Dict, List

import requests

DEFAULT_API_URL = os.getenv("ASR_API_URL", "http://127.0.0.1:8000/transcribe")
DEFAULT_SUMMARY_URL = os.getenv("ASR_SUMMARY_URL", "http://127.0.0.1:8000/summarize")
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "50"))
ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac", ".webm", ".aac", ".3gp", ".opus"}
DEFAULT_TIMEOUT = int(os.getenv("ASR_HTTP_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("ASR_HTTP_RETRIES", "2"))
DEFAULT_BATCH_URL = os.getenv("ASR_BATCH_URL", DEFAULT_API_URL.replace("/transcribe", "/transcribe-batch"))


def _normalize_mode(m: str) -> str:
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
    enhance_mode: str,
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
    api_url = (api_url or DEFAULT_API_URL).strip()
    chosen = _pick_input_path(source, file_path, mic_path)
    if not chosen:
        return "لم يتم تحديد مدخل صالح (ملف أو تسجيل).", "", "", "", "", "", "", ""
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
                return {"file": (Path(chosen).name, f, "application/octet-stream")}
            em = (enhance_mode or "off").strip().lower()
            if em not in ("off", "light", "full"):
                em = "off"
            data: Dict[str, str] = {
                "model_name": model_name,
                "enhance_mode": em,
                "enhance": "true" if em != "off" else "false",
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
            if (data.get("summary_mode") or "").lower() == "off":
                data.pop("summary_mode", None)
            for attempt in range(MAX_RETRIES + 1):
                try:
                    resp = requests.post(api_url, files=build_files(), data=data, headers=headers, timeout=timeout_s)
                    break
                except requests.Timeout:
                    if attempt < MAX_RETRIES:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise
            if resp.status_code != 200:
                try:
                    j = resp.json()
                    err = j.get("error") or ""
                    det = j.get("detail") or ""
                    if resp.status_code == 413:
                        det = det or "الملف أكبر من الحد المسموح."
                    if resp.status_code == 415:
                        det = det or "امتداد غير مدعوم."
                    if resp.status_code == 401:
                        det = det or "مفتاح API غير صالح."
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
                txt, summary, keywords,
                json.dumps(segs, ensure_ascii=False, indent=2),
                srt, vtt,
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
    enhance_mode: str,
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
    api_url_batch = (api_url_batch or DEFAULT_BATCH_URL).strip()
    paths = [p for p in (files_list or []) if p]
    if not paths:
        return "لم يتم اختيار ملفات.", "", "", "", "", "", "", ""
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
    em = (enhance_mode or "off").strip().lower()
    if em not in ("off", "light", "full"):
        em = "off"
    data: Dict[str, str] = {
        "model_name": model_name,
        "enhance_mode": em,
        "enhance": "true" if em != "off" else "false",
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
    file_handles = []
    try:
        for pth in paths:
            file_handles.append(open(pth, "rb"))
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
            except requests.Timeout:
                if attempt < MAX_RETRIES:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        if resp.status_code != 200:
            try:
                j = resp.json()
                msg = f"HTTP {resp.status_code}: {j.get('error') or ''} {('| ' + (j.get('detail') or '')) if j.get('detail') else ''}"
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
            txt, summary, keywords,
            json.dumps(segs, ensure_ascii=False, indent=2),
            srt, vtt,
            json.dumps(dl, ensure_ascii=False, indent=2),
            txt_path,
        )
    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout).", "", "", "", "", "", "", ""
    except Exception as e:
        return f"حدث خطأ: {e}", "", "", "", "", "", "", ""
    finally:
        for fh in file_handles:
            try:
                fh.close()
            except Exception:
                pass


def enroll_speaker_api(
    api_base_url: str,
    name: str,
    files_list: Optional[List[str]],
    mic_path: Optional[str],
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> str:
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
            file_handles.append((open(pth, "rb"), pth))
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
            except requests.Timeout:
                if attempt < MAX_RETRIES:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        if resp.status_code != 200:
            try:
                j = resp.json()
                msg = f"HTTP {resp.status_code}: {j.get('error') or ''} {('| ' + (j.get('detail') or '')) if j.get('detail') else ''}"
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
    api_url = f"{api_base_url.rstrip('/')}/enrolled-speakers"
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    try:
        resp = requests.get(api_url, headers=headers, timeout=timeout_s)
        if resp.status_code != 200:
            return []
        return resp.json().get("speakers", [])
    except Exception:
        return []


def delete_speaker_api(
    api_base_url: str,
    name: str,
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> str:
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
                msg = f"HTTP {resp.status_code}: {j.get('error') or ''} {('| ' + (j.get('detail') or '')) if j.get('detail') else ''}"
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
    if not name or not name.strip():
        return []
    api_url = f"{api_base_url.rstrip('/')}/speaker-files"
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    params = {"name": name.strip()}
    try:
        resp = requests.get(api_url, headers=headers, params=params, timeout=timeout_s)
        if resp.status_code != 200:
            return []
        return resp.json().get("files", [])
    except Exception:
        return []


def get_tts_voices_api(
    api_base_url: str,
    api_key: str = "",
    timeout_s: int = DEFAULT_TIMEOUT,
) -> List[str]:
    """Fetch list of TTS voice IDs from GET /tts/voices."""
    url = f"{api_base_url.rstrip('/')}/tts/voices"
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    try:
        r = requests.get(url, headers=headers, timeout=timeout_s)
        if r.status_code != 200:
            return []
        data = r.json()
        if isinstance(data.get("voices"), list):
            return data["voices"]
        return []
    except Exception:
        return []


def call_tts_api(
    api_base_url: str,
    text: str,
    voice: str = "af_heart",
    speed: float = 1.0,
    fmt: str = "wav",
    api_key: str = "",
    timeout_s: int = DEFAULT_TIMEOUT,
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    POST /tts. Returns (error_message, download_url_for_audio, duration_info).
    On success error_message is empty and download_url can be used in gr.Audio(value=...).
    """
    url = f"{api_base_url.rstrip('/')}/tts"
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    headers["Content-Type"] = "application/json"
    payload: Dict[str, Any] = {"text": (text or "").strip(), "voice": voice or "af_heart", "speed": float(speed), "format": fmt or "wav"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout_s)
        if r.status_code != 200:
            try:
                j = r.json()
                err = j.get("error") or ""
                det = j.get("detail") or ""
                if r.status_code == 429:
                    det = det or "تجاوز حد الطلبات. حاول لاحقاً."
                msg = f"HTTP {r.status_code}: {err} {('| ' + det) if det else ''}"
            except Exception:
                msg = f"HTTP {r.status_code}: {r.text[:200]}"
            return msg, None, None
        data = r.json()
        if not data.get("ok"):
            return data.get("error") or "tts_failed", None, None
        download_url = data.get("download_url") or None
        dur = data.get("duration_sec")
        dur_s = f" ({dur}s)" if dur is not None else ""
        return "", download_url, dur_s
    except requests.Timeout:
        return "انتهت مهلة الاتصال (Timeout).", None, None
    except Exception as e:
        return f"خطأ: {e}", None, None


def summarize_now(
    api_summary_url: str,
    txt_path_state: str,
    current_text: str,
    mode: str,
    api_key: str,
    timeout_s: int = DEFAULT_TIMEOUT,
) -> Tuple[str, str, str]:
    url = (api_summary_url or DEFAULT_SUMMARY_URL).strip()
    headers = {"X-API-Key": api_key.strip()} if api_key and api_key.strip() else {}
    data: Dict[str, str] = {"summary_mode": _normalize_mode(mode)}
    if txt_path_state:
        data["path"] = txt_path_state
    else:
        data["text"] = current_text or ""
    try:
        if (data.get("summary_mode") or "").lower() == "off":
            data.pop("summary_mode", None)
        r = requests.post(url, data=data, headers=headers, timeout=timeout_s)
        if r.status_code != 200:
            try:
                j = r.json()
                err = j.get("error") or ""
                det = j.get("detail") or ""
                if r.status_code == 413:
                    det = det or "الملف أكبر من الحد المسموح."
                if r.status_code == 401:
                    det = det or "مفتاح API غير صالح."
                msg = f"HTTP {r.status_code}: {err} {('| ' + det) if det else ''}"
            except Exception:
                msg = f"HTTP {r.status_code}: {r.text[:160]}"
            return msg, "", ""
        js = r.json()
        return js.get("summary", "") or "", js.get("keywords", "") or "", js.get("summary_path", "") or ""
    except requests.Timeout:
        return "انتهت مهلة الاتصال بالخادم (Timeout).", "", ""
    except Exception as e:
        return f"حدث خطأ: {e}", "", ""
