# server/segments.py — تحليل مقاطع النص وكتابة JSON
import re
import json
import pathlib
from typing import Optional


def parse_segments(text: str) -> list:
    segs = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("\u200f")
        m1 = re.match(
            r"^\[(\d+(?:\.\d+)?)\s*[\u2192\-\>]\s*(\d+(?:\.\d+)?)\]\s*\((.*?)\)\s*(.+)$",
            line,
        )
        if m1:
            st, en = float(m1.group(1)), float(m1.group(2))
            who, txt = m1.group(3).strip(), m1.group(4).strip()
            segs.append({"start": st, "end": en, "speaker": who, "text": txt})
            continue
        m2 = re.match(
            r"^\((.*?)\)\s*\[(\d+(?:\.\d+)?)\s*[\u2192\-\>]\s*(\d+(?:\.\d+)?)\]\s*(.+)$",
            line,
        )
        if m2:
            who = m2.group(1).strip()
            st, en = float(m2.group(2)), float(m2.group(3))
            txt = m2.group(4).strip()
            segs.append({"start": st, "end": en, "speaker": who, "text": txt})
    return segs


def write_segments_json(segments: list, base_txt_path: str) -> Optional[str]:
    try:
        if not base_txt_path:
            return None
        p = pathlib.Path(base_txt_path).with_suffix(".segments.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(segments or [], f, ensure_ascii=False)
        return p.as_posix()
    except Exception:
        return None
