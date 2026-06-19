"""Motor de CUMPLIMIENTO legal para acreditacion de PYMEs (MIPYME Cuba).

A diferencia del pipeline general (que solo clasifica el TIPO), aqui el sistema
actua como un primer filtro de abogacia: por cada documento produce un INFORME DE
CUMPLIMIENTO = la lista de TODO lo que NO cumple (cada hallazgo con su base legal y
severidad), para que la abogada lo revise.

Capas de verificacion:
  1) TEXTO  (capa de palabras/campos): frases obligatorias, NIT, folios, fechas.
  2) IMAGEN (cuño/firma): no se decide aqui; se marca "requiere verificacion visual".
  3) LOGICA (vigencia y cruces de NIT/razon social entre los 5 documentos).

Severidades: critico (no apto / posible nulidad), alto/medio (revisar), imagen
(verificacion visual pendiente).
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = BASE_DIR / "config" / "pyme_rules.json"

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    # Abreviaturas frecuentes en certificaciones.
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}

SEV_ICON = {"critico": "🔴", "alto": "🟡", "medio": "🟡", "imagen": "⚪"}


def load_rules() -> dict:
    with open(RULES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize_text(text: str) -> str:
    """Colapsa el texto ESPACIADO-POR-CARACTER que aparece en muchos escaneos
    cubanos ("E S C R I T U R A" -> "ESCRITURA", "O N A T" -> "ONAT") uniendo
    secuencias de tokens de un solo caracter. En texto normal apenas tiene efecto.
    Devuelve una version sin tildes y en minusculas, lista para matching robusto."""
    text = text.replace("\xa0", " ").replace(" ", " ").replace(" ", " ")
    # Unifica TODO espacio en blanco (incl. saltos de linea) antes de unir
    # caracteres: si no, "O N A T \n" no se colapsaba a "ONAT".
    text = re.sub(r"\s+", " ", text)
    out, buf = [], []
    for tok in text.split(" "):
        if len(tok) == 1 and tok.isalnum():
            buf.append(tok)
        else:
            if buf:
                out.append("".join(buf))
                buf = []
            out.append(tok)
    if buf:
        out.append("".join(buf))
    joined = " ".join(out)
    joined = re.sub(r"\s+", " ", joined)
    return _strip_accents(joined).lower()


def extract_text_from_pdf(pdf_path: str | Path) -> tuple[str, bool]:
    """Devuelve (texto, scanned). Lee la capa de texto del PDF con pymupdf. Si el
    documento es escaneado (capa de texto vacia/minima), scanned=True para que el
    llamador haga OCR (DocEnhancer + PaddleOCR sobre la portada renderizada)."""
    import fitz  # pymupdf

    doc = fitz.open(pdf_path)
    parts = [page.get_text("text") for page in doc]
    doc.close()
    raw = "\n".join(parts)
    scanned = len(re.sub(r"\s", "", raw)) < 40  # casi sin texto -> escaneado
    return raw, scanned


def _extract_fields(norm: str, campos: dict) -> dict:
    fields: dict = {}
    for name, pat in campos.items():
        m = re.search(pat, norm, re.IGNORECASE)
        if m:
            fields[name] = (m.group(1) if m.groups() else m.group(0)).strip()
    return fields


def _parse_fecha(norm: str) -> date | None:
    """Intenta encontrar y parsear una fecha (formato '12 de marzo de 2023' o
    dd/mm/aaaa). Devuelve la mas reciente encontrada (la emision suele ser la
    ultima fecha del documento)."""
    found: list[date] = []
    # "12 de marzo de 2023"  y tambien  "a los 16 dias del mes de junio, de 2025"
    patrones = [
        r"(\d{1,2})\s+de\s+([a-zñ]+)\.?\s+de\s+(\d{4})",
        r"(\d{1,2})\s*dias?\s+del\s+mes\s+de\s+([a-zñ]+),?\s+de\s+(\d{4})",
        r"(\d{1,2})\s+([a-zñ]+)\.?\s+(\d{4})",  # '9 ene 2026' / '9 enero 2026'
    ]
    for pat in patrones:
        for m in re.finditer(pat, norm):
            d, mes, y = int(m.group(1)), _MESES.get(m.group(2)), int(m.group(3))
            if mes:
                try:
                    found.append(date(y, mes, d))
                except ValueError:
                    pass
    # Numericas dd/mm/aa(aa) con separador / - o .  (también '9-01-26')
    for m in re.finditer(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\b", norm):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            found.append(date(y, mo, d))
        except ValueError:
            pass
    # ISO aaaa-mm-dd
    for m in re.finditer(r"\b(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})\b", norm):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            found.append(date(y, mo, d))
        except ValueError:
            pass
    return max(found) if found else None


def evaluate(text: str, doc_type: str, rules: dict, today: date | None = None,
             image_info: dict | None = None) -> dict:
    """Evalua un documento (ya con su texto extraido) contra las reglas del tipo.
    Devuelve el informe de cumplimiento: lista de hallazgos + veredicto + score.

    image_info (capa imagen, opcional): {digital, marker, ink_present, zone_crop}.
    Enriquece los checks de tipo 'imagen' (cuño/firma): si hay firma DIGITAL, el
    check queda satisfecho (verificable); si hay tinta en la zona de firmas, se
    marca como 'posible' con recorte para que la abogada lo confirme."""
    today = today or date.today()
    norm = normalize_text(text)
    tcfg = rules["tipos"].get(doc_type)
    if not tcfg:
        return {"doc_type": doc_type, "error": f"Tipo desconocido: {doc_type}"}

    image_info = image_info or {}
    img_digital = bool(image_info.get("digital"))
    img_ink = bool(image_info.get("ink_present"))

    fields = _extract_fields(norm, rules.get("campos", {}))
    fecha = _parse_fecha(norm)
    vig_dias = rules.get("no_adeudo_vigencia_dias", 90)

    findings: list[dict] = []
    crit_fail = alto_fail = imagen_pend = 0

    for chk in tcfg["checks"]:
        ctype, sev = chk["type"], chk["severity"]
        status, detail = "ok", ""

        if ctype == "keyword":
            hit = next((k for k in chk["any"] if _strip_accents(k).lower() in norm), None)
            if hit:
                detail = f"encontrado: '{hit}'"
            else:
                status = "fail"
                detail = "no aparece ninguna de: " + ", ".join(chk["any"][:4])
        elif ctype == "field":
            # La fecha usa el parser robusto (formatos legales cubanos), no el regex simple.
            val = fecha.isoformat() if (chk["field"] == "fecha" and fecha) else fields.get(chk["field"])
            if val:
                detail = f"{chk['field']}={val}"
            elif chk["field"] == "fecha":
                # No se pudo leer la fecha automaticamente -> NO es rechazo: lo confirma
                # la abogada visualmente (suele estar junto al cuño/firma).
                status = "imagen"
                detail = "No se pudo leer la fecha automaticamente — verificar en el documento"
            else:
                status = "fail"
                detail = f"no se detecto {chk['field']}"
        elif ctype == "vigencia":
            if not fecha:
                # Sin fecha legible: revision visual de la abogada (no rechazo).
                status = "imagen"
                detail = "Sin fecha legible — verificar vigencia en el documento"
            else:
                dias = (today - fecha).days
                if dias <= vig_dias:
                    detail = f"emitido hace {dias} dias (limite {vig_dias})"
                else:
                    status = "fail"
                    detail = f"VENCIDO: emitido hace {dias} dias (limite {vig_dias})"
        img_signal = ""
        if ctype == "imagen":
            status = "imagen"
            if img_digital:
                img_signal = "digital"
                detail = "Firma/cuño DIGITAL detectado en el documento — confirmar validez del certificado"
            elif img_ink:
                img_signal = "posible"
                detail = "Tinta de color detectada en la zona de firmas — confirmar cuño/firma en el recorte"
            else:
                img_signal = "ausente"
                detail = "No se detecto cuño/firma automaticamente — verificar manualmente"

        if status == "fail" and sev == "critico":
            crit_fail += 1
        elif status == "fail" and sev in ("alto", "medio"):
            alto_fail += 1
        elif status == "imagen" and img_signal != "digital":
            # La firma digital queda satisfecha; solo lo fisico/ausente sigue pendiente.
            imagen_pend += 1

        icon = "🟢"
        if status == "fail":
            icon = SEV_ICON.get(sev, "🟡")
        elif status == "imagen":
            icon = "🟢" if img_signal == "digital" else "⚪"

        findings.append({
            "id": chk["id"], "label": chk["label"], "severity": sev,
            "status": status, "base": chk["base"], "detail": detail,
            "img_signal": img_signal, "icon": icon,
        })

    if crit_fail:
        verdict = "no_apto"
    elif alto_fail or imagen_pend:
        verdict = "revisar"
    else:
        verdict = "apto"

    # Incumplimientos = lo que falla o sigue pendiente de confirmar (no lo digital).
    incumplimientos = [
        f for f in findings
        if f["status"] == "fail" or (f["status"] == "imagen" and f.get("img_signal") != "digital")
    ]
    total = len(findings)
    # La firma/cuño DIGITAL cuenta como satisfecho para el score.
    satisfechos = sum(
        1 for f in findings
        if f["status"] == "ok" or (f["status"] == "imagen" and f.get("img_signal") == "digital")
    )
    score = round(100 * satisfechos / total) if total else 0

    return {
        "doc_type": doc_type,
        "label": tcfg["label"],
        "verdict": verdict,        # apto / revisar / no_apto
        "score": score,
        "fecha_emision": fecha.isoformat() if fecha else None,
        "fields": fields,
        "findings": findings,
        "incumplimientos": incumplimientos,
        "imagen": {
            "digital": img_digital,
            "marker": image_info.get("marker", ""),
            "ink_present": img_ink,
            "zone_crop": image_info.get("zone_crop", ""),
        },
        "resumen": {
            "criticos": crit_fail, "advertencias": alto_fail,
            "verificacion_visual": imagen_pend, "ok": satisfechos, "total": total,
        },
    }


def format_report(res: dict) -> str:
    """Render de texto del informe de cumplimiento (para CLI / logs / revisor)."""
    if res.get("error"):
        return res["error"]
    icon = {"apto": "🟢 APTO", "revisar": "🟡 REVISAR", "no_apto": "🔴 NO APTO"}[res["verdict"]]
    lines = [
        f"=== {res['label']}  ->  {icon}  (score {res['score']}%)",
        f"    NIT={res['fields'].get('nit','-')}  fecha={res.get('fecha_emision') or '-'}",
        "    Hallazgos:",
    ]
    for f in res["findings"]:
        mark = {"ok": "✓", "fail": "✗", "imagen": "○"}[f["status"]]
        lines.append(f"      {f['icon']} {mark} {f['label']}  [{f['base']}]  — {f['detail']}")
    r = res["resumen"]
    lines.append(
        f"    Resumen: {r['criticos']} criticos · {r['advertencias']} advertencias · "
        f"{r['verificacion_visual']} verif.visual · {r['ok']}/{r['total']} OK"
    )
    return "\n".join(lines)


def cross_validate(resultados: list[dict]) -> list[dict]:
    """Cruce entre los documentos del expediente: el NIT debe ser el MISMO en todos
    los que lo declaran. Devuelve hallazgos a nivel de expediente."""
    nits = {}
    for r in resultados:
        nit = (r.get("fields") or {}).get("nit")
        if nit:
            nits.setdefault(nit, []).append(r.get("label", r.get("doc_type")))
    hallazgos = []
    if len(nits) > 1:
        detalle = "; ".join(f"{n} en [{', '.join(docs)}]" for n, docs in nits.items())
        hallazgos.append({
            "id": "nit_cruzado", "severity": "critico", "status": "fail",
            "label": "El NIT no coincide entre los documentos del expediente",
            "base": "coherencia del expediente", "detail": detalle, "icon": "🔴",
        })
    return hallazgos
