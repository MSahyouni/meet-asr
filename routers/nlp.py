# routers/nlp.py
import pathlib
import secrets
from typing import Optional

from fastapi import APIRouter, Form, Header
from fastapi.responses import JSONResponse

import nlp_core
from config import settings
from server.deps import response_error

router = APIRouter()


def _check_api_key(x_api_key: Optional[str]) -> Optional[JSONResponse]:
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return response_error(401, "unauthorized", "invalid api key")
    return None


@router.post("/ner")
async def ner_endpoint(
    text: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    body = (text or "").strip()
    if (path or "").strip():
        try:
            p = pathlib.Path(path).expanduser().resolve()
            base = settings.OUTPUTS_DIR
            if base not in p.parents and base != p.parent:
                return response_error(403, "forbidden_path", "outside outputs/")
            if not p.exists() or not p.is_file():
                return response_error(404, "file_not_found", p.as_posix())
            body = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return response_error(500, "read_failed", str(e))
    if not body:
        return response_error(400, "no_text", "nothing to analyze")
    ents = nlp_core.extract_entities(body)
    return JSONResponse({"entities": ents})
