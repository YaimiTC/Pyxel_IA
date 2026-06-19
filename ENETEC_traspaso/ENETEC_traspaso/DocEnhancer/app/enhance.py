"""Nucleo de realce de imagen de DocEnhancer. Lleva un documento escaneado o
fotografiado al maximo de legibilidad ANTES del OCR, encadenando tecnicas de
vision por computador (todo local, sin nube):

  1. Auto-orientacion
  2. Deteccion del documento + correccion de perspectiva (dewarp)
  3. Deskew (enderezar inclinacion fina)
  4. Normalizacion de iluminacion / quitar sombras
  5. Reduccion de ruido preservando bordes
  6. Contraste local adaptativo (CLAHE)
  7. Super-resolucion (DNN local si hay modelo; si no, cubica)
  8. Nitidez (unsharp mask)

Cada paso es defensivo: ante cualquier fallo conserva el resultado del paso
anterior, de modo que el servicio nunca devuelve una imagen vacia.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Cache del modelo de super-resolucion (se carga una sola vez).
_SR = None
_SR_TRIED = False


# --------------------------------------------------------------------------- #
# Carga de imagen (soporta PDF si PyMuPDF esta instalado)
# --------------------------------------------------------------------------- #
def load_image(data: bytes, filename: str = "") -> np.ndarray:
    """Decodifica bytes a imagen BGR. Si es PDF, rasteriza la primera pagina."""
    is_pdf = filename.lower().endswith(".pdf") or data[:5] == b"%PDF-"
    if is_pdf:
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=data, filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))  # 3x = ~216 dpi
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            return img
        except Exception:
            pass  # cae al decode normal si falla
    # Decodifica respetando la orientacion EXIF (fotos de movil suelen venir
    # giradas 90/180); cv2.imdecode la ignora, asi que usamos PIL primero.
    try:
        import io

        from PIL import Image, ImageOps

        pil = Image.open(io.BytesIO(data))
        pil = ImageOps.exif_transpose(pil).convert("RGB")
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        pass
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen")
    return img


# --------------------------------------------------------------------------- #
# Pasos de realce
# --------------------------------------------------------------------------- #
def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]   # top-right
    rect[3] = pts[np.argmax(d)]   # bottom-left
    return rect


def _find_document_quad(bgr: np.ndarray):
    """Busca el contorno cuadrilatero mas grande (el borde del documento)."""
    h, w = bgr.shape[:2]
    area_img = h * w
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:5]:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > 0.30 * area_img and cv2.isContourConvex(approx):
            return approx.reshape(4, 2).astype("float32")
    return None


def dewarp(bgr: np.ndarray):
    """Corrige la perspectiva si detecta el documento. Devuelve (img, detectado)."""
    try:
        quad = _find_document_quad(bgr)
        if quad is None:
            return bgr, False
        rect = _order_points(quad)
        (tl, tr, br, bl) = rect
        wA = np.linalg.norm(br - bl)
        wB = np.linalg.norm(tr - tl)
        hA = np.linalg.norm(tr - br)
        hB = np.linalg.norm(tl - bl)
        maxW = int(max(wA, wB))
        maxH = int(max(hA, hB))
        if maxW < 200 or maxH < 200:
            return bgr, False
        dst = np.array([[0, 0], [maxW - 1, 0], [maxW - 1, maxH - 1], [0, maxH - 1]], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(bgr, M, (maxW, maxH)), True
    except Exception:
        return bgr, False


def deskew(gray: np.ndarray) -> tuple[np.ndarray, float]:
    try:
        inv = cv2.bitwise_not(gray)
        thr = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thr > 0))
        if len(coords) < 50:
            return gray, 0.0
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) < 0.2 or abs(angle) > 15:
            return gray, 0.0
        h, w = gray.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rot = cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rot, round(float(angle), 2)
    except Exception:
        return gray, 0.0


def remove_shadows(gray: np.ndarray) -> np.ndarray:
    """Normaliza la iluminacion: estima el fondo y lo divide para quitar sombras
    y manchas de luz despareja (muy efectivo en fotos de documentos)."""
    try:
        dilated = cv2.dilate(gray, np.ones((7, 7), np.uint8))
        bg = cv2.medianBlur(dilated, 21)
        diff = 255 - cv2.absdiff(gray, bg)
        return cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
    except Exception:
        return gray


def _get_sr():
    """Carga (una vez) un modelo de super-resolucion DNN local si existe en
    models/ (p.ej. FSRCNN_x2.pb / EDSR_x2.pb). Si no hay, devuelve None y se usa
    interpolacion cubica."""
    global _SR, _SR_TRIED
    if _SR_TRIED:
        return _SR
    _SR_TRIED = True
    try:
        if not hasattr(cv2, "dnn_superres"):
            return None
        # FSRCNN primero: muy rapido y ligero (ideal para un servicio en vivo).
        # EDSR como alternativa de maxima calidad si esta presente.
        for name, algo, scale in [("FSRCNN_x2.pb", "fsrcnn", 2), ("EDSR_x2.pb", "edsr", 2)]:
            p = MODELS_DIR / name
            if p.exists():
                sr = cv2.dnn_superres.DnnSuperResImpl_create()
                sr.readModel(str(p))
                sr.setModel(algo, scale)
                _SR = (sr, scale)
                break
    except Exception:
        _SR = None
    return _SR


def upscale(gray: np.ndarray, target_long: int = 2400) -> tuple[np.ndarray, str]:
    """Amplia para que el texto pequeno se lea mejor. Usa DNN local si esta
    disponible; si no, interpolacion cubica."""
    h, w = gray.shape[:2]
    longest = max(h, w)
    if longest >= target_long:
        return gray, "none"
    sr = _get_sr()
    if sr is not None:
        try:
            out = sr[0].upsample(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
            return cv2.cvtColor(out, cv2.COLOR_BGR2GRAY), "dnn"
        except Exception:
            pass
    scale = target_long / longest
    return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC), "cubic"


def _sharpness(gray: np.ndarray) -> float:
    return round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)


# --------------------------------------------------------------------------- #
# Pipeline completo
# --------------------------------------------------------------------------- #
def enhance(data: bytes, filename: str = "", do_dewarp: bool = True) -> tuple[bytes, dict]:
    """Devuelve (png_bytes_realzada, meta). Encadena todos los pasos de forma
    defensiva."""
    t0 = time.time()
    steps = []
    bgr = load_image(data, filename)
    h0, w0 = bgr.shape[:2]

    detected = False
    if do_dewarp:
        bgr, detected = dewarp(bgr)
        if detected:
            steps.append("dewarp")

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    sharp_in = _sharpness(gray)

    gray, angle = deskew(gray)
    if angle:
        steps.append("deskew(%.1f)" % angle)

    gray = remove_shadows(gray)
    steps.append("shadow_removal")

    gray = cv2.fastNlMeansDenoising(gray, None, h=7, templateWindowSize=7, searchWindowSize=21)
    steps.append("denoise")

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    steps.append("clahe")

    gray, sr_mode = upscale(gray)
    steps.append("upscale:" + sr_mode)

    # Nitidez moderada: realza trazos sin llegar a pegar caracteres/palabras.
    blur = cv2.GaussianBlur(gray, (0, 0), 2)
    gray = cv2.addWeighted(gray, 1.4, blur, -0.4, 0)
    steps.append("sharpen")

    ok, buf = cv2.imencode(".png", gray)
    if not ok:
        raise ValueError("No se pudo codificar la imagen realzada")

    meta = {
        "steps": steps,
        "doc_detected": detected,
        "deskew_angle": angle,
        "size_in": [int(w0), int(h0)],
        "size_out": [int(gray.shape[1]), int(gray.shape[0])],
        "sharpness_in": sharp_in,
        "sharpness_out": _sharpness(gray),
        "sr_mode": sr_mode,
        "ms": int((time.time() - t0) * 1000),
    }
    return buf.tobytes(), meta
