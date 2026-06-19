# Expediente de documentos de importación — ODIN 2.0

## Contexto del sistema

El sistema ODIN 2.0 gestiona procesos de importación para ENETEC S.A.
Cada proceso (`importation.process`) tiene un expediente estructurado de documentos
con validación IA y revisión comercial, replicando el patrón del expediente de acreditación.

---

## Modelos involucrados

### `pyxel.import.document`
Documento individual del expediente. Dos tipos:

| Campo | Descripción |
|-------|-------------|
| `importation_id` | Many2one → `importation.process` (siempre requerido) |
| `purchase_order_id` | Many2one → `purchase.order` (solo para docs de OC; null para docs de la importación) |
| `document_key` | Clave técnica del tipo de documento |
| `document_label` | Nombre visible |
| `is_required` | Obligatorio u opcional |
| `display_type` | `'line_section'` para filas cabecera de OC; `False` para docs normales |
| `attachment_id` | Many2one → `ir.attachment` (el archivo subido) |
| `ai_state` | Estado IA: `pending / validating / passed / doubt / rejected` |
| `ai_confidence` | Porcentaje de confianza IA |
| `commercial_state` | Estado comercial: `blocked / to_review / approved / rejected` |
| `portal_state` | Computed: `pending / validating / in_review / approved / rejected / optional` |
| `source_type` | `file` (subido) o `camera` (fotos ensambladas) |
| `page_ids` | One2many → `pyxel.import.document.page` (fotos antes de ensamblar) |

### `pyxel.import.document.page`
Página fotográfica acumulada antes de generar el PDF.

| Campo | Descripción |
|-------|-------------|
| `document_id` | Many2one → `pyxel.import.document` |
| `page_number` | Número de página |
| `image` | Binary (foto JPEG/PNG) |
| `quality_score` | Calidad estimada por IA |

### Campos añadidos a `importation.process`
```python
en_import_document_ids      # todos los docs del expediente
en_import_process_doc_ids   # solo docs de la importación (purchase_order_id = False)
en_import_oc_doc_ids        # solo docs de OC (purchase_order_id != False)
en_import_doc_count         # total de docs
en_import_doc_approved      # total aprobados
en_ready_for_customs        # True cuando bl_awb + factura_comercial + lista_empaque aprobados
```

---

## Catálogos de documentos

### Documentos del proceso de importación (1 set por proceso)
| Clave | Etiqueta | Obligatorio |
|-------|----------|-------------|
| `bl_awb` | BL / AWB | Sí |
| `cert_calidad` | Certificado de calidad | No |
| `cert_exportacion` | Certificado de exportación | No |
| `cert_origen` | Certificado de origen | No |

### Documentos por Orden de Compra (1 set por OC vinculada al proceso)
| Clave | Etiqueta | Obligatorio |
|-------|----------|-------------|
| `oferta` | Oferta firmada | Sí |
| `factura_comercial` | Factura comercial | Sí |
| `lista_empaque` | Lista de empaque | Sí |
| `dm` | Declaración de Mercancía (DM) | No |
| `permisos_regulatorios` | Permisos por entidades regulatorias | No |

---

## Creación automática del expediente

### Al crear un proceso de importación
```python
# En importation_process.py → create()
env['pyxel.import.document'].build_expediente(records)
```
Crea los 4 slots de documentos de la importación.

### Al vincular una OC al proceso
```python
# En en_purchase_order.py → create() y write()
env['pyxel.import.document'].build_oc_expediente(purchase_orders)
```
Crea una fila cabecera (`display_type='line_section'`, `sequence=0`) con el nombre de la OC
y los 5 slots de documentos (`sequence=10..50`).
No duplica si la OC ya tiene slots.

### Migración manual (procesos existentes)
```python
# En importation_process.py
def action_create_import_expediente(self):
    env['pyxel.import.document'].build_expediente(self)
```
El botón "Crear expediente" aparece en la pestaña cuando `en_import_doc_count == 0`.

---

## Flujo de validación (2 pasos)

