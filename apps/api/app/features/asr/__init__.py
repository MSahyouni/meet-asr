# features/asr/__init__.py
"""ASR (Speech-to-Text) feature - Router re-export."""

from app.routers.transcribe import router

__all__ = ["router"]
