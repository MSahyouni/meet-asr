"""Aggregated legacy router from canonical app.routers modules."""

from fastapi import APIRouter

from . import health, transcribe, summarize, nlp, speakers, export, models, jobs, tts

router = APIRouter()
router.include_router(health.router, tags=["Health"])
router.include_router(transcribe.router, tags=["ASR"])
router.include_router(summarize.router, tags=["Summarization"])
router.include_router(nlp.router, tags=["NLP"])
router.include_router(speakers.router, tags=["Speakers"])
router.include_router(export.router, tags=["Export"])
router.include_router(models.router, tags=["Models"])
router.include_router(jobs.router, tags=["Jobs"])
router.include_router(tts.router, tags=["TTS"])

__all__ = ["router"]
