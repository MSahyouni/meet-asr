# features/nlp/__init__.py
"""NLP (Summarization, NER) feature - Router aggregation."""

from fastapi import APIRouter
from app.routers.summarize import router as summarize_router
from app.routers.nlp import router as nlp_router

router = APIRouter()
router.include_router(summarize_router, tags=["Summarization"])
router.include_router(nlp_router, tags=["NLP"])

__all__ = ["router"]
