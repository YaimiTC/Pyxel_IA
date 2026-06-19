"""Pipeline de acreditacion PYME: recibe un PDF (base64), extrae su texto (capa
del PDF o, si esta escaneado, OCR de la portada realzada) y lo pasa por el motor
de cumplimiento legal -> informe de hallazgos. Tambien evalua el expediente
completo (los 5 documentos) con el cruce de NIT.

Detector PRINCIPAL = texto/OCR + reglas (segun diseno acordado: OCR principal,
CNN de apoyo). El clasificador de imagen PYME entra como senal extra cuando exista
el modelo entrenado.
"""
from __future__ import annotations

import base64

from . import ocr as ocr_mod
from . import pyme_compliance as pc
from . import pyme_image as pyimg
from .config import get_settings

_RULES = None


def _rules() -> dict:
    global _RULES
    if _RULES is None:
        _RULES = pc.load_rules()
    return _RULES


def _pdf_text(pdf_bytes: bytes) -> tuple[str, str]:
    """Devuelve (texto, via). via = 'capa-pdf' u 'OCR (Npags)' (escaneado).
    Para escaneados hace OCR de VARIAS paginas (no solo la portada) y, si hay
    DocEnhancer configurado, REALZA cada pagina antes del OCR."""
    import re

    import cv2
    import fitz  # pymupdf
    import numpy as np

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    raw = "\n".join(page.get_text("text") for page in doc)
    scanned = len(re.sub(r"\s", "", raw)) < 40
    if not scanned:
        doc.close()
        return raw, "capa-pdf"

    settings = get_settings()
    if not settings.enable_ocr:
        doc.close()
        return "", "OCR"

    max_pages = min(len(doc), 4)  # multipagina: cubre escrituras con portada escasa
    texts = []
    for i in range(max_pages):
        pix = doc[i].get_pixmap(dpi=200)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        img, enhanced = _maybe_enhance(img)
        t = ocr_mod.read_text(img, settings.ocr_lang, preprocess=not enhanced)
        if t:
            texts.append(t)
    doc.close()
    return "\n".join(texts), f"OCR ({len(texts)}/{max_pages} pags)"


def _maybe_enhance(bgr):
    """Realza una pagina escaneada con DocEnhancer si esta configurado. Devuelve
    (imagen, enhanced_bool). Si no hay servicio o falla, devuelve la original."""
    import cv2
    import numpy as np
    import requests

    url = get_settings().enhancer_url
    if not url:
        return bgr, False
    try:
        ok, buf = cv2.imencode(".png", bgr)
        if not ok:
            return bgr, False
        b64 = base64.b64encode(buf).decode()
        resp = requests.post(
            url.rstrip("/") + "/enhance",
            json={"file_b64": b64, "filename": "page.png"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok") and data.get("image_b64"):
            raw = base64.b64decode(data["image_b64"])
            arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if arr is not None:
                return arr, True
    except Exception:  # noqa: BLE001
        pass
    return bgr, False


def verify_pyme(file_b64: str, doc_type: str) -> dict:
    """Evalua UN documento PYME. Devuelve el informe de cumplimiento + 'via'.
    Combina texto (cumplimiento legal) + capa imagen (cuño/firma: digital por
    texto, fisico por tinta en la zona de firmas con recorte para la abogada)."""
    pdf_bytes = base64.b64decode(file_b64)
    text, via = _pdf_text(pdf_bytes)
    try:
        img = pyimg.analyze_pdf(pdf_bytes)
        img.update(pyimg.digital_trust_from_text(text))
    except Exception:  # noqa: BLE001
        img = {}
    res = pc.evaluate(text, doc_type, _rules(), image_info=img)
    res["via_texto"] = via
    res["chars"] = len(text)
    res["cnn"] = _cnn_support(pdf_bytes, doc_type, res)
    return res


def _cnn_support(pdf_bytes: bytes, doc_type: str, res: dict) -> dict:
    """Clasificador PYME de apoyo (CNN): predice el tipo desde la portada. La
    deteccion PRINCIPAL es el texto/reglas; la CNN solo confirma o avisa. Si no hay
    modelo entrenado, degrada a 'unknown' sin afectar el veredicto."""
    from . import classifier as clf_mod

    try:
        import cv2
        import fitz
        import numpy as np
        from PIL import Image

        s = get_settings()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = doc[0].get_pixmap(dpi=150)
        doc.close()
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
        else:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB) if False else arr
        pil = Image.fromarray(arr)
        clf = clf_mod.predict(pil, s.pyme_model_path, s.pyme_classes_path, s.device)
    except Exception:  # noqa: BLE001
        return {"label": "unknown", "confidence": 0.0}

    label, conf = clf.get("label", "unknown"), clf.get("confidence", 0.0)
    # Aviso suave si la CNN, con confianza alta, ve un tipo distinto al declarado.
    if label not in ("unknown", doc_type) and conf >= 75:
        res.setdefault("findings", []).append({
            "id": "cnn_tipo", "label": "El clasificador de imagen ve un tipo distinto",
            "severity": "medio", "status": "fail", "base": "CNN de apoyo",
            "detail": f"la CNN clasifica la portada como '{label}' ({conf}%), no '{doc_type}'",
            "img_signal": "", "icon": "🟡",
        })
        res["resumen"]["advertencias"] = res["resumen"].get("advertencias", 0) + 1
        if res.get("verdict") == "apto":
            res["verdict"] = "revisar"
    return {"label": label, "confidence": conf}


def verify_expediente(documentos: list[dict]) -> dict:
    """Evalua el expediente completo. documentos = [{doc_type, file_b64}, ...].
    Devuelve cada informe + el cruce de coherencia (NIT) + estado global."""
    informes = []
    for d in documentos:
        try:
            informes.append(verify_pyme(d["file_b64"], d["doc_type"]))
        except Exception as e:  # noqa: BLE001
            informes.append({"doc_type": d.get("doc_type"), "error": str(e), "verdict": "no_apto"})

    cruces = pc.cross_validate(informes)
    tipos_requeridos = list(_rules()["tipos"].keys())
    entregados = {i.get("doc_type") for i in informes}
    faltantes = [t for t in tipos_requeridos if t not in entregados]

    hay_no_apto = any(i.get("verdict") == "no_apto" for i in informes) or bool(cruces)
    hay_revisar = any(i.get("verdict") == "revisar" for i in informes)
    if faltantes or hay_no_apto:
        estado = "no_apto"
    elif hay_revisar:
        estado = "revisar"
    else:
        estado = "apto"

    return {
        "estado": estado,                  # apto / revisar / no_apto
        "completos": f"{len(entregados)}/{len(tipos_requeridos)}",
        "faltantes": faltantes,
        "cruces": cruces,
        "informes": informes,
    }
