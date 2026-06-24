# INCIDENCIA: Campo "Tipo de carga" editable y sin valor por defecto

**Contexto del sistema:**
- Proyecto ODIN 2.0 — ENETEC S.A.
- Odoo 17 en Docker, contenedor `enetradex_odoo`, BD `enetradex_dev`
- Módulo afectado: `pyxel_import_backend`
- Modelo: `importation.load`, campo `cargo_type` (Selection: dry/reefer)
- Ruta del proyecto: `D:\trabajo\Pyxel\IA\ENETEC_traspaso\ENETEC_traspaso\odoo-enetradex\addons\`

---

## Problema reportado

El campo "Tipo de carga" aparece editable en el formulario de carga, permitiendo
al operador seleccionar "Refrigerated" por error. ENETEC solo opera cargas secas (dry).
Además, algunos registros existentes pueden tener el campo vacío.

---

## Solución aplicada

### 1. Modelo — agregar default

Archivo: `pyxel_import_backend/models/importation_load.py`

```python
cargo_type = fields.Selection([
    ('dry', 'Dry'),
    ('reefer', 'Refrigerated'),
], string='Load Type', default='dry')
```

### 2. Vista form de carga

Archivo: `pyxel_import_backend/views/view_importation_load.xml`

```xml
<field name="cargo_type" invisible="hide_cargo_type" readonly="1"/>
```

### 3. Vista progress (tree + form inline)

Archivo: `pyxel_import_backend/views/view_importation_progress.xml`

```xml
<!-- en el tree -->
<field name="cargo_type" optional="show" readonly="1"/>

<!-- en el form inline -->
<field name="cargo_type" invisible="hide_cargo_type" readonly="1"/>
```

### 4. Actualizar módulo en Docker

```bash
docker exec enetradex_odoo odoo -u pyxel_import_backend -d enetradex_dev --stop-after-init
docker restart enetradex_odoo
```

---

## Corrección de datos existentes

### Verificar estado actual

```sql
SELECT cargo_type, COUNT(*) FROM importation_load GROUP BY cargo_type;
```

### Corregir registros vacíos

```sql
UPDATE importation_load
SET cargo_type = 'dry'
WHERE cargo_type IS NULL OR cargo_type = '';
```

### Verificar después de la corrección

```sql
SELECT cargo_type, COUNT(*) FROM importation_load GROUP BY cargo_type;
-- Resultado esperado: solo 1 fila con cargo_type = 'dry'
```

### Ejecutar desde Docker

```bash
docker exec enetradex_postgres psql -U odoo -d enetradex_dev -c \
  "UPDATE importation_load SET cargo_type = 'dry' WHERE cargo_type IS NULL OR cargo_type = '';"

docker exec enetradex_postgres psql -U odoo -d enetradex_dev -c \
  "SELECT cargo_type, COUNT(*) FROM importation_load GROUP BY cargo_type;"
```

---

## Criterio de aceptación

- El campo "Tipo de carga" aparece en gris (deshabilitado) con valor "Dry" en todos los formularios
- No es posible cambiarlo desde la interfaz
- Todos los registros existentes tienen `cargo_type = 'dry'`
- Los nuevos registros se crean automáticamente con `dry`

---

*Incidencia resuelta — ODIN 2.0 · ENETEC S.A. · Junio 2026*
