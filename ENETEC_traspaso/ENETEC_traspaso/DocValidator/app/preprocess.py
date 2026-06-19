"""Pre-procesado de imagen para OCR. Limpia y realza el escaneo ANTES de pasarlo
a PaddleOCR para que lea mejor el texto (etiquetas y campos como shipper, puertos).

Importante: esto se usa SOLO para el OCR. El clasificador de tipo de documento
sigue recibiendo la imagen ORIGINAL (se entreno con imagenes sin procesar)."""
from __future__ import annotations

import cv2
import numpy as np


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Corrige una inclinacion leve del escaneo (deskew). Si algo falla o el
    angulo es grande/improbable, devuelve la imagen sin tocar."""
    try:
        inv = cv2.bitwise_not(gray)
        thr = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thr > 0))
        if len(coords) < 50:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        # Solo corrige inclinaciones pequenas (evita rotar formularios validos).
        if abs(angle) < 0.3 or abs(angle) > 10:
            return gray
        h, w = gray.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(
            gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
    except Exception:
        return gray


def preprocess_for_ocr(image_bgr: np.ndarray) -> np.ndarray:
    """Devuelve una version 3-canales lista para OCR: ampliada, enderezada,
    con mas contraste, menos ruido y mas nitida. Es defensiva: ante cualquier
    fallo devuelve la imagen original (el OCR nunca se queda sin imagen)."""
    try:
        img = image_bgr
        h, w = img.shape[:2]

        # 1) Upscale: el texto pequeno de un BL escaneado se lee mucho mejor
        #    con mas resolucion (el OCR es sensible a la altura de la letra).
        longest = max(h, w)
        if longest < 2200:
            scale = 2200.0 / longest
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2) Deskew (enderezar)
        gray = _deskew(gray)

        # 3) Contraste local adaptativo (CLAHE): realza texto tenue sin quemar.
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # 4) Reduccion de ruido preservando bordes del texto.
        gray = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)

        # 5) Nitidez (unsharp mask): resalta los trazos de las letras.
        blur = cv2.GaussianBlur(gray, (0, 0), 3)
        gray = cv2.addWeighted(gray, 1.6, blur, -0.6, 0)

        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    except Exception:
        return image_bgr
