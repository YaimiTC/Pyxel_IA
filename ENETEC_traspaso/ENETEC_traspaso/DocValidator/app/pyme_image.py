"""Capa IMAGEN del cumplimiento PYME: detecta CUÑOS (sellos, region circular con
tinta) y FIRMAS (trazo manuscrito) en el documento escaneado.

Filosofia: la vision no decide sola algo legalmente critico. El detector localiza
y RECORTA la region candidata para que la abogada la confirme de un vistazo, en
vez de buscar el sello a mano. Devuelve, por cada elemento: encontrado (si/no),
confianza y los recortes (base64 JPEG) de las regiones halladas.
"""
from __future__ import annotations

import base64

import cv2
import numpy as np


def render_pages(pdf_bytes: bytes, dpi: int = 200, max_pages: int = 4) -> list[np.ndarray]:
    import fitz  # pymupdf

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    imgs = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(dpi=dpi)
        a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            a = cv2.cvtColor(a, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            a = cv2.cvtColor(a, cv2.COLOR_RGB2BGR)
        else:
            a = cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
        imgs.append(a)
    doc.close()
    return imgs


def _colored_ink_mask(bgr: np.ndarray) -> np.ndarray:
    """Tinta de color (azul/violeta/rojo de cuños y firmas), excluyendo el negro del
    texto impreso (baja saturacion) y el blanco del papel. Exige saturacion ALTA
    para no caer en el ruido de color JPEG sobre el texto negro."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    mask = ((s > 50) & (v > 40) & (v < 240)).astype(np.uint8) * 255
    return mask


def _crop_b64(bgr: np.ndarray, box, pad: int = 8, max_w: int = 320) -> str:
    H, W = bgr.shape[:2]
    x0, y0, x1, y1 = box[:4]
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(W, x1 + pad), min(H, y1 + pad)
    crop = bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return ""
    if crop.shape[1] > max_w:
        scale = max_w / crop.shape[1]
        crop = cv2.resize(crop, (max_w, int(crop.shape[0] * scale)))
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf).decode() if ok else ""


def detect_seals(bgr: np.ndarray) -> list[tuple]:
    """Cuños: blobs de TINTA DE COLOR compactos (aprox. circulares/cuadrados) en la
    zona de firmas. Se ignora el 15% superior (membrete/logo) para no confundir el
    logotipo institucional con un cuño. (Sin Hough: disparaba sobre cada renglon.)"""
    H, W = bgr.shape[:2]
    minside = min(H, W)
    mask = _colored_ink_mask(bgr)
    mask[: int(H * 0.15), :] = 0  # fuera membrete/logo superior
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w < minside * 0.06 or h < minside * 0.06:
            continue
        if w > minside * 0.6 or h > minside * 0.6:
            continue
        ar = w / float(h)
        area = cv2.contourArea(c)
        fill = area / float(w * h + 1)
        # circular/compacto: bounding casi cuadrado y relleno apreciable
        (_cx, _cy), rad = cv2.minEnclosingCircle(c)
        circ = area / (np.pi * rad * rad + 1)  # 1.0 = circulo perfecto
        if 0.6 < ar < 1.7 and fill > 0.18 and circ > 0.35:
            conf = round(min(0.95, 0.45 + circ * 0.5), 2)
            boxes.append((x, y, x + w, y + h, conf, "cuno"))
    return _dedup(boxes)


def detect_signatures(bgr: np.ndarray) -> list[tuple]:
    """Firmas: trazo manuscrito (tinta de color, alargado/irregular), tipicamente en
    la mitad inferior. Se distingue del cuño por ser ancho y poco relleno, y del
    texto impreso por ir en tinta de color y no alinearse en renglones."""
    H, W = bgr.shape[:2]
    minside = min(H, W)
    mask = _colored_ink_mask(bgr)
    # solo mitad inferior (donde se firma); evita confundir membretes de color
    mask[: int(H * 0.45), :] = 0
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 7))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w < minside * 0.12 or h < minside * 0.02:
            continue
        ar = w / float(h)
        fill = cv2.contourArea(c) / float(w * h + 1)
        # trazo de firma: ancho (ar alto), poco relleno (trazo fino sobre area grande)
        if ar > 1.8 and fill < 0.45:
            boxes.append((x, y, x + w, y + h, round(min(1.0, 0.45 + ar / 12), 2), "trazo"))
    return _dedup(boxes)


def _dedup(boxes: list[tuple]) -> list[tuple]:
    """Quita cajas muy solapadas; deja la de mayor confianza."""
    boxes = sorted(boxes, key=lambda b: -b[4])
    kept: list[tuple] = []
    for b in boxes:
        if all(_iou(b, k) < 0.5 for k in kept):
            kept.append(b)
    return kept


def _iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a[:4]
    bx0, by0, bx1, by1 = b[:4]
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    if inter == 0:
        return 0.0
    ua = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / float(ua)


# --- Deteccion DIGITAL por texto (fiable en PDFs nativos firmados) ---
_DIGITAL_MARKERS = [
    "firmado digitalmente", "firma digital", "cuno digital", "cuño digital",
    "firma electronica", "firma electrónica", "certificad", "autoridad de certificacion",
    "sello de tiempo", "c=cu,", "validez de la firma",
]


def digital_trust_from_text(text: str) -> dict:
    """Detecta firma/cuño DIGITAL a partir del texto (PDF nativo firmado). Es la
    señal mas fiable cuando existe: el propio documento declara la firma electronica."""
    low = (text or "").lower()
    hit = next((m for m in _DIGITAL_MARKERS if m in low), None)
    return {"digital": bool(hit), "marker": hit or ""}


def _region_b64(region: np.ndarray, max_w: int = 520) -> str:
    if region.size == 0:
        return ""
    if region.shape[1] > max_w:
        scale = max_w / region.shape[1]
        region = cv2.resize(region, (max_w, int(region.shape[0] * scale)))
    ok, buf = cv2.imencode(".jpg", region, [cv2.IMWRITE_JPEG_QUALITY, 78])
    return base64.b64encode(buf).decode() if ok else ""


def _colored_ratio(region: np.ndarray) -> float:
    if region.size == 0:
        return 0.0
    return float((_colored_ink_mask(region) > 0).mean())


def analyze_pdf(pdf_bytes: bytes, max_pages: int = 4) -> dict:
    """Capa imagen para la abogada. Devuelve:
    - colored_ratio: proporcion de tinta de color en la zona de firmas (parte baja).
    - ink_present: si hay tinta de color apreciable alli (indicio de cuño/firma fisicos).
    - zone_crop: recorte de la zona de firmas/cuños (base64) para confirmar de un vistazo.
    - seals/signatures: cajas best-effort (pueden ir vacias en escaneos debiles).
    """
    pages = render_pages(pdf_bytes, max_pages=max_pages)
    best = None  # pagina con mas tinta de color en la zona de firma
    seals_all, signs_all = [], []
    for img in pages:
        H = img.shape[0]
        zone = img[int(H * 0.6):, :]  # 40% inferior: area habitual de firma/cuño
        ratio = _colored_ratio(zone)
        if best is None or ratio > best[0]:
            best = (ratio, zone, img)
        for b in detect_seals(img):
            seals_all.append((b[4], _crop_b64(img, b)))
        for b in detect_signatures(img):
            signs_all.append((b[4], _crop_b64(img, b)))

    ratio, zone, _img = best if best else (0.0, np.zeros((1, 1, 3), np.uint8), None)
    ink_present = ratio > 0.0008  # ~0.08% de pixeles de color en la zona
    seals_all.sort(key=lambda t: -t[0])
    signs_all.sort(key=lambda t: -t[0])
    return {
        "colored_ratio": round(ratio, 4),
        "ink_present": ink_present,
        "zone_crop": _region_b64(zone),
        "seals": [c for _v, c in seals_all if c][:2],
        "signatures": [c for _v, c in signs_all if c][:2],
    }
