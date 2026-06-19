---
name: pyme-acreditacion
description: "Nuevo caso de uso — acreditación de PYMEs (MIPYME Cuba): 5 documentos reales escaneados, mismo sistema que carné/BL"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0852c323-f81a-4b41-90ea-80b200e8aa52
---

Tercer caso de uso del Validador de Documentos: **acreditación de PYMEs (MIPYME) en Cuba**. La PYME entrega **5 documentos requeridos** y el sistema (mismo principio: IA primer filtro + revisión humana) valida que cada uno sea el correcto.

**Los 5 documentos** (PDF REALES escaneados, en `C:\Proyectos\DocValidator\Pyme\` — datos sensibles, GITIGNORED):
1. Certifico de Registro Mercantil
2. Escritura notarial (constitución)
3. Identificación Fiscal (NIT/RC)
4. No Adeudo (ONAT, no debe impuestos)
5. Contrato de cuentas (bancarias)
~20 PDFs reales (3-5/clase). Algunos multipágina.

**Diferencias vs carné/BL:** PDF escaneados (no fotos), documentos de TEXTO muy parecidos entre sí (oficiales cubanos con membrete/cuño), POCAS muestras reales, y es un EXPEDIENTE con varios documentos (no uno suelto). Siempre llevan **preprocesado con DocEnhancer** (enderezar, contraste, denoise, super-resolución) antes de evaluar.

**DISEÑO ACORDADO (2026-06-16):**
1. **Expediente con checklist de los 5** documentos (progreso X/5; se aprueba la acreditación completa).
2. **Detección: OCR (palabras clave del título) PRINCIPAL + CNN de apoyo** (por similitud visual y pocas muestras).
3. **Modelo PYME SEPARADO** (clasificador dedicado a las 5 clases + basura), aparte del de carné/BL.

**Pipeline por documento:** PDF→imagen (portada) → DocEnhancer (preproc) → clasifica (CNN) + OCR (keywords/campos: NIT, razón social, fecha, nº inscripción) → veredicto OCR-weighted (🟢/🟡/🔴). Avanzado: validación cruzada (mismo NIT/empresa entre documentos). Interfaz nueva `/pyme` (multi-doc checklist) front + vista del revisor en backend.

**Estado:** diseño acordado; PENDIENTE implementar. Fases: 1) dataset (portadas de PDFs + reglas OCR), 2) entrenar modelo PYME + veredicto OCR, 3) config DocValidator + integrar DocEnhancer, 4) interfaz /pyme, 5) pruebas con los reales.

## Corpus legal estudiado (2026-06-16) — base para verificar CUMPLIMIENTO

El usuario quiere que el sistema actúe como experto legal y verifique que cada documento CUMPLE lo regulado (folios, cuños, firmas, vigencias, NIT), no solo el tipo. Leyes descargadas en `DocValidator/Pyme/_legal/` (gitignored): `notariado.pdf` (Ley del Notariado 175/2025), `mipyme_goc2021_o94.pdf` (Decreto-Ley 46/47/48/49 MIPYME), `registro_mercantil_dl226.pdf` (DL 226). Se extraen con pymupdf (en DocEnhancer/.venv).

Elementos formales obligatorios por documento (base legal):
- **Escritura notarial** (Ley Notariado): nº protocolo/folio, CUÑO de notaría + FIRMA y signo del notario, FIRMAS de comparecientes, lugar/fecha, fe de conocimiento. NULIDAD si falta identidad/firma del notario o firma de comparecientes. La nueva Ley 175 rige desde 7-ene-2026 (escrituras reales del usuario son 2022-23, formato anterior → entrenar con ambos).
- **Cert. Registro Mercantil** (DL226 + Reglamento Res.230/2002): "REGISTRO MERCANTIL"+"CERTIFICO", tomo/folio/hoja/asiento, CUÑO del registro + FIRMA del registrador, denominación social, NIT.
- **Identificación Fiscal**: NIT 11 dígitos, "Registro de Contribuyentes"/ONAT/ONEI, razón social, domicilio fiscal.
- **No Adeudo** (ONAT Modelo C-04): "NO ADEUDO"+"CERTIFICO"+ONAT, NIT, fecha, CUÑO ONAT + FIRMA del director municipal. VIGENCIA: la fija la entidad acreditadora (PENDIENTE confirmar plazo).
- **Contrato de cuenta** (privado, BANDEC/BPA): banco, nº cuenta, moneda CUP/USD, titular=razón social, firmas+cuño del banco.

Corpus descargado: + `decreto308.pdf` (Decreto 308 procedimientos tributarios; art. 56 = certificaciones ONAT: Inscripción, Residencia Fiscal, Adeudos Fiscales, gravadas con sello del timbre). Hallazgo: la VIGENCIA del No Adeudo NO está en la ley tributaria → la fija la ENTIDAD ACREDITADORA (configurable, PENDIENTE que el usuario lo confirme). Falta solo el Reglamento RM (Res.230/2002) — no hay PDF directo (la web da 403/expirado).

OBJETIVO confirmado por el usuario: al evaluar cada documento, el sistema debe LISTAR TODO LO QUE NO CUMPLE (cada hallazgo con su base legal) = un INFORME DE CUMPLIMIENTO para que lo revise la ABOGADA. Verificación en 3 capas: (1) OCR/texto = frases obligatorias + nº folio/protocolo/asiento + NIT + fechas; (2) imagen = CUÑO (región circular) y FIRMA (trazo manuscrito); (3) lógica = vigencia + NIT/razón social CRUZADO igual en los 5. Salida = lista de hallazgos por documento (✓/✗/⚠) + score + "requiere revisión".

## Fase 2 IMPLEMENTADA (2026-06-16) — motor de cumplimiento

Hecho y validado contra los 5 documentos reales:
- `DocValidator/config/pyme_rules.json`: 5 tipos con checks calibrados (keyword/field/vigencia/imagen), severidad (critico/alto/medio/imagen) + base legal por check; campos regex (nit 11 díg, fecha, tomo/folio/asiento, cuenta); `no_adeudo_vigencia_dias=90`.
- `DocValidator/app/pyme_compliance.py`: `normalize_text` (colapsa texto espaciado-por-carácter "O N A T"→"ONAT", unifica saltos de línea, quita tildes), `extract_text_from_pdf` (capa pymupdf; si <40 chars → scanned=True → OCR), `_parse_fecha` (2 formatos: "12 de marzo de 2023" Y "a los 16 días del mes de junio, de 2025"), `evaluate` (produce findings + veredicto apto/revisar/no_apto + score), `cross_validate` (NIT igual entre docs), `format_report`.
- `DocValidator/training/eval_pyme.py`: runner que extrae los ZIP, mapea carpeta→tipo, evalúa y muestra el informe. pymupdf instalado en DocValidator/.venv.

VIGENCIA RESUELTA: el propio documento ONAT lo declara — **90 días (3 meses) territorio nacional / 180 días internacional**. Ya no es pregunta pendiente. (El No Adeudo real de prueba salió 🔴 NO APTO correctamente: emitido 16-jun-2025, vencido a 365 días.)

Resultados reales: Identificación Fiscal 🟢 100%; Registro Mercantil 🟡 71% (solo cuño/firma pendientes de verif. visual); Contrato BANDEC 🟡 (OCR ok); Escritura 🟡 (OCR de portada sparse, 140 chars — pendiente OCR multipágina/DocEnhancer); No Adeudo 🔴 vencido. Hallazgo: NIT 11 díg colisiona con nº de Carné (en TCP/persona natural el NIT ES el carné → válido).

## Fases 3 y 4 IMPLEMENTADAS (2026-06-16) — servicio + interfaz Odoo

**Fase 3 (servicio):** `DocValidator/app/pyme_pipeline.py` (verify_pyme: PDF b64→texto capa/OCR→motor; verify_expediente: 5 docs + cruce NIT + estado global). Endpoints en `app/main.py`: `POST /pyme/verify`, `/pyme/expediente`, `/pyme/verify-upload`.

**Fase 4 (Odoo, módulo doc_verification):** TODO end-to-end y verificado con los PDF reales.
- Front portal `/pyme` (auth public, modo demo): checklist de los 5 docs, carga PDF + validación en vivo (`POST /pyme/add`→`action_process_ai`→motor), progreso X/5, badge 🟢/🟡/🔴 por doc, botón "Enviar a revisión de la abogada" (`POST /pyme/finalize`). Expediente aislado por `request.session['pyme_req_id']`.
- Vista del revisor (backend, ficha del documento): grupo "Informe de cumplimiento legal (para la abogada)" con `compliance_html` = tabla de hallazgos (✓/✗/○) + detalle + base legal + resumen. Badge `pyme_verdict` en la lista.
- `models/verification_line.py`: campos `compliance_json`, `pyme_verdict`, `compliance_html` (compute, Markup); `_process_pyme()` + branch en `action_process_ai` para `PYME_TYPES`. Veredicto→ai_result: apto→passed, revisar→doubt, no_apto→rejected.
- `models/verification_engine.py`: `verify_pyme_b64()`→`/pyme/verify`. 5 `document.type` nuevos en data (codes = claves pyme_rules.json).
- `controllers/portal.py`: PYME_DOCS, rutas /pyme, /pyme/add, /pyme/finalize.
- `scripts/pyme_demo_shot.py`: demo Playwright (sube los 5 por la UI).

INFRA: doc_verification montado en odoo17-app (`C:/Proyectos/doc_verification:/mnt/extra-addons/doc_verification`). engine_url real en BD = `http://host.docker.internal:8000` (NO 127.0.0.1, que apunta al contenedor). DocValidator NO auto-arranca: `cd DocValidator; .venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`. pymupdf instalado en DocValidator/.venv. Tras cambios Python: actualizar módulo (`docker exec odoo17-app odoo -u doc_verification -d docverif --stop-after-init --no-http`) y `docker restart odoo17-app`. DB docverif, admin/admin, partner demo cliente@demo.cu.

## Fase 5 IMPLEMENTADA (2026-06-16) — capa imagen cuño/firma

`DocValidator/app/pyme_image.py`: (1) `digital_trust_from_text(text)` detecta firma/cuño DIGITAL por marcadores en el texto ("Firmado digitalmente", "firma digital", "certificad", "c=cu", etc.) — señal FIABLE en PDFs nativos firmados. (2) `analyze_pdf(pdf_bytes)` mide tinta de color en la zona de firmas (40% inferior, `_colored_ink_mask` con s>50; la tinta de los cuños cubanos es AZUL hue~100-120, saturación moderada) y devuelve `zone_crop` (recorte base64 de la zona de firmas) para que la abogada confirme de un vistazo. SE DESCARTÓ HoughCircles (disparaba sobre cada renglón de texto) y la detección de blob circular (los sellos escaneados son de trazo fino, se fragmentan; no fiable sin falsos positivos).

Enfoque honesto: la visión NO decide algo legalmente crítico; localiza/recorta y la abogada confirma. `pyme_compliance.evaluate(...,image_info)` enriquece los checks tipo "imagen": DIGITAL→satisfecho (verde, suma al score, no pendiente); tinta física→"posible" (⚪ con recorte); ausente→verificar manual. El informe lleva `imagen{digital,marker,ink_present,zone_crop}`. `compliance_html` pinta la señal y muestra el recorte al pie.

Resultado real end-to-end (Odoo): Registro Mercantil e Identif. Fiscal (firmados digitalmente) → 🟢 APTO 100% (antes 🟡 71%/100%); No Adeudo 57→86% pero sigue 🔴 NO APTO (vigencia vencida = crítico, bien); Escritura/Contrato (físicos) → 🟡 con recorte de la zona de firmas. Hallazgo: los 5 docs reales resultaron ser híbridos — varios son PDF NATIVOS firmados digitalmente (no escaneos puros). Demo visual: `scripts/pyme_demo_shot.py`.

LAS 5 FASES COMPLETAS Y COMMITEADAS (8ed9689, a070fef, 0929833, 60c4a2a + Fase 1). Sistema PYME funcional end-to-end.

## Clasificador CNN + mejoras OCR/realce IMPLEMENTADO (2026-06-16, commit a5bdbca)

**Clasificador PYME separado (CNN de apoyo, OCR sigue PRINCIPAL):**
- `training/prep_pyme_dataset.py`: expande las 20 muestras renderizando TODAS las páginas de cada PDF real (hasta 6, dpi 150) + clase `_basura` (~35, negativos del dataset principal: carné/BL/factura) → `dataset_pyme_full/` (gitignored). 
- `training/train.py` parametrizado: `--dataset --out`. Modelo PYME = `models/classifier_pyme.pt`+`.json` (gitignored, regenerable). Entrenado en GPU RTX 3060, 40 epochs, 100% train (dataset chico → overfit, pero es solo apoyo). Comando: `python -m training.train --dataset dataset_pyme_full --out classifier_pyme --epochs 40 --batch 8`.
- `pipeline._cnn_support()`: la CNN confirma el tipo o emite ADVERTENCIA suave (no bloquea, baja apto→revisar) si con conf≥75% ve un tipo distinto al declarado. Degrada a 'unknown' sin modelo. Los 5 reales → clasificados correctos al 100%. Config: `pyme_model_path`/`pyme_classes_path`.

**Mejoras de lectura (escaneados):**
- `_pdf_text`: OCR MULTIPÁGINA (hasta 4 págs, no solo portada). Escritura: 140→~9900 chars, ahora pasa protocolo/doy fe/comparecientes (38→62%). Contrato: 1203→14676 chars (60→80%).
- `_maybe_enhance`: realza cada página con DocEnhancer `/enhance` si `DOCVAL_ENHANCER_URL` configurado (en `.env` = http://127.0.0.1:8800), antes del OCR. Degrada con elegancia si DocEnhancer no está. DocEnhancer se arranca: `cd DocEnhancer; .venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8800`.

CASO PYME COMPLETO: 5 fases + clasificador + mejoras, todo end-to-end y verificado con los reales. Veredictos finales: Registro Mercantil/Identif.Fiscal 🟢 APTO 100%; Contrato 🟡 80%; Escritura 🟡 62%; No Adeudo 🔴 NO APTO (vigencia vencida). Commits: 8ed9689, a070fef, 0929833, 60c4a2a, a5bdbca.

Relacionado con [[docvalidator-project]].
