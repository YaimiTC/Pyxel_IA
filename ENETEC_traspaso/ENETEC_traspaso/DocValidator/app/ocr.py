"""OCR con PaddleOCR + extraccion de campos por regla. El import es perezoso
para que el servicio arranque aunque PaddleOCR no este instalado todavia."""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

from . import preprocess as pp


@lru_cache
def _get_ocr(lang: str):
    import os
    from paddleocr import PaddleOCR  # import pesado: solo al primer uso

    cpu_threads = max(1, os.cpu_count() or 1)
    return PaddleOCR(use_angle_cls=True, lang=lang, show_log=False, cpu_threads=cpu_threads)


def _order_boxes(result) -> str:
    """Ordena las cajas detectadas por posicion (fila de arriba a abajo, y dentro
    de cada fila de izquierda a derecha) para que cada etiqueta quede junto a su
    valor. Un OCR sin orden espacial mezcla columnas y rompe la extraccion."""
    items = []  # (y_top, x_left, alto, texto)
    for page in result or []:
        for box in page or []:
            if not (box and box[1] and box[1][0]):
                continue
            pts = box[0] or []
            ys = [p[1] for p in pts] or [0]
            xs = [p[0] for p in pts] or [0]
            items.append((min(ys), min(xs), max(ys) - min(ys), box[1][0]))
    if not items:
        return ""
    # Tolerancia de fila: ~60% de la altura mediana de la letra detectada.
    heights = sorted(h for _, _, h, _ in items if h > 0)
    tol = max(8.0, (heights[len(heights) // 2] if heights else 12) * 0.6)
    items.sort(key=lambda t: (t[0], t[1]))
    rows = []  # [y_ref, [items...]]
    for it in items:
        for row in rows:
            if abs(row[0] - it[0]) <= tol:
                row[1].append(it)
                break
        else:
            rows.append([it[0], [it]])
    lines = []
    for _y, row_items in sorted(rows, key=lambda r: r[0]):
        row_items.sort(key=lambda t: t[1])
        lines.append(" ".join(t[3] for t in row_items))
    return " ".join(lines)


def read_text(image_bgr: np.ndarray, lang: str = "es", preprocess: bool = True) -> str:
    """Devuelve todo el texto detectado. Aplica un pre-procesado de imagen
    (limpieza/realce) antes del OCR y ordena el resultado espacialmente. Si la
    imagen ya viene realzada (DocEnhancer), preprocess=False evita procesarla dos
    veces. Si el OCR no esta disponible, "" (el pipeline sigue sin texto)."""
    try:
        ocr = _get_ocr(lang)
    except Exception:
        return ""
    image = pp.preprocess_for_ocr(image_bgr) if preprocess else image_bgr
    try:
        result = ocr.ocr(image, cls=True)
    except Exception:
        return ""
    return _order_boxes(result)


def extract_fields(text: str, type_cfg: dict) -> dict:
    """Extrae campos via regex configurado por tipo: el numero principal mas
    cualquier campo definido en 'field_patterns' (nombre, vencimiento, ...)."""
    fields: dict = {}
    regex = type_cfg.get("number_regex")
    if regex:
        m = re.search(regex, text, re.IGNORECASE)
        if m:
            fields["numero"] = m.group(0)
    for name, pattern in (type_cfg.get("field_patterns") or {}).items():
        # Cada campo admite un patron o una lista de patrones (se prueban en orden:
        # util para cubrir el formato sintetico y el de documentos reales).
        patterns = pattern if isinstance(pattern, list) else [pattern]
        for pat in patterns:
            try:
                m = re.search(pat, text, re.IGNORECASE)
            except re.error:
                continue
            if m:
                value = (m.group(1) if m.groups() else m.group(0)).strip()
                if value:
                    fields[name] = value
                    break
    return fields


def keywords_present(text: str, keywords: list[str]) -> tuple[int, int]:
    """Cuenta cuantas palabras clave esperadas aparecen en el texto."""
    low = text.lower()
    hit = sum(1 for k in keywords if k.lower() in low)
    return hit, len(keywords)
