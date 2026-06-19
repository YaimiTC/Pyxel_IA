"""Genera un dataset SINTETICO para validar el pipeline sin documentos reales.
Incluye documentos de identidad (carne, etc.) y documentos navieros/transitarios
(Bill of Lading, factura comercial, packing list, certificado de origen) + basura.
Cuando tengas documentos REALES, vacia dataset/ y coloca tus imagenes por carpeta.

Uso:
    python -m training.make_synthetic_data
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET = BASE_DIR / "dataset"

SPECS = {
    # --- Documentos de identidad / legales ---
    "carnet_identidad": {
        "bg": (210, 225, 245),
        "title": "REPUBLICA DE CUBA - CARNE DE IDENTIDAD",
        "fields": ["Nombre: Persona {idx}", "Numero: {num11}", "Apellidos: Prueba Demo", "Vencimiento: 2030-01-01"],
    },
    "certificacion_legal": {
        "bg": (245, 240, 220),
        "title": "CERTIFICACION LEGAL - NOTARIO REGISTRO",
        "fields": ["Certifico que el cliente", "Notario Publico", "Registro: {num6}", "Tomo y Folio: {num3}"],
    },
    "doc_empresa": {
        "bg": (225, 245, 225),
        "title": "DOCUMENTO LEGAL DE EMPRESA - NIT LICENCIA",
        "fields": ["Razon Social: Empresa {idx} SA", "NIT: {num9}", "Licencia comercial", "Domicilio fiscal"],
    },
    # --- Documentos navieros / transitarios ---
    "bl": {
        "bg": (214, 226, 238),
        "title": "BILL OF LADING",
        "fields": [
            "B/L No: MAEU{num9}",
            "Shipper: Exporter {idx} SA",
            "Consignee: Importer {idx} LTD",
            "Notify Party: Same as consignee",
            "Vessel / Voyage: MV OCEAN {idx} / V{num3}",
            "Port of Loading: SHANGHAI",
            "Port of Discharge: MARIEL",
            "Container No: MSKU{num7}",
            "Description of Goods: 1200 CARTONS",
        ],
    },
    "commercial_invoice": {
        "bg": (224, 240, 224),
        "title": "COMMERCIAL INVOICE",
        "fields": [
            "Invoice No: INV-{num6}",
            "Seller: Exporter {idx} SA",
            "Buyer: Importer {idx} LTD",
            "Description: Auto parts",
            "Quantity: {num3} units",
            "Unit Price: USD 12.50",
            "Total Amount: USD {num5}",
            "Incoterms: FOB SHANGHAI",
        ],
    },
    "packing_list": {
        "bg": (246, 243, 220),
        "title": "PACKING LIST",
        "fields": [
            "Packing List No: PL-{num6}",
            "Shipper: Exporter {idx} SA",
            "Consignee: Importer {idx} LTD",
            "Marks and Numbers: 1-{num3}",
            "No of Packages: {num3} cartons",
            "Net Weight: {num4} KG",
            "Gross Weight: {num4} KG",
            "Dimensions: 40x30x25 cm",
        ],
    },
    "certificate_of_origin": {
        "bg": (240, 230, 214),
        "title": "CERTIFICATE OF ORIGIN",
        "fields": [
            "Certificate No: CO-{num6}",
            "Exporter: Exporter {idx} SA",
            "Consignee: Importer {idx} LTD",
            "Country of Origin: CHINA",
            "Description of Goods: Auto parts",
            "Chamber of Commerce",
        ],
    },
    # --- Basura / documento equivocado ---
    "_basura": {
        "bg": (235, 235, 235),
        "title": "recibo de la luz / foto aleatoria",
        "fields": ["Consumo kWh: {num3}", "Importe: 45.20", "Cliente residencial", "Factura electrica"],
    },
}


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _fmt(t: str, idx: int) -> str:
    return t.format(
        idx=idx,
        num3=random.randint(100, 999),
        num4=random.randint(1000, 9999),
        num5=random.randint(10000, 99999),
        num6=random.randint(10 ** 5, 10 ** 6 - 1),
        num7=random.randint(10 ** 6, 10 ** 7 - 1),
        num9=random.randint(10 ** 8, 10 ** 9 - 1),
        num11=random.randint(10 ** 10, 10 ** 11 - 1),
    )


def make_image(spec: dict, idx: int) -> Image.Image:
    img = Image.new("RGB", (900, 620), spec["bg"])
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 880, 600], outline=(120, 120, 120), width=3)
    d.text((40, 34), spec["title"], fill=(20, 20, 20), font=_font(28))
    y = 100
    for f in spec.get("fields", []):
        d.text((40, y), _fmt(f, idx), fill=(40, 40, 40), font=_font(20))
        y += 38
    for _ in range(30):  # ruido para variar las muestras
        x, yy = random.randint(40, 860), random.randint(y + 10, 580)
        d.line([x, yy, x + random.randint(10, 60), yy], fill=(180, 180, 180))
    return img


def main(per_class: int = 40) -> None:
    for name, spec in SPECS.items():
        folder = DATASET / name
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(per_class):
            make_image(spec, i).save(folder / f"{name}_{i:03d}.jpg")
        print(f"{name}: {per_class} imagenes")
    print(f"\nDataset sintetico ({len(SPECS)} clases) en: {DATASET}")
    print("Recuerda: reemplazalo por documentos reales antes de produccion.")


if __name__ == "__main__":
    main()
