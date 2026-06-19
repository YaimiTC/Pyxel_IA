"""Dibuja las detecciones de cuño (verde) y firma (azul) sobre cada documento PYME
real, para calibrar visualmente. Guarda PNG anotados en images/_det_<tipo>.png"""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import pyme_image as pi  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
OUT = BASE.parent / "images"
OUT.mkdir(exist_ok=True)

M = {"registro mercantil": "registro_mercantil", "escritura": "escritura_notarial",
     "identific": "identificacion_fiscal", "adeudo": "no_adeudo", "cuentas": "contrato_cuentas"}


def t(n):
    n = n.lower()
    for k, v in M.items():
        if k in n:
            return v


seen = {}
for p in sorted((BASE / "_pyme_eval").rglob("*.pdf")):
    dt = t(p.parent.name) or t(p.name)
    if dt and dt not in seen:
        seen[dt] = p

for dt, pdf in seen.items():
    pages = pi.render_pages(pdf.read_bytes(), max_pages=4)
    nseal = nsign = 0
    # busca la pagina con mas detecciones para anotar
    best = None
    for img in pages:
        seals = pi.detect_seals(img)
        signs = pi.detect_signatures(img)
        nseal += len(seals)
        nsign += len(signs)
        if best is None or (len(seals) + len(signs)) > best[1]:
            best = (img.copy(), len(seals) + len(signs), seals, signs)
    img, _n, seals, signs = best
    for x0, y0, x1, y1, conf, kind in seals:
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 180, 0), 4)
        cv2.putText(img, f"CUNO {conf}", (x0, max(0, y0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 180, 0), 3)
    for x0, y0, x1, y1, conf, kind in signs:
        cv2.rectangle(img, (x0, y0), (x1, y1), (220, 0, 0), 4)
        cv2.putText(img, f"FIRMA {conf}", (x0, max(0, y0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (220, 0, 0), 3)
    out = OUT / f"_det_{dt}.png"
    cv2.imwrite(str(out), img)
    print(f"{dt}: cuños={nseal} firmas={nsign} -> {out.name}")
