"""API de DocEnhancer: microservicio LOCAL de realce de imagen de documentos.
Es el PRIMER paso del flujo: recibe lo que el cliente sube, lo lleva al maximo
de legibilidad y devuelve la imagen mejorada (base64) para que el OCR/clasificador
de DocValidator lean mucho mejor.

Endpoints:
  GET  /health         -> estado del servicio
  POST /enhance        -> JSON {file_b64, filename?} -> imagen realzada base64 (lo usa Odoo)
  POST /enhance-upload -> multipart (file) -> imagen PNG realzada (pruebas manuales)
"""
from __future__ import annotations

import base64

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from . import enhance as eng

app = FastAPI(
    title="DocEnhancer",
    version="0.1.0",
    description="Servicio local de realce de imagen de documentos (offline).",
)


class EnhanceRequest(BaseModel):
    file_b64: str
    filename: str = ""
    dewarp: bool = True


@app.get("/health")
def health():
    sr = eng._get_sr()
    return {
        "status": "ok",
        "super_resolution": "dnn" if sr else "cubic",
        "pdf_support": _has_fitz(),
    }


def _has_fitz() -> bool:
    try:
        import fitz  # noqa: F401

        return True
    except Exception:
        return False


@app.post("/enhance")
def enhance_json(req: EnhanceRequest):
    """Endpoint que consume Odoo: imagen en base64 -> imagen realzada en base64."""
    try:
        data = base64.b64decode(req.file_b64)
        out, meta = eng.enhance(data, req.filename, do_dewarp=req.dewarp)
        return {
            "ok": True,
            "image_b64": base64.b64encode(out).decode(),
            "mime": "image/png",
            "meta": meta,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@app.post("/enhance-upload")
async def enhance_upload(file: UploadFile = File(...), dewarp: bool = Form(True)):
    """Endpoint comodo para pruebas: sube un archivo y descarga el PNG realzado."""
    data = await file.read()
    out, meta = eng.enhance(data, file.filename or "", do_dewarp=dewarp)
    headers = {"X-Enhance-Steps": ",".join(meta.get("steps", [])), "X-Enhance-Ms": str(meta.get("ms"))}
    return Response(content=out, media_type="image/png", headers=headers)
