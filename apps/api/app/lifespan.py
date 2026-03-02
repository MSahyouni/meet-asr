# app/lifespan.py — Application Lifecycle
"""Lifespan management (startup/shutdown)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    logger.info("Application starting up...")
    try:
        # ASR Core is eagerly initialized on first request/import
        from app import asr_core
        logger.info("ASR Core module loaded")
    except Exception as e:
        logger.error(f"Failed to load ASR Core: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Application shutting down...")
