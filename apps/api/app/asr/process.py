# asr/process.py — المسار الرئيسي: process و process_many
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
import atexit
import pathlib
import tempfile
import traceback
from typing import Optional, List, Dict

from app import nlp_core

from app.config import settings
from .common import err, safe_filename, to_ar_speaker, OUTPUTS_DIR, DEFAULT_MODEL
from .audio import to_wav16k_enhanced
from .whisper import get_model, run_asr
from .diarization import diarize_with_pyannote, map_speakers_to_segments
from . import diarization as diarization_mod
from .speakers import map_generic_to_enrolled_speakers
from .subtitles import segments_to_srt, segments_to_vtt


def _clean_utterance(t: str) -> str:
    if not t:
        return ""
    _FILLERS = {"يعني", "تمام", "طيب", "هيك", "مم", "اها", "اه", "آه", "بس"}
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"([.!؟?،,:;])\1+", r"\1", t)
    t = t.replace("?", "؟")
    t = re.sub(r"\b(\w+)(?:\s+\1){2,}\b", r"\1 \1", t)
    words = [w for w in t.split() if w.lower() not in _FILLERS]
    cleaned = " ".join(words)
    cleaned = re.sub(r"\s*([،,:;.!؟])\s*", r"\1 ", cleaned).strip()
    return cleaned


def _renumber_speakers(text: str) -> str:
    mapping: Dict[str, int] = {}
    next_id = 1

    def repl(m):
        nonlocal next_id
        old_num = m.group(1)
        if old_num not in mapping:
            mapping[old_num] = next_id
            next_id += 1
        return f"(متكلم_{mapping[old_num]:02d})"

    return re.sub(r"\(متكلم[_\s]+(\d+)\)", repl, text)


