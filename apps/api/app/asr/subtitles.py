# asr/subtitles.py — توليد SRT و VTT
import pathlib
from typing import List, Dict, Optional

from .common import to_ar_speaker


def _fmt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: List[Dict], base_path: str, out_path: Optional[str] = None) -> str:
    p = pathlib.Path(out_path) if out_path else pathlib.Path(base_path).with_suffix(".srt")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        rlm = "\u200F"
        for i, seg in enumerate(segments, 1):
            spk = to_ar_speaker(seg.get("speaker", ""))
            f.write(f"{i}\n{_fmt_ts(seg['start'])} --> {_fmt_ts(seg['end'])}\n{rlm}{spk}: {seg['text']}\n\n")
    return str(p)


def segments_to_vtt(segments: List[Dict], base_path: str, out_path: Optional[str] = None) -> str:
    p = pathlib.Path(out_path) if out_path else pathlib.Path(base_path).with_suffix(".vtt")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("WEBVTT\n\n")
        rlm = "\u200F"
        for seg in segments:
            st = _fmt_ts(seg["start"]).replace(",", ".")
            en = _fmt_ts(seg["end"]).replace(",", ".")
            spk = to_ar_speaker(seg.get("speaker", ""))
            f.write(f"{st} --> {en}\n{rlm}{spk}: {seg['text']}\n\n")
    return str(p)
