# features/tts/__init__.py
"""TTS (Text-to-Speech) feature - Router re-export."""

from app.routers.tts import router

__all__ = ["router"]