def process(
    file_path: str,
    model_name: Optional[str] = None,
    enhance: bool = False,
    enhance_mode: str = "off",
    whisper_mode: str = "normal",
    enhance_level: str = "medium",
    diarize: bool = False,
    auto_k: bool = True,
    max_speakers: int = 2,
    enroll_threshold: float = 0.65,
    device_sel: str = "auto",
    compute_sel: str = "auto",
    punctuate: bool = False,
    summary_mode: str = "best",
    job_id: Optional[str] = None,
):
    """
    Pipeline: AudioAdapter (decode/resample + optional enhance) → ASR → Diarization (optional)
    → Text PostProcess (punctuation, normalization) → Export (txt/srt/vtt).
    enhance_mode: "off" | "light" (normalize+highpass) | "full" (noise reduce+filters).
    """
    if not os.path.exists(file_path):
        return err(f"File not found: {file_path}")
    if enhance_mode not in ("off", "light", "full"):
        enhance_mode = "off"
    # Backward compat: enhance=True -> treat as full
    effective_mode = "full" if enhance else enhance_mode
    do_enhance = effective_mode != "off"
    _log = logging.getLogger("asr")
    stage_ms: Dict[str, float] = {}
    t0_total = time.perf_counter()

    try:
        t0 = time.perf_counter()
        wav = to_wav16k_enhanced(
            file_path,
            enhance=do_enhance,
            enhance_mode=effective_mode if do_enhance else "off",
            whisper_mode=whisper_mode,
            enhance_level=enhance_level,
        )
        stage_ms["decode_resample"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        model = get_model(model_name or DEFAULT_MODEL, device_sel, compute_sel)
        header_txt, whisper_segments = run_asr(wav, model, whisper_mode=whisper_mode)
        stage_ms["whisper"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        if diarize and getattr(diarization_mod, "_PYANNOTE_AVAILABLE", False):
            num_spk = max_speakers if not auto_k else 0
            speaker_turns = diarize_with_pyannote(wav, num_speakers=num_spk)
            seg_rows = map_speakers_to_segments(whisper_segments, speaker_turns)
            seg_rows = map_generic_to_enrolled_speakers(wav, seg_rows, enroll_threshold)
        else:
            seg_rows = map_speakers_to_segments(whisper_segments, [])
        stage_ms["diarization"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        if punctuate:
            try:
                for s in seg_rows:
                    s["text"] = nlp_core.restore_punct(s.get("text", ""))
            except Exception as _e:
                _log.warning("punctuation failed: %s", _e)
        stage_ms["punctuation"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        RLM = "\u200F"
        LRM = "\u200E"
        lines = []
        for s in seg_rows:
            spk = to_ar_speaker(s.get("speaker", ""))
            st = f"{LRM}{s['start']:.2f}{LRM}"
            en = f"{LRM}{s['end']:.2f}{LRM}"
            txt = _clean_utterance(s["text"])
            lines.append(
                f"{RLM}{spk}\n"
                f"{RLM}[{st} → {en}]\n"
                f"{RLM}{txt}\n"
                f"••••••••••••••••••••••••••••••••"
            )
        full_txt = header_txt + "\n\n" + "\n".join(lines)
        raw_text_for_keywords = "\n".join([s.get("text", "") for s in seg_rows])
        keywords = nlp_core.extract_keywords(raw_text_for_keywords)

        jid = job_id or str(uuid.uuid4())
        job_dir = pathlib.Path(OUTPUTS_DIR) / "asr" / jid
        job_dir.mkdir(parents=True, exist_ok=True)

        out_path = str(job_dir / "transcript.txt")
        pathlib.Path(out_path).write_text(full_txt, encoding="utf-8")

        for s in seg_rows:
            s["speaker"] = to_ar_speaker(s.get("speaker", ""))
        srt_path = segments_to_srt(seg_rows, out_path)
        vtt_path = segments_to_vtt(seg_rows, out_path)
        seg_path = str(job_dir / "segments.json")
        segments_payload = {
            "job_id": jid,
            "language": "ar",
            "options": {
                "enhance_mode": effective_mode,
                "diarization": diarize,
                "punctuation": punctuate,
                "model": model_name or DEFAULT_MODEL,
            },
            "segments": seg_rows,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(seg_path, "w", encoding="utf-8") as f:
            json.dump(segments_payload, f, ensure_ascii=False)
        stage_ms["export"] = (time.perf_counter() - t0) * 1000

        total_ms = (time.perf_counter() - t0_total) * 1000
        _log.debug("job_id=%s stage_ms=%s total_ms=%.0f", jid, stage_ms, total_ms)

        numbered_text = _renumber_speakers(full_txt)

        return {
            "text": numbered_text,
            "txt_path": out_path,
            "summary": "",
            "summary_path": None,
            "keywords": keywords,
            "segments": seg_rows,
            "srt_path": srt_path,
            "vtt_path": vtt_path,
            "segments_path": seg_path,
            "job_id": jid,
            "timings_ms": {**stage_ms, "total": total_ms},
        }
    except Exception as e:
        msg = f"Error during processing: {e}"
        logging.getLogger("asr").exception("process failed: %s", msg)
        return err(msg)


def process_many(file_paths: List[str], **kwargs):
    if not file_paths:
        return err("الرجاء رفع ملفات.")
    merge_outputs = kwargs.pop("merge_outputs", True)
    tag_sources = kwargs.pop("tag_sources", True)
    job_id = kwargs.pop("job_id", None) or str(uuid.uuid4())
    per_file_results: List[Dict] = []
    all_text_blocks: List[str] = []
    all_raw_text: List[str] = []
    all_segments: List[Dict] = []
    cumulative_offset = 0.0

    for fp in file_paths:
        res = process(fp, job_id=None, **kwargs)
        per_file_results.append(res)
        name = pathlib.Path(fp).stem
        all_text_blocks.append(f"### ملف: {name}\n{res.get('text','')}\n")
        raw_from_segments = "\n".join([s.get("text", "") for s in res.get("segments", [])])
        all_raw_text.append(raw_from_segments)
        if merge_outputs:
            segs = res.get("segments", [])
            for s in segs:
                new_seg = dict(s)
                new_seg["start"] = float(s["start"]) + cumulative_offset
                new_seg["end"] = float(s["end"]) + cumulative_offset
                if tag_sources:
                    new_seg["text"] = f"[{name}] {new_seg.get('text','')}"
                all_segments.append(new_seg)
            if segs:
                cumulative_offset += max(float(s["end"]) for s in segs)

    merged_text = "\n\n".join(all_text_blocks).strip()
    job_dir = pathlib.Path(OUTPUTS_DIR) / "asr" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    merged_txt_path = str(job_dir / "transcript.txt")
    pathlib.Path(merged_txt_path).write_text(merged_text, encoding="utf-8")
    merged_keywords = nlp_core.extract_keywords("\n".join(all_raw_text))
    merged_text = _renumber_speakers(merged_text)
    merged_srt_path = None
    merged_vtt_path = None
    merged_seg_path = str(job_dir / "segments.json")
    if merge_outputs and all_segments:
        all_segments.sort(key=lambda s: (float(s["start"]), float(s["end"])))
        merged_srt_path = segments_to_srt(all_segments, base_path="", out_path=str(job_dir / "transcript.srt"))
        merged_vtt_path = segments_to_vtt(all_segments, base_path="", out_path=str(job_dir / "transcript.vtt"))
        em = kwargs.get("enhance_mode", "off")
        segments_payload = {
            "job_id": job_id,
            "language": "ar",
            "options": {
                "enhance_mode": em,
                "diarization": kwargs.get("diarize", False),
                "punctuation": kwargs.get("punctuate", False),
                "model": kwargs.get("model_name") or DEFAULT_MODEL,
            },
            "segments": all_segments,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(merged_seg_path, "w", encoding="utf-8") as f:
            json.dump(segments_payload, f, ensure_ascii=False)
    else:
        merged_seg_path = None

    return {
        "text": merged_text,
        "txt_path": merged_txt_path,
        "summary": "",
        "summary_path": None,
        "keywords": merged_keywords,
        "segments": all_segments if merge_outputs else [],
        "srt_path": merged_srt_path,
        "vtt_path": merged_vtt_path,
        "segments_path": merged_seg_path,
        "job_id": job_id,
        "items": per_file_results,
    }


def cleanup_temp_files():
    try:
        temp_dir = pathlib.Path(tempfile.gettempdir())
        cutoff = time.time() - 86400
        for temp_file in temp_dir.glob("asr_*.wav"):
            try:
                if temp_file.stat().st_mtime < cutoff:
                    temp_file.unlink()
            except Exception:
                pass
    except Exception:
        pass


atexit.register(cleanup_temp_files)
