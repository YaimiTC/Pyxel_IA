# Apoderado de aduana — ODIN 2.0: pruebas de punta a punta

## Contexto del sistema

El sistema ODIN 2.0 gestiona procesos de importación para ENETEC S.A.
El **apoderado de aduana** es un usuario interno de Odoo que gestiona la
Declaración de Mercancía (DM) por orden de compra, una vez que el expediente
de documentos de entrada está aprobado por el comercial.

---

## Stack técnico

- Odoo 17 en Docker: contenedor `enetradex_odoo`, puerto `8469`
- Base de datos: `enetradex_dev`
- Addons: `C:\odoo_enetradex\addons\pyxel_enetradex_backend`
- DocValidator (IA): FastAPI en `http://host.docker.internal:8000/verify`

---

## Modelos involucrados

### `importation.process` — proceso de importación
| Campo | Descripción |
|-------|-------------|
| `stage_id` | Etapa del proceso; debe ser `TRÁMITES EN DESTINO` (id=4) |
| `en_request_approved` | True cuando la solicitud fue aprobada |
| `en_ready_for_customs` | Computed: True cuando BL/AWB + factura + lista de empaque están `approved` |
| `en_customs_agent_id` | Many2one → `res.users`: apoderado asignado al proceso |
| `en_customs_dm_done` | Computed: True cuando todas las DM tienen `dm_confirmed=True` |

### `pyxel.import.document` — documento del expediente
| Campo | Descripción |
|-------|-------------|
| `importation_id` | Many2one → `importation.process` |
| `purchase_order_id` | Many2one → `purchase.order` (solo docs de OC) |
| `document_key` | Clave técnica: `bl_awb`, `factura_comercial`, `lista_empaque`, `dm`, etc. |
| `display_type` | `line_section` para encabezados de OC, False para documentos reales |
| `portal_state` | `pending` → `in_review` → `approved` / `rejected` |
| `ai_state` | `pending` → `validating` → `passed` / `doubt` / `rejected` |
| `dm_number` | Número de DM (extraído por IA o ingresado manual) |
| `dm_container_number` | Contenedor (extraído por IA o manual) |
| `dm_cif_value` | Valor CIF en USD |
| `dm_arancel_total` | Total aranceles en USD |
| `dm_impuesto_circulacion` | Impuesto de circulación en USD |
| `dm_arancel_notes` | Notas arancelarias (texto libre) |
| `dm_extraction_state` | `pending` / `extracted` / `manual` |
| `dm_confirmed` | True cuando el apoderado confirma los datos de la DM |

### Relaciones One2many en `importation.process`
| Campo | Filtra |
|-------|--------|
| `en_import_process_doc_ids` | `purchase_order_id = False` (docs de la importación) |
| `en_import_oc_doc_ids` | `purchase_order_id != False` (docs de OC, incluye encabezados) |
| `en_import_dm_doc_ids` | `document_key = 'dm'` (una DM por cada OC) |

---

## Flujo completo del apoderado

```
1. Proveedor sube BL/AWB + Factura + Lista de empaque por portal
2. IA valida cada documento
3. Comercial aprueba los documentos clave
4. en_ready_for_customs = True → proceso aparece en "Trámites de aduana"
5. Apoderado se asigna al proceso
6. Apoderado sube PDF de la DM por cada OC
7. IA extrae campos dm_* del PDF
8. Apoderado revisa y corrige campos si es necesario
9. Apoderado confirma datos → dm_confirmed = True por cada OC
10. Cuando todas las DM están confirmadas → en_customs_dm_done = True
11. Proceso desaparece de "Trámites de aduana"
```

---

## Vista backend del apoderado

**Menú:** Importación → Trámites de aduana

**Filtro de la acción:**
```python
[
  ('stage_id.name', '=', 'TRÁMITES EN DESTINO'),
  ('en_ready_for_customs', '=', True),
  ('en_customs_dm_done', '=', False),
]
```

**Vista lista:** referencia, proveedor, cliente, apoderado asignado (avatar), DM lista (boolean)
- Fila en gris = tiene apoderado asignado, aún en proceso
- Fila en verde = todas las DM confirmadas (no debería aparecer por el filtro)

**Vista formulario — 2 pestañas:**

1. **Documentos de entrada** (readonly para el apoderado)
   - Sección BL/AWB: estado IA + estado aprobación + botón Ver
   - Sección por OC (encabezados P00010, P00011 en negrita): factura + lista con estados

2. **Declaración de Mercancía (DM)**
   - Banner de bloqueo si `en_ready_for_customs = False`
   - Tabla editable por OC: subir PDF → IA extrae campos → apoderado corrige → Confirmar
   - Sección de notas arancelarias

---

## Casos de prueba

---

### PRUEBA 1 — Proceso NO aparece en la lista del apoderado si faltan documentos

**Precondición:** proceso en etapa "TRÁMITES EN DESTINO" pero con BL/AWB o factura sin aprobar.

**Pasos:**
1. Ir a Importación → Trámites de aduana
2. Verificar que el proceso NO aparece

