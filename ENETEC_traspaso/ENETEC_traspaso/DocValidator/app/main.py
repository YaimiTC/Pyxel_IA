"""API del servicio DocValidator. Odoo consume POST /verify (base64).
La doc interactiva queda en http://HOST:PUERTO/docs (Swagger)."""
from __future__ import annotations

import base64

from fastapi import FastAPI, File, Form, UploadFile
from pydantic import BaseModel

from . import pipeline
from . import pyme_pipeline
from .config import get_settings

app = FastAPI(
    title="DocValidator",
    version="0.1.0",
    description="Servicio local de validacion de documentos por IA (offline).",
)


class VerifyRequest(BaseModel):
    file_b64: str
    expected_type: str
    pre_enhanced: bool = False
    ocr_b64: str = ""  # imagen realzada (DocEnhancer) para el OCR; clasifica con file_b64


@app.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "device": s.device,
        "model_present": s.model_path.exists(),
        "types": list(s.load_types().get("types", {}).keys()),
    }


@app.post("/verify")
def verify_json(req: VerifyRequest):
    """Endpoint que consume Odoo: recibe el archivo en base64 + el tipo esperado.
    Si la imagen ya viene realzada por DocEnhancer, pre_enhanced=True evita
    procesarla dos veces."""
    return pipeline.verify(
        req.file_b64, req.expected_type, pre_enhanced=req.pre_enhanced, ocr_b64=req.ocr_b64
    )


@app.post("/verify-upload")
async def verify_upload(expected_type: str = Form(...), file: UploadFile = File(...)):
    """Endpoint comodo para pruebas manuales (curl / navegador)."""
    data = await file.read()
    return pipeline.verify(base64.b64encode(data).decode(), expected_type)


# ------------------------- Acreditacion PYME (MIPYME) -------------------------

class PymeDoc(BaseModel):
    doc_type: str        # registro_mercantil | escritura_notarial | identificacion_fiscal | no_adeudo | contrato_cuentas
    file_b64: str        # PDF en base64


class PymeExpediente(BaseModel):
    documentos: list[PymeDoc]


@app.post("/pyme/verify")
def pyme_verify(req: PymeDoc):
    """Evalua UN documento PYME contra las reglas de cumplimiento legal.
    Devuelve el informe de hallazgos (lo que NO cumple) + veredicto."""
    return pyme_pipeline.verify_pyme(req.file_b64, req.doc_type)


@app.post("/pyme/expediente")
def pyme_expediente(req: PymeExpediente):
    """Evalua el expediente PYME completo (los 5 documentos) con el cruce de NIT
    y el estado global de la acreditacion."""
    return pyme_pipeline.verify_expediente([d.model_dump() for d in req.documentos])


@app.post("/pyme/verify-upload")
async def pyme_verify_upload(doc_type: str = Form(...), file: UploadFile = File(...)):
    """Prueba manual: sube un PDF y obtiene el informe de cumplimiento."""
    data = await file.read()
    return pyme_pipeline.verify_pyme(base64.b64encode(data).decode(), doc_type)
