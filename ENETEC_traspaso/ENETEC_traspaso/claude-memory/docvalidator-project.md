---
name: docvalidator-project
description: Proyecto DocValidator — servicio local de validación de documentos por IA que Odoo consumirá
metadata: 
  node_type: memory
  type: project
  originSessionId: 0852c323-f81a-4b41-90ea-80b200e8aa52
---

El usuario construye un sistema de **verificación documental con IA + revisión humana** (estilo KYC/KYB) para clientes que suben carnet de identidad, certificación legal y documentación de empresa. La IA hace el **primer filtro** (¿es el tipo correcto / es basura?) y luego una persona revisa. Objetivo declarado: filtrar documentos "que no son ni se parecen".

Arquitectura en dos piezas:
1. **DocValidator** (en construcción primero, en `C:\Proyectos\DocValidator`): microservicio **FastAPI** local que recibe `POST /verify {file_b64, expected_type}` y devuelve veredicto 🟢passed/🟡doubt/🔴rejected. Stack: EfficientNetV2 (clasificador, PyTorch+timm), PaddleOCR (OCR), OpenCV (calidad). El "entrenamiento" = soltar variantes en `dataset/<tipo>/` y correr `python -m training.train`. Tipos/reglas en `config/document_types.json`.
2. **Módulo Odoo** (construido, en `C:\Proyectos\doc_verification`): Odoo 17/18 **Community**, depende de base/mail/portal (sin OCA). Modelos: `document.type`, `document.verification.request/line/log`, `verification.engine` (conector HTTP). Tiene backend (expedientes + revisión humana + auditoría), portal de cliente (subir/ver estado), grupos Revisor/Admin, semáforo 🟢🟡🔴. URL del servicio en param `doc_verification.engine_url`. Sintaxis validada (py_compile + XML), pero NO instalado aún en un Odoo real (no hay Odoo en esta PC).

**Odoo en marcha (Docker):** existe un stack Docker del usuario en `C:\Proyectos\odoo17\` (creado 2026-06-13, contenedores `odoo17-app` odoo:17.0 + `odoo17-db` postgres:16, puertos 8069/8072, volúmenes `odoo17_odoo-db-data`/`odoo17_odoo-web-data`). NO crear un stack paralelo — usar ese. El módulo `doc_verification` se monta vía bind `C:/Proyectos/doc_verification -> /mnt/extra-addons/doc_verification` (añadido al compose). BD Odoo: `docverif` (login admin/admin). Param `doc_verification.engine_url` = `http://host.docker.internal:8000` (desde el contenedor el host NO es 127.0.0.1). DocValidator corre en el host con uvicorn.

**OCR activo:** PaddleOCR 2.8.1 + paddlepaddle 2.6.2 (CPU) instalados en el venv. Modelos cacheados en `C:\Users\Home\.paddleocr` (det en + rec latin + cls) — **para producción offline hay que pre-descargar/copiar esa carpeta**. `DOCVAL_ENABLE_OCR=true`. Servicio uvicorn corre en background (relanzar: `cd C:\Proyectos\DocValidator; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`). Primera llamada OCR descarga modelos (lenta); luego rápida.

**Portal del cliente (vivo):** experiencia completa scoped a carné cubano. Usuario demo portal: `cliente@demo.cu` / `cliente123`. Flujo: /my → "Subir mi carné" (/my/verifications/new crea expediente) → sube imagen → el controller llama action_process_ai automáticamente (validación al subir) → estado "En revisión" → back-office aprueba → cliente ve "APROBADO". Verificado por HTTP end-to-end. Lecciones QWeb Odoo17: no usar dicts inline en `#{...}` de t-attf (usar t-set + t-att-class); t-field NO va directo en `<td>` (envolver en `<span>`). El pipeline `_decide` ahora combina clasificador+OCR: si el clasificador falla pero OCR reconoce keywords → 'doubt' (no rechazo). Carné cubano: keywords incluyen "cuba"; clasificador entrenado con sintético estilo "REPUBLICA DE CUBA - CARNE DE IDENTIDAD". Para reconocer carnés REALES con fiabilidad hace falta reentrenar con muestras reales del usuario (NO se scrapean IDs reales de Google por privacidad).

