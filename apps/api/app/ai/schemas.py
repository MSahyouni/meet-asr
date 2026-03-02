# ai/schemas.py — AI Request/Response Contracts
"""Pydantic schemas for AI operations."""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from enum import Enum


class ASRRequest(BaseModel):
    file_path: str = Field(..., title="Path to audio file")
    enhance: bool = Field(False, title="Enable audio enhancement")
    enhance_mode: str = Field("off", title="Enhancement mode (off/light/full)")
    language: str = Field("ar", title="Language code")


class ASRResponse(BaseModel):
    job_id: str
    text: str
    segments: List[dict] = []
    confidence: Optional[float] = None


class TTSRequest(BaseModel):
    text: str = Field(..., title="Text to synthesize")
    voice: str = Field("af_heart", title="Voice ID")
    speed: float = Field(1.0, title="Speech speed")


class TTSResponse(BaseModel):
    audio_url: str
    duration: float


class SummarizationRequest(BaseModel):
    text: str = Field(..., title="Text to summarize")
    mode: str = Field("lite", title="Summarization mode (lite/ultra)")


class SummarizationResponse(BaseModel):
    summary: str
    keywords: str
