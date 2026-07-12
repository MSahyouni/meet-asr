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
        from app.features.auth.security import ensure_jwt_secret_at_startup

        ensure_jwt_secret_at_startup()
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning("JWT secret startup check failed unexpectedly: %s", e)
    try:
        from app.server.jobs import reload_jobs_from_disk, schedule_resumed_jobs
        from app.server.deps import get_core

        stats = reload_jobs_from_disk()
        resumed = schedule_resumed_jobs(stats.get("pending") or [], get_core)
        logger.info(
            "Job store restored from disk (restored=%s interrupted=%s resumed=%s)",
            stats.get("restored"),
            stats.get("interrupted"),
            resumed,
        )
    except Exception as e:
        logger.warning("Failed to reload jobs from disk: %s", e)
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
