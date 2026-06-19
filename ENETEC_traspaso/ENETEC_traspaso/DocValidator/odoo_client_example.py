"""Ejemplo de como Odoo (o cualquier cliente) llama al servicio DocValidator.
En el modulo Odoo, esta logica vive en el modelo abstracto 'verification.engine'.
Aqui se muestra como script independiente para probar la integracion."""
from __future__ import annotations

import base64
import sys

import requests

ENGINE_URL = "http://127.0.0.1:8000/verify"


def verify_file(path: str, expected_type: str) -> dict:
    with open(path, "rb") as fh:
        file_b64 = base64.b64encode(fh.read()).decode()
    resp = requests.post(
        ENGINE_URL,
        json={"file_b64": file_b64, "expected_type": expected_type},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python odoo_client_example.py <ruta_imagen> <tipo_esperado>")
        print("Ej:  python odoo_client_example.py foto.jpg carnet_identidad")
        raise SystemExit(1)
    result = verify_file(sys.argv[1], sys.argv[2])
    print(f"Veredicto : {result['verdict']}")
    print(f"Tipo IA   : {result['classified_type']} ({result['score']}%)")
    print(f"Calidad   : {result['quality']['score']}")
    print(f"Campos    : {result['fields']}")
    print(f"Motivos   : {result['reasons']}")