```
PROVEEDOR sube doc
       ↓
[IA] DocValidator /verify
       ↓
ai_state = passed / doubt → commercial_state = to_review
ai_state = rejected        → comercial no se desbloquea
ai_state = validating      → DocValidator no disponible (sigue en cola)
       ↓
[COMERCIAL] Revisar → Aprobar / Rechazar
       ↓
portal_state = approved / rejected
```

### DocValidator
- URL: `http://host.docker.internal:8000/verify`
- Payload: `{ "file_b64": "...", "expected_type": "bill_of_lading" }`
- Respuesta: `{ "verdict": "apto|revisar|no_apto", "confidence": 0.95, "reason": "..." }`
- Si no responde: documento queda en `ai_state = 'validating'` (no bloquea el flujo)

---

## Vista backend — pestaña "Expediente de documentos"

### Sección 1: Documentos de la importación
Tree con columnas: Documento | Dictamen IA | Confianza (%) | Comercial | Estado proveedor | [Revisar] [Ver]

- **Revisar**: abre la vista dedicada `view_pyxel_import_document_form` (form completo con visor PDF, widget cámara, dictamen IA, revisión comercial)
- **Ver**: abre el archivo en nueva pestaña (visible solo si tiene attachment)
- Colores de fila: verde=aprobado, rojo=rechazado, naranja=en revisión, gris=pendiente/opcional

### Sección 2: Documentos por Orden de Compra
Mismo tree con columna "Documento / OC".
Las filas de cabecera (`display_type='line_section'`) muestran el nombre de la OC en negrita
sin badges ni botones.
Las filas de documentos siguen debajo, agrupadas visualmente por OC.

---

## Vista de revisión (`view_pyxel_import_document_form`)

Formulario dedicado accesible desde el botón "Revisar":

```
[Aprobar] [Rechazar] [Reabrir]   Estado: [badge portal_state]

sheet:
  ┌── Visor PDF (widget=pdf_viewer) ─────────────────────┐
  │  document_file (related a attachment_id.datas)        │
  └───────────────────────────────────────────────────────┘

  ┌── Widget cámara (widget=camera_capture) ─────────────┐
  │  Tomar foto | Subir archivo                           │
  │  [miniaturas de páginas acumuladas]                   │
  │  [Generar PDF y aplicar]                              │
  └───────────────────────────────────────────────────────┘

  ┌── Dictamen IA ────────────────────────────────────────┐
  │  ai_state | ai_confidence | ai_quality                │
  │  ai_reason (texto)                                    │
  │  ai_extracted_data (JSON OCR)                         │
  └───────────────────────────────────────────────────────┘

  ┌── Revisión Comercial ─────────────────────────────────┐
  │  commercial_state | commercial_reason                 │
  └───────────────────────────────────────────────────────┘
```

---

## Widget cámara OWL (`camera_capture`)

Archivo: `pyxel_enetradex_backend/static/src/js/camera_field.js`
Template: `pyxel_enetradex_backend/static/src/xml/camera_field.xml`

**Flujo:**
1. El revisor toma fotos o sube archivos (PDF/imagen)
2. Se acumulan en estado local del componente (lista de páginas con preview)
3. Al pulsar "Generar PDF y aplicar":
   - Llama `orm.call('pyxel.import.document', 'action_assemble_from_images', [[id], [b64...]])`
   - El servidor fusiona con PyPDF2 (PDFs) + Pillow (imágenes) en un único PDF
   - Guarda como `ir.attachment`, actualiza `attachment_id`
   - Llama al DocValidator automáticamente
4. El componente recarga el record (`this.props.record.load()`)

---

## Pruebas de punta a punta

### PRE-REQUISITO
- Odoo corriendo en `http://localhost:8469`
- Al menos 1 proceso de importación con expediente creado
- Al menos 1 OC vinculada al proceso (`purchase_order_id.importation_id`)
- Credenciales admin: admin / admin (o las del entorno)

---

### TEST 1 — Estructura del expediente al crear proceso

**Pasos:**
1. Ir a Importación → Procesos → Nuevo
2. Completar campos mínimos (cliente, proveedor, tipo)
3. Guardar

**Resultado esperado:**
- Se crea automáticamente el expediente con 4 slots (BL/AWB, Cert. calidad, Cert. exportación, Cert. origen)
- Todos en estado `ai_state=pending`, `commercial_state=blocked`, `portal_state=pending/optional`
- La pestaña "Expediente de documentos" muestra la sección "Documentos de la importación" con las 4 filas
- La sección "Documentos por Orden de Compra" está vacía

