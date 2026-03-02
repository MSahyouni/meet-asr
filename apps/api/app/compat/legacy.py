"""Backward-compatible legacy API routes.

This module preserves old endpoint paths (e.g., /transcribe, /summarize, /tts)
by re-exporting the legacy router tree from app.routers.
"""

from app.routers import router

__all__ = ["router"]
