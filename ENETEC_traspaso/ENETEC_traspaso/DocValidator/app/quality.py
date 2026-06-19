"""Pre-check de calidad: descarta imagenes ilegibles antes de gastar GPU."""
from __future__ import annotations

import cv2
import numpy as np


def quality_score(image_bgr: np.ndarray) -> dict:
    """Devuelve un score 0-100 de legibilidad combinando nitidez,
    resolucion y brillo."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    # Nitidez: varianza del Laplaciano (mas alto = mas nitido)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharp_score = min(sharpness / 500.0, 1.0) * 100  # ~500 ya es nitido

    # Resolucion: el lado corto deberia rondar >= 600px
    res_score = min(min(h, w) / 600.0, 1.0) * 100

    # Brillo: penaliza imagenes negras o quemadas
    mean = float(gray.mean())
    bright_score = 100.0 if 40 < mean < 220 else 0.0

    score = 0.5 * sharp_score + 0.3 * res_score + 0.2 * bright_score
    return {
        "score": round(score, 1),
        "sharpness": round(float(sharpness), 1),
        "resolution": [int(w), int(h)],
        "brightness": round(mean, 1),
    }
