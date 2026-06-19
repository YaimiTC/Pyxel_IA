"""Evalua los documentos PYME REALES contra el motor de cumplimiento.

Extrae los ZIP de Pyme/ a una carpeta temporal, mapea cada carpeta a su tipo,
extrae el texto (capa PDF; si esta escaneado -> OCR de la portada) y produce el
informe de cumplimiento por documento + el cruce de NIT del expediente.

Uso:  python -m training.eval_pyme
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import pyme_compliance as pc  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
PYME = BASE / "Pyme"
WORK = BASE / "_pyme_eval"

# carpeta del zip (por substring) -> tipo de documento en las reglas
ZIP_TO_TYPE = {
    "registro mercantil": "registro_mercantil",
    "escritura": "escritura_notarial",
    "identific": "identificacion_fiscal",
    "adeudo": "no_adeudo",
    "cuentas": "contrato_cuentas",
}


def _match_type(name: str) -> str | None:
    low = name.lower()
    for key, t in ZIP_TO_TYPE.items():
        if key in low:
            return t
    return None


def _ensure_extracted() -> None:
    WORK.mkdir(exist_ok=True)
    for zp in PYME.glob("*.zip"):
        out = WORK / zp.stem
        if out.exists():
            continue
        out.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zp) as zf:
                zf.extractall(out)
        except Exception as e:  # noqa: BLE001
            print(f"  ! no se pudo extraer {zp.name}: {e}")
    # carpetas ya extraidas (no-zip) tambien valen
    for d in PYME.iterdir():
        if d.is_dir() and d.name != "_legal" and not (WORK / d.name).exists():
            (WORK / d.name).symlink_to(d) if False else None


def _ocr_pdf_first_page(pdf: Path) -> str:
    """Para escaneados: renderiza la portada y pasa OCR (PaddleOCR)."""
    try:
        import cv2
        import fitz
        import numpy as np
        from app import ocr as ocr_mod
    except Exception as e:  # noqa: BLE001
        return ""
    doc = fitz.open(pdf)
    pix = doc[0].get_pixmap(dpi=200)
    doc.close()
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return ocr_mod.read_text(img, "es", preprocess=True)


def main() -> None:
    rules = pc.load_rules()
    _ensure_extracted()

    # localiza fuentes: cada subcarpeta extraida + carpetas sueltas en Pyme/
    sources = list(WORK.iterdir())
    for d in PYME.iterdir():
        if d.is_dir() and d.name != "_legal":
            sources.append(d)

    resultados = []
    for src in sources:
        if not src.is_dir():
            continue
        dtype = _match_type(src.name)
        if not dtype:
            continue
        pdfs = sorted(src.rglob("*.pdf"))
        if not pdfs:
            continue
        pdf = pdfs[0]  # un representante por tipo para la demo
        text, scanned = pc.extract_text_from_pdf(pdf)
        via = "capa-pdf"
        if scanned:
            text = _ocr_pdf_first_page(pdf)
            via = "OCR"
        res = pc.evaluate(text, dtype, rules)
        resultados.append(res)
        print(f"\n[{dtype}] fuente={pdf.name}  ({via}, {len(text)} chars)")
        print(pc.format_report(res))

    # cruce de expediente
    cruces = pc.cross_validate(resultados)
    print("\n" + "=" * 70)
    print("CRUCE DEL EXPEDIENTE (coherencia entre documentos):")
    if cruces:
        for c in cruces:
            print(f"  {c['icon']} {c['label']} — {c['detail']}")
    else:
        print("  🟢 NIT coherente / sin contradicciones detectadas en texto")


if __name__ == "__main__":
    main()
