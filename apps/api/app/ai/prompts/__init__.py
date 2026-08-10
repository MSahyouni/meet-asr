# ai/prompts/__init__.py
"""Prompt management — re-exports NLP summarization prompts."""

from app.nlp.prompts import (
    build_ultra_prompt,
    normalize_prompt_mode,
)

__all__ = [
    "build_ultra_prompt",
    "normalize_prompt_mode",
]
