# features/health/__init__.py
"""Health check feature — detailed diagnostics from canonical router."""

from app.routers.health import router

__all__ = ["router"]