**Resultado esperado:** la lista está vacía o no contiene ese proceso.

**Verificación en BD:**
```sql
SELECT name, en_ready_for_customs, en_customs_dm_done
FROM importation_process
WHERE stage_id = 4;
```

---

### PRUEBA 2 — Proceso aparece cuando los documentos clave están aprobados

**Precondición:** proceso en etapa "TRÁMITES EN DESTINO" con:
- `en_request_approved = True`
- BL/AWB con `portal_state = 'approved'`
- Al menos una OC con factura + lista empaque `portal_state = 'approved'`

**Pasos:**
1. Ir a Importación → Trámites de aduana
2. Verificar que IMP00003 aparece en la lista

**Resultado esperado:**
- IMP00003 visible con columna "Apoderado asignado" vacía y "DM lista" = No

**Verificación en BD:**
```sql
SELECT name, en_ready_for_customs, en_customs_agent_id, en_customs_dm_done
FROM importation_process WHERE id = 3;
```

---

### PRUEBA 3 — Asignación del apoderado

**Pasos:**
1. Abrir IMP00003 desde Trámites de aduana
2. En el campo "Apoderado asignado" seleccionar un usuario interno
3. Guardar

**Resultado esperado:**
- El usuario aparece con su avatar en la lista
- La fila se muestra en gris (tiene apoderado, aún no terminó)
- El campo queda guardado en BD:

```sql
SELECT en_customs_agent_id FROM importation_process WHERE id = 3;
```

---

### PRUEBA 4 — Pestaña "Documentos de entrada" es solo lectura

**Pasos:**
1. Abrir IMP00003 en Trámites de aduana
2. Ir a pestaña "Documentos de entrada"
3. Intentar editar cualquier campo

**Resultado esperado:**
- Sección BL/AWB: muestra el archivo subido (PDF o link "Ver"), estado IA y estado aprobación — todo readonly
- Sección por OC: encabezados P00011 y P00010 en negrita, docs de factura y lista abajo con estados
- No hay botones de edición ni "Revisar"

---

### PRUEBA 5 — Subida de DM y extracción IA

**Precondición:** DocValidator corriendo en `http://host.docker.internal:8000/verify`

**Pasos:**
1. Abrir IMP00003 → pestaña "Declaración de Mercancía (DM)"
2. En la fila de P00011, clic en "Subir DM"
3. En la ficha que se abre, subir un PDF de DM válido
4. Esperar a que la IA procese (estado cambia a "Validando" → "Pasado"/"Duda")
5. Volver al formulario del apoderado

**Resultado esperado:**
- `attachment_id` del registro DM de P00011 apunta al PDF subido
- `dm_extraction_state` = `extracted`
- Campos `dm_number`, `dm_cif_value`, `dm_arancel_total`, `dm_impuesto_circulacion` tienen valores
- Botón "Ver DM" visible, botón "Subir DM" desaparece
- Botón "Confirmar" aparece en verde

**Verificación en BD:**
```sql
SELECT document_key, purchase_order_id, dm_number, dm_cif_value,
       dm_arancel_total, dm_extraction_state, dm_confirmed
FROM pyxel_import_document
WHERE importation_id = 3 AND document_key = 'dm';
```

---

### PRUEBA 6 — Corrección manual de campos DM

**Pasos:**
1. En la pestaña DM, hacer clic en la fila de P00011
2. Editar el campo "Nº DM" manualmente
3. Editar "CIF (USD)" manualmente
4. Guardar

**Resultado esperado:**
- Los valores quedan guardados
- `dm_extraction_state` puede quedar como `extracted` (la corrección no lo resetea)
- La sección de notas permite escribir texto libre

---

### PRUEBA 7 — Confirmación de DM por OC

**Pasos:**
1. Con la DM de P00011 subida y campos completos
2. Clic en botón "Confirmar" en la fila de P00011
3. Verificar cambio visual

**Resultado esperado:**
- `dm_confirmed = True` para esa fila
- La fila se muestra en verde en la tabla
- Botón "Confirmar" desaparece en esa fila
- El proceso AÚN aparece en la lista (falta confirmar DM de P00010)
- `en_customs_dm_done` sigue en False

**Verificación en BD:**
```sql
SELECT purchase_order_id, dm_confirmed
FROM pyxel_import_document
WHERE importation_id = 3 AND document_key = 'dm';
```

---

### PRUEBA 8 — Proceso desaparece cuando todas las DM están confirmadas

**Pasos:**
1. Confirmar también la DM de P00010
2. Ir a Importación → Trámites de aduana

**Resultado esperado:**
- `en_customs_dm_done = True`
- IMP00003 ya NO aparece en la lista del apoderado
- Si se quita el filtro ("DM lista = Todas"), sí aparece con estado verde

**Verificación en BD:**
```sql
SELECT name, en_customs_dm_done
FROM importation_process WHERE id = 3;
```

---

### PRUEBA 9 — Dos apoderados, sin conflicto

**Precondición:** crear IMP00004 en el mismo estado (stage=4, en_ready_for_customs=True, en_customs_dm_done=False)

