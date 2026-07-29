# features/__init__.py
"""
Features — public FastAPI mount surface organized by domain.

Layout:
  - `app/features/<domain>/` aggregates or owns HTTP routers for that domain
  - `app/routers/` holds ASR/NLP/TTS/health handlers (implementation)
  - Auth / Users / Billing / Dashboard live fully under `features/`

Prefer importing routers via `register_feature_routers(app)` from main so the
dual layer stays intentional rather than scattered include_router calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def register_feature_routers(app: "FastAPI") -> None:
    """Mount all canonical feature routers on the application."""
    from app.features.health import router as health_router
    from app.features.asr import router as asr_router
    from app.features.nlp import router as nlp_router
    from app.features.tts import router as tts_router
    from app.features.auth.router import router as auth_router
    from app.features.users import router as users_router
    from app.features.billing import router as billing_router
    from app.features.dashboard import router as dashboard_router
    from app.routers.export import download_txt

    app.include_router(health_router, tags=["Health"])
    # Neutral download alias (ASR/TTS/NLP outputs). Legacy: /asr/download
    app.add_api_route("/download", download_txt, methods=["GET"], tags=["Download"])
    app.include_router(asr_router, prefix="/asr", tags=["ASR"])
    app.include_router(nlp_router, prefix="/nlp", tags=["NLP"])
    app.include_router(tts_router, prefix="/tts", tags=["TTS"])
    app.include_router(auth_router, tags=["Auth"])
    app.include_router(users_router, tags=["Users"])
    app.include_router(billing_router, tags=["Billing"])
    app.include_router(dashboard_router, tags=["Dashboard"])


__all__ = ["register_feature_routers"]
