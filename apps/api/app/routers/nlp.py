# routers/nlp.py
import pathlib
from typing import Optional

from fastapi import APIRouter, Form, Header
from fastapi.responses import JSONResponse

from app import nlp_core
from app.config import settings
from app.server.deps import response_error, check_api_key

router = APIRouter()


@router.post("/ner")
async def ner_endpoint(
    text: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
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