**Pasos:**
1. Apoderado A abre IMP00003 y se asigna
2. Apoderado B abre IMP00004 y se asigna
3. Ambos ven su proceso en la lista

**Resultado esperado:**
- Cada apoderado ve ambos procesos en la lista
- La columna "Apoderado asignado" indica claramente quién trabaja cada uno
- Apoderado A trabaja IMP00003 sin interferir con IMP00004

---

### PRUEBA 10 — Banner de bloqueo cuando documentos no están aprobados

**Pasos:**
1. Crear un proceso en stage=4 pero con `en_ready_for_customs = False`
2. Forzar acceso directo al form (por URL o quitando el filtro de la acción)
3. Ir a pestaña "Declaración de Mercancía (DM)"

**Resultado esperado:**
- Se muestra el banner amarillo de advertencia:
  *"Los documentos de entrada aún no están aprobados. No es posible gestionar la DM hasta que el expediente esté completo."*
- La tabla de DM está oculta

---

## Script de datos de prueba

Para preparar IMP00003 en estado listo para el apoderado sin necesidad de aprobar manualmente:

```sql
-- 1. Aprobar documentos clave
UPDATE pyxel_import_document
SET ai_state='passed', ai_confidence=95,
    commercial_state='approved', portal_state='approved'
WHERE importation_id = 3
  AND document_key IN ('bl_awb', 'factura_comercial', 'lista_empaque');

-- 2. Activar flags del proceso
UPDATE importation_process
SET en_request_approved = true,
    en_ready_for_customs = true,
    en_customs_dm_done = false
WHERE id = 3;

-- 3. Verificar
SELECT p.name, p.en_ready_for_customs, p.en_customs_dm_done,
       d.document_key, d.purchase_order_id, d.portal_state
FROM importation_process p
JOIN pyxel_import_document d ON d.importation_id = p.id
WHERE p.id = 3
  AND d.document_key IN ('bl_awb','factura_comercial','lista_empaque')
ORDER BY d.purchase_order_id NULLS FIRST;
```

---

## Crear usuario de prueba — Apoderado de aduana

### Desde la interfaz de Odoo
1. Ir a **Ajustes → Usuarios → Nuevo**
2. Completar:
   - **Nombre:** Apoderado Aduana
   - **Correo electrónico:** apoderado@enetradex.cu
   - **Contraseña:** apoderado (cambiar en el primer acceso)
   - **Tipo de usuario:** Usuario interno
3. Guardar y enviar invitación (o establecer contraseña manualmente)

### Desde SQL (más rápido para pruebas)

```sql
-- 1. Crear el contacto (res.partner)
INSERT INTO res_partner (name, email, active, company_type, lang)
VALUES ('Apoderado Aduana', 'apoderado@enetradex.cu', true, 'person', 'es_ES')
RETURNING id;

-- 2. Crear el usuario vinculado al contacto (usar el id devuelto arriba)
INSERT INTO res_users (partner_id, login, active, share)
SELECT id, 'apoderado@enetradex.cu', true, false
FROM res_partner WHERE email = 'apoderado@enetradex.cu'
RETURNING id;

-- 3. Establecer contraseña "apoderado"
UPDATE res_users
SET password = crypt('apoderado', gen_salt('bf'))
WHERE login = 'apoderado@enetradex.cu';

-- 4. Verificar
SELECT u.id, u.login, p.name, u.active, u.share
FROM res_users u
JOIN res_partner p ON p.id = u.partner_id
WHERE u.login = 'apoderado@enetradex.cu';
```

### Desde Docker (comando directo)

```powershell
docker exec enetradex_postgres psql -U odoo -d enetradex_dev -c "
SELECT u.id, u.login, p.name
FROM res_users u
JOIN res_partner p ON p.id = u.partner_id
WHERE u.share = false
ORDER BY u.id DESC LIMIT 10;"
```

### Credenciales de acceso
| Campo | Valor |
|-------|-------|
| URL | http://localhost:8469 |
| Usuario | apoderado@enetradex.cu |
| Contraseña | apoderado |

---

## Comandos de apoyo

```powershell
# Ver logs en tiempo real mientras se prueba
docker logs enetradex_odoo -f --tail 50

# Ver estado de todos los docs DM
docker exec enetradex_postgres psql -U odoo -d enetradex_dev -c "
SELECT p.name proceso, po.name oc,
       d.dm_number, d.dm_cif_value, d.dm_extraction_state, d.dm_confirmed
FROM pyxel_import_document d
JOIN importation_process p ON p.id = d.importation_id
LEFT JOIN purchase_order po ON po.id = d.purchase_order_id
WHERE d.document_key = 'dm'
ORDER BY p.id, po.id;"

# Ver procesos visibles para el apoderado
docker exec enetradex_postgres psql -U odoo -d enetradex_dev -c "
SELECT name, en_ready_for_customs, en_customs_dm_done,
       en_customs_agent_id
FROM importation_process
WHERE stage_id = 4 AND en_ready_for_customs = true AND en_customs_dm_done = false;"
```
