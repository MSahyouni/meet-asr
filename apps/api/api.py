"""
api.py — Backward Compatibility Entry Point

This file serves as the uvicorn entry point for backward compatibility 
with existing docker-compose configurations and deployment scripts.

All functionality has been migrated to the professional architecture in app.main.
"""

from app.main import app

__all__ = ["app"]