**Verificación SQL:**
```sql
SELECT document_key, ai_state, commercial_state, portal_state
FROM pyxel_import_document
WHERE importation_id = <ID_PROCESO>
ORDER BY purchase_order_id NULLS FIRST, sequence;
```

---

### TEST 2 — Creación de docs de OC al vincular una OC

**Pasos:**
1. Abrir un proceso existente → pestaña "Órdenes de compra"
2. Crear una nueva OC con `importation_id` = el proceso actual

**Resultado esperado:**
- Se crean automáticamente 6 registros para esa OC:
  - 1 fila cabecera (`display_type='line_section'`, `document_key='_section'`, `document_label=nombre_OC`)
  - 5 slots de documentos: oferta, factura_comercial, lista_empaque, dm, permisos_regulatorios
- En la pestaña "Expediente de documentos", sección "Documentos por Orden de Compra", aparece la OC en negrita como cabecera y sus 5 docs debajo

**No duplica:** si se edita la OC nuevamente (write sin cambiar importation_id), no se crean docs adicionales.

---

### TEST 3 — Subida de archivo y validación IA

**Pasos:**
1. Abrir el proceso → pestaña "Expediente de documentos"
2. Click en "Revisar" en la fila "BL / AWB"
3. En el formulario dedicado, usar "Subir archivo" (widget=camera_capture) para subir un PDF
4. Click en "Generar PDF y aplicar"

**Resultado esperado:**
- El PDF aparece en el visor izquierdo
- `ai_state` cambia a `validating` (y a `passed/doubt/rejected` si DocValidator responde)
- Si DocValidator no está disponible: queda en `validating` (no error al usuario)
- Si IA aprueba: `commercial_state` pasa de `blocked` a `to_review`
- `portal_state` refleja el estado combinado

**Verificación:**
```sql
SELECT ai_state, ai_confidence, commercial_state, portal_state
FROM pyxel_import_document
WHERE document_key = 'bl_awb' AND importation_id = <ID>;
```

---

### TEST 4 — Revisión comercial

**Pasos:**
1. En la vista de revisión del documento (tras subir archivo y que IA pase)
2. Click en "Aprobar"

**Resultado esperado:**
- `commercial_state = approved`
- `portal_state = approved`
- Fila verde en el listado del expediente
- Si todos los obligatorios están aprobados: mensaje en chatter "Expediente completo"

**Rechazo:**
1. Click en "Rechazar" sin `commercial_reason` → error de validación
2. Escribir motivo → Click "Rechazar"
3. `commercial_state = rejected`, `portal_state = rejected`
4. El proveedor verá el motivo en el portal

---

### TEST 5 — Widget cámara (tomar foto)

**Pasos:**
1. Abrir la vista de revisión de un documento
2. Click en "📷 Tomar foto" → pedir acceso a cámara
3. Tomar 2-3 fotos con "Capturar"
4. Click "✖ Cerrar" para cerrar la cámara
5. Verificar miniaturas visibles
6. Click "📄 Generar PDF y aplicar"

**Resultado esperado:**
- Las fotos se convierten a PDF en el servidor (Pillow → PyPDF2)
- El PDF aparece en el visor
- La IA se llama automáticamente
- Las miniaturas desaparecen del widget tras el éxito

---

### TEST 6 — `en_ready_for_customs`

**Condición:** `en_request_approved = True` Y los docs `bl_awb`, `factura_comercial`, `lista_empaque` tienen `portal_state = approved`.

**Pasos:**
1. Aprobar la solicitud del proceso
2. Subir y aprobar BL/AWB (importación), Factura comercial y Lista de empaque (OC)
3. Revisar el campo "Lista para despacho aduanero" en la pestaña del expediente

**Resultado esperado:**
- `en_ready_for_customs = True`
- Campo verde/activo en la vista

---

### TEST 7 — Procesos existentes sin expediente

**Pasos:**
1. Abrir un proceso creado antes de la migración
2. Ir a pestaña "Expediente de documentos"
3. Si el expediente está vacío → click en botón "Crear expediente"