Restricciones clave: **todo offline/air-gapped** en producción (datos sensibles no salen). Estado a 2026-06-14: **SISTEMA COMPLETO end-to-end con OCR + PORTAL DEL CLIENTE verificado en Odoo** — expediente VER/2026/00001: veredicto 🟢 passed, clasif. carnet 100%, campo numero extraído ("76641873226"), "Documento válido". Regex de numero en config cambiado a `\d{11}` (el OCR concatena "Numero" sin espacio). Falta: cargar documentos reales y reentrenar, pulir flujo de revisión/portal, validaciones extra (vigencia, nombre coincide).

## Estado a 2026-06-15 (handoff para retomar)

**Portal del cliente reescrito a MODO DEMO sin login.** Entrada única: **`http://localhost:8069/carnet`** (auth=public, NO pide login). Endpoints en `controllers/portal.py` (todos auth=public + sudo, usan partner por defecto "Cliente Demo" vía `_demo_partner()`):
- `/carnet` → formulario limpio (reusa un borrador vacío o crea uno).
- `/carnet/validate` (POST) → paso 1: valida la foto con IA **sin guardar**, devuelve JSON.
- `/carnet/submit` (POST) → paso 2: crea expediente+línea, corre IA, lo deja `to_review` (al backend).
- `/my/verification/<id>/image/<line>` → sirve la foto (sin control de acceso, demo).

**Flujo front (2 pasos, sin recargar):** seleccionar foto → validación automática (stepper paso 2, muestra Apto/datos, sin enviar) → botón **"Subir y validar"** (fetch a /carnet/submit → paso 3 "Revisión") → botón **"Nueva comprobación"** (limpia todo por JS, vuelve a paso 1). La lógica JS está **inline en `views/portal_templates.xml`** (NO como asset: los bundles `assets_frontend_lazy` de Odoo 17 no ejecutaban el init a tiempo; el inline sí). Construye el resultado con `textContent` (sin HTML en JS) para no romper el XML; único char escapado: `&lt;`.

**Backend (revisor):** ve la foto del carné — miniatura en el tree de líneas + imagen grande al abrir la línea (campo `doc_image = Binary related a attachment_id.datas`, widget image). Botones Aprobar/Rechazar en el header del expediente (solo visibles con ancho suficiente; Odoo los colapsa en pantallas estrechas).

**Extracción IA:** `numero` (`\d{11}`), `nombre`, `vencimiento` vía `field_patterns` en `config/document_types.json`. Con carné cubano REAL, nombre/vencimiento salen "—" (los regex están afinados al sintético) → **pendiente afinar al formato real**.

**Preview en vivo dentro de Claude:** `scripts/odoo_proxy.py` (proxy a Odoo 8069) + `.claude/launch.json` → `preview_start("odoo")`; sirve para ver/operar el portal en el panel de Claude. `scripts/web_shot.py` toma screenshots con el Chrome del sistema (Playwright `channel=chrome`; el Chromium propio no descarga en esta red). SIEMPRE verificar UIs así (ver [[verify-web-designs]]).

**Git:** repo privado **github.com/ntdiaz87-sudo/validador-de-documentos**, todo pusheado al 2026-06-15. Workflow local-first (ver [[git-workflow]]). Backend Odoo LIMPIO (0 expedientes, secuencia reiniciada → próximo VER/2026/00001).

**Próximos pasos sugeridos:** (1) afinar extracción nombre/vencimiento del carné cubano real; (2) maquetar/cuidar la vista del revisor en el backend; (3) cargar dataset real del usuario y reentrenar; (4) opcional: detección de fraude/anti-falsificación.

Ver [[dev-machine-no-nvidia]], [[git-workflow]] y [[verify-web-designs]].
