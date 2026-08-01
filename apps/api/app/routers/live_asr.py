"""Live / pseudo-streaming ASR endpoints (web mic)."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.asr import live_session as live
from app.features.auth.deps import require_logged_in_user
from app.server.deps import check_api_key, limiter, response_error

router = APIRouter(prefix="/live", tags=["ASR Live"])
logger = logging.getLogger("api.live_asr")


def _auth(authorization: Optional[str], x_api_key: Optional[str], user_email: Optional[str] = None):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return None, auth_error
    return require_logged_in_user(user_email, authorization)


@router.post("/warmup")
@limiter.limit("10/minute")
async def live_warmup(
    request: Request,
    user_email: str = Form(""),
    device: str = Form(""),
    compute: str = Form(""),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    resolved, auth_error = _auth(authorization, x_api_key, user_email or None)
    if auth_error:
        return auth_error
    try:
        result = await asyncio.to_thread(
            live.warmup_whisper,
            device=(device or "").strip() or None,
            compute_type=(compute or "").strip() or None,
        )
        return JSONResponse({"ok": True, "user_email": resolved, **result})
    except Exception as e:
        logger.exception("live_warmup failed: %s", e)
        return response_error(500, "live_warmup_failed", str(e))


@router.post("/start")
@limiter.limit("20/minute")
async def live_start(
    request: Request,
    user_email: str = Form(""),
    whisper_mode: str = Form("normal"),
    device: str = Form(""),
    compute: str = Form(""),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    resolved, auth_error = _auth(authorization, x_api_key, user_email or None)
    if auth_error:
        return auth_error
    try:
        sess = live.create_session(
            resolved,
            whisper_mode=whisper_mode or "normal",
            device=(device or "").strip() or None,
            compute_type=(compute or "").strip() or None,
        )
        return JSONResponse(
            {
                "ok": True,
                "session_id": sess.session_id,
                "user_email": resolved,
                "ttl_sec": live.SESSION_TTL_SEC,
            }
        )
    except Exception as e:
        logger.exception("live_start failed: %s", e)
        return response_error(500, "live_start_failed", str(e))


@router.post("/chunk")
@limiter.limit("60/minute")
async def live_chunk(
    request: Request,
    session_id: str = Form(...),
    user_email: str = Form(""),
    audio: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    resolved, auth_error = _auth(authorization, x_api_key, user_email or None)
    if auth_error:
        return auth_error
    sess = live.get_session(session_id)
    if not sess:
        return response_error(404, "session_not_found", "live session expired or missing")
    try:
        live.assert_session_owner(sess, resolved)
    except PermissionError as e:
        return response_error(403, "forbidden", str(e))

    try:
        raw = await audio.read()
        if not raw:
            return response_error(400, "validation_error", "empty audio chunk")
        # Soft size cap ~15MB for cumulative webm
        if len(raw) > 15 * 1024 * 1024:
            return response_error(413, "file_too_large", "live chunk too large")
        result = await asyncio.to_thread(
            live.ingest_cumulative_audio,
            sess,
            raw,
            audio.filename or "chunk.webm",
        )
        return JSONResponse({"ok": True, **result})
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        logger.exception("live_chunk failed: %s", e)
        return response_error(500, "live_chunk_failed", str(e))


@router.post("/finalize")
@limiter.limit("20/minute")
async def live_finalize(
    request: Request,
    session_id: str = Form(...),
    user_email: str = Form(""),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    resolved, auth_error = _auth(authorization, x_api_key, user_email or None)
    if auth_error:
        return auth_error
    sess = live.get_session(session_id)
    if not sess:
        return response_error(404, "session_not_found", "live session expired or missing")
    try:
        live.assert_session_owner(sess, resolved)
        result = await asyncio.to_thread(live.finalize_session, sess)
        return JSONResponse({"ok": True, **result})
    except PermissionError as e:
        return response_error(403, "forbidden", str(e))
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        logger.exception("live_finalize failed: %s", e)
        return response_error(500, "live_finalize_failed", str(e))


@router.post("/save-audio")
@limiter.limit("20/minute")
async def live_save_audio(
    request: Request,
    session_id: str = Form(...),
    user_email: str = Form(""),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    resolved, auth_error = _auth(authorization, x_api_key, user_email or None)
    if auth_error:
        return auth_error
    sess = live.get_session(session_id)
    if not sess:
        return response_error(404, "session_not_found", "live session expired or missing")
    try:
        live.assert_session_owner(sess, resolved)
        if not sess.user_email:
            sess.user_email = resolved
        result = live.save_session_audio(sess)
        # Quote path for download URL safety
        if result.get("wav_path"):
            result["download_url"] = f"/download?path={quote(result['wav_path'])}"
        return JSONResponse({"ok": True, **result})
    except PermissionError as e:
        return response_error(403, "forbidden", str(e))
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        logger.exception("live_save_audio failed: %s", e)
        return response_error(500, "live_save_failed", str(e))


@router.delete("/session")
@limiter.limit("30/minute")
async def live_delete_session(
    request: Request,
    session_id: str = Query(...),
    user_email: str = Query(""),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    resolved, auth_error = _auth(authorization, x_api_key, user_email or None)
    if auth_error:
        return auth_error
    sess = live.get_session(session_id)
    if sess:
        try:
            live.assert_session_owner(sess, resolved)
        except PermissionError as e:
            return response_error(403, "forbidden", str(e))
    deleted = live.delete_session(session_id)
    return JSONResponse({"ok": True, "deleted": deleted, "session_id": session_id})