**Resultado esperado:**
- Se crean los 4 slots de importación
- Si el proceso tiene OCs vinculadas, también se crean sus slots automáticamente

---

## Estado visual del expediente (referencia)

```
DOCUMENTOS DE LA IMPORTACIÓN
┌──────────────────────┬─────────────┬──────────┬──────────┬──────────────────┬─────────┐
│ Documento            │ Dictamen IA │Confianza │Comercial │ Estado proveedor │         │
├──────────────────────┼─────────────┼──────────┼──────────┼──────────────────┼─────────┤
│ BL / AWB             │ [Pendiente] │   0,00   │[No aplica│ [Pendiente]      │ Revisar │
│ Certificado calidad  │ [Pendiente] │   0,00   │[No aplica│ [Opcional]       │ Revisar │
│ Certificado exportac.│ [Pendiente] │   0,00   │[No aplica│ [Opcional]       │ Revisar │
│ Certificado origen   │ [Pendiente] │   0,00   │[No aplica│ [Opcional]       │ Revisar │
└──────────────────────┴─────────────┴──────────┴──────────┴──────────────────┴─────────┘

DOCUMENTOS POR ORDEN DE COMPRA
┌──────────────────────┬─────────────┬──────────┬──────────┬──────────────────┬─────────┐
│ Documento / OC       │ Dictamen IA │Confianza │Comercial │ Estado proveedor │         │
├──────────────────────┴─────────────┴──────────┴──────────┴──────────────────┴─────────┤
│ P00010  [negrita, sin badges]                                                           │
├──────────────────────┬─────────────┬──────────┬──────────┬──────────────────┬─────────┤
│ Oferta firmada       │ [Pendiente] │   0,00   │[No aplica│ [Pendiente]      │ Revisar │
│ Factura comercial    │ [Pendiente] │   0,00   │[No aplica│ [Pendiente]      │ Revisar │
│ Lista de empaque     │ [Pendiente] │   0,00   │[No aplica│ [Pendiente]      │ Revisar │
│ Declaración Mercancía│ [Pendiente] │   0,00   │[No aplica│ [Opcional]       │ Revisar │
│ Permisos regulatorios│ [Pendiente] │   0,00   │[No aplica│ [Opcional]       │ Revisar │
├──────────────────────┴─────────────┴──────────┴──────────┴──────────────────┴─────────┤
│ P00011  [negrita, sin badges]                                                           │
├──────────────────────┬─────────────┬──────────┬──────────┬──────────────────┬─────────┤
│ Oferta firmada       │ [Pendiente] │   0,00   │[No aplica│ [Pendiente]      │ Revisar │
│ ...                  │             │          │          │                  │         │
└──────────────────────┴─────────────┴──────────┴──────────┴──────────────────┴─────────┘
```

---

## Archivos clave modificados

| Archivo | Cambio |
|---------|--------|
| `pyxel_enetradex_backend/models/import_document.py` | Modelo principal, catálogos, build_expediente, build_oc_expediente, DocValidator, widget cámara |
| `pyxel_enetradex_backend/models/importation_process.py` | Campos en_import_*_doc_ids, en_ready_for_customs |
| `pyxel_enetradex_backend/models/en_purchase_order.py` | Hook create/write → build_oc_expediente |
| `pyxel_enetradex_backend/models/__init__.py` | Import de en_purchase_order |
| `pyxel_enetradex_backend/views/en_backend_views.xml` | Pestaña expediente con 2 secciones |
| `pyxel_enetradex_backend/views/import_document_views.xml` | Vista form de revisión |
| `pyxel_enetradex_backend/static/src/js/camera_field.js` | Widget OWL cámara |
| `pyxel_enetradex_backend/static/src/xml/camera_field.xml` | Template OWL cámara |
| `pyxel_enetradex_backend/security/ir.model.access.csv` | Permisos pyxel.import.document y .page |
| `pyxel_enetradex_website/controllers/portal_import.py` | Portal proveedor /my/despacho |
| `pyxel_enetradex_website/views/portal_import.xml` | Plantilla portal |
| `pyxel_enetradex_website/static/src/js/import_camera.js` | Cámara vanilla JS portal |
