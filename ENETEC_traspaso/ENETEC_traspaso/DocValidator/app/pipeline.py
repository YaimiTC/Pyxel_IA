"""Orquesta el pipeline de validacion: calidad -> clasificacion -> OCR/reglas
-> veredicto (passed / doubt / rejected). Este es el cerebro del servicio."""
from __future__ import annotations

import base64
import io

import cv2
import numpy as np
from PIL import Image

from . import classifier as clf_mod
from . import ocr as ocr_mod
from . import quality as quality_mod
from .config import get_settings


def _decode_image(file_b64: str):
    raw = base64.b64decode(file_b64)
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return pil, bgr


def verify(file_b64: str, expected_type: str, pre_enhanced: bool = False, ocr_b64: str = "") -> dict:
    settings = get_settings()
    types_cfg = settings.load_types()
    garbage = types_cfg.get("garbage_class", "_basura")
    type_cfg = types_cfg.get("types", {}).get(expected_type, {})

    # La imagen ORIGINAL (color) se usa para clasificar y medir calidad: el
    # clasificador se entreno con imagenes a color sin procesar.
    pil, bgr = _decode_image(file_b64)

    # 1) Calidad (barato, primero)
    q = quality_mod.quality_score(bgr)
    if q["score"] < types_cfg.get("quality_min_score", 40):
        return _result(
            "rejected", 0.0, "unknown", {}, q,
            ["Imagen ilegible o de baja calidad"], expected_type,
        )

    # 2) Clasificacion del tipo de documento (siempre sobre la ORIGINAL)
    clf = clf_mod.predict(pil, settings.model_path, settings.classes_path, settings.device)
    classified = clf["label"]
    confidence = clf["confidence"]

    # 3) OCR sobre la imagen REALZADA si se provee (DocEnhancer); si no, sobre la
    #    original con pre-procesado interno. Asi clasificacion y lectura usan la
    #    mejor imagen para cada tarea.
    if ocr_b64:
        _pil_e, ocr_bgr = _decode_image(ocr_b64)
        text = ocr_mod.read_text(ocr_bgr, settings.ocr_lang, preprocess=False) if settings.enable_ocr else ""
    else:
        text = ocr_mod.read_text(bgr, settings.ocr_lang, preprocess=not pre_enhanced) if settings.enable_ocr else ""
    fields = ocr_mod.extract_fields(text, type_cfg)
    kw_hit, kw_total = ocr_mod.keywords_present(text, type_cfg.get("keywords", []))
    kw_ok = (kw_total == 0) or (kw_hit >= max(1, kw_total // 2))

    # 4) Reglas + veredicto
    reasons: list[str] = []
    is_garbage = classified in (garbage, "unknown")
    type_match = classified == expected_type

    if is_garbage:
        reasons.append("El documento no corresponde a ningun tipo valido")
    elif not type_match:
        reasons.append(f"Se esperaba '{expected_type}' pero parece '{classified}'")
    if not kw_ok:
        reasons.append("No se encontraron las palabras clave esperadas")

    missing_required = [f for f in type_cfg.get("required_fields", []) if not fields.get(f)]

    min_conf = type_cfg.get("min_confidence", 70)
    verdict = _decide(confidence, type_match, kw_ok, min_conf, is_garbage)
    # Un documento del tipo correcto pero con campos obligatorios ausentes no se
    # aprueba directo: baja a revision humana (doubt), no se rechaza de golpe.
    if verdict == "passed" and missing_required:
        verdict = "doubt"
        reasons.append("Faltan campos obligatorios: " + ", ".join(missing_required))
    elif verdict == "passed":
        reasons.append("Documento valido")
    elif verdict == "doubt" and not reasons:
        reasons.append("Confianza insuficiente: requiere revision humana")

    return _result(verdict, confidence, classified, fields, q, reasons, expected_type, text[:500])


def _decide(conf: float, type_match: bool, kw_ok: bool, min_conf: float, is_garbage: bool) -> str:
    """La IA solo filtra (rejected) y prioriza (doubt). Nunca aprueba sola lo
    critico: 'passed' significa 'apto para revision rapida', no aprobacion final.

    Combina clasificador de imagen + OCR: si el clasificador falla pero el texto
    del documento (OCR) reconoce las palabras clave esperadas, NO se rechaza de
    golpe, sino que se manda a revision humana (doubt). Solo se rechaza la basura
    clara o el tipo equivocado SIN ninguna senal de texto coherente."""
    if (is_garbage or not type_match) and not kw_ok:
        return "rejected"
    if type_match and conf >= min_conf and kw_ok:
        return "passed"
    return "doubt"


def _result(verdict, conf, classified, fields, q, reasons, expected, ocr_text=""):
    return {
        "verdict": verdict,  # passed (verde) / doubt (amarillo) / rejected (rojo)
        "score": conf,
        "expected_type": expected,
        "classified_type": classified,
        "quality": q,
        "fields": fields,
        "reasons": reasons,
        "ocr_excerpt": ocr_text,
    }
