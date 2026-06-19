"""Expande el dataset PYME para entrenar el clasificador separado.

Renderiza TODAS las paginas (hasta max) de cada PDF real por clase -> muchas mas
muestras a partir de las 20 originales. Añade una clase _basura con negativos del
dataset principal (carne, BL, facturas...) para que el modelo rechace lo que no es
PYME. Salida: dataset_pyme_full/<clase>/*.jpg

Uso:  python -m training.prep_pyme_dataset
"""
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
SRC_PDFS = BASE / "_pyme_eval"
DATASET_MAIN = BASE / "dataset"
OUT = BASE / "dataset_pyme_full"
MAX_PAGES = 6
DPI = 150

MAP = {"registro mercantil": "registro_mercantil", "escritura": "escritura_notarial",
       "identific": "identificacion_fiscal", "adeudo": "no_adeudo", "cuentas": "contrato_cuentas"}


def _type(name: str):
    low = name.lower()
    for k, v in MAP.items():
        if k in low:
            return v


def render_pdf_pages(pdf: Path, out_dir: Path, stem: str):
    import fitz

    doc = fitz.open(pdf)
    n = 0
    for i, page in enumerate(doc):
        if i >= MAX_PAGES:
            break
        pix = page.get_pixmap(dpi=DPI)
        a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            a = cv2.cvtColor(a, cv2.COLOR_RGBA2BGR)
        elif pix.n == 1:
            a = cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
        else:
            a = cv2.cvtColor(a, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(out_dir / f"{stem}_p{i}.jpg"), a)
        n += 1
    doc.close()
    return n


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1) Documentos PYME reales: todas las paginas
    counts = {}
    for pdf in sorted(SRC_PDFS.rglob("*.pdf")):
        t = _type(pdf.parent.name) or _type(pdf.name)
        if not t:
            continue
        d = OUT / t
        d.mkdir(exist_ok=True)
        stem = pdf.stem.replace(" ", "_")[:30] + f"_{abs(hash(str(pdf))) % 1000}"
        counts[t] = counts.get(t, 0) + render_pdf_pages(pdf, d, stem)

    # 2) _basura: negativos del dataset principal (lo que NO es PYME)
    bas = OUT / "_basura"
    bas.mkdir(exist_ok=True)
    nbas = 0
    sources = ["_basura", "carnet_identidad", "bl", "commercial_invoice", "doc_empresa"]
    for cls in sources:
        cdir = DATASET_MAIN / cls
        if not cdir.exists():
            continue
        for img in sorted(cdir.glob("*.jpg"))[:7]:  # pocos por fuente -> ~35, balanceado
            shutil.copy(img, bas / f"{cls}_{img.name}")
            nbas += 1
    counts["_basura"] = nbas

    print("Dataset PYME expandido en:", OUT)
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v} imagenes")


if __name__ == "__main__":
    main()
