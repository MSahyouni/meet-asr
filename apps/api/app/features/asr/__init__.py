# features/asr/__init__.py
"""ASR feature — transcribe, speakers, jobs, export."""

from fastapi import APIRouter

from app.routers.transcribe import router as transcribe_router
from app.routers.speakers import router as speakers_router
from app.routers.jobs import router as jobs_router
from app.routers.export import router as export_router

router = APIRouter()
router.include_router(transcribe_router, tags=["ASR"])
router.include_router(speakers_router, tags=["Speakers"])
router.include_router(jobs_router, tags=["Jobs"])
router.include_router(export_router, tags=["Export"])

__all__ = ["router"]
