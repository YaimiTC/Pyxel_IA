# INCIDENCIA: Campo Naviera/Aerolínea/Transitoria no aparece o tiene etiqueta incorrecta

**Contexto del sistema:**
- Proyecto ODIN 2.0 — ENETEC S.A.
- Odoo 17 en Docker, contenedor `enetradex_odoo`, BD `enetradex_dev`
- Módulo afectado: `pyxel_import_backend`
- Modelo: `importation.load`
- Ruta del proyecto: `D:\trabajo\Pyxel\IA\ENETEC_traspaso\ENETEC_traspaso\odoo-enetradex\addons\`

---

## Problema reportado

En el formulario de carga (modal desde el proceso de importación), los campos
de transporte marítimo/aéreo no aparecen correctamente según el tipo de importación,
y las etiquetas en español son incorrectas:

- `shipping_company` mostraba "Empresa de transporte" en lugar de "Naviera"
- `transit_agency` mostraba "Agencia de tránsito" en lugar de "Transitoria"

## Comportamiento esperado

| Tipo de importación | Campos visibles |
|---------------------|-----------------|
| Ocean Freight | Naviera + Transitoria |
| Air Freight | Aerolínea |
| On Site | Ninguno |

La visibilidad la controlan los flags `show_shipping_company`, `show_airline`,
`show_transit_agency` del modelo `import.type` (Configuración → Tipos de importación).

---

## Solución aplicada

### 1. Modelo — corregir etiquetas y agregar campos computed

Archivo: `pyxel_import_backend/models/importation_load.py`

**Etiquetas corregidas:**
```python
shipping_company = fields.Char(string='Naviera')
airline = fields.Char(string='Aerolínea')
transit_agency = fields.Char(string='Transitoria')
```

**Campo related store=True para que onchange funcione:**
```python
import_type_id = fields.Many2one(
    comodel_name='import.type',
    related='importation_id.import_type_id',
    string='IIT', store=True)
```

**Campos computed para visibilidad en modal de nuevo registro:**
```python
show_shipping_company = fields.Boolean(
    string='Mostrar Naviera',
    compute='_compute_show_transport', store=False)
show_airline = fields.Boolean(
    string='Mostrar Aerolínea',
    compute='_compute_show_transport', store=False)
show_transit_agency = fields.Boolean(
    string='Mostrar Transitoria',
    compute='_compute_show_transport', store=False)

@api.depends('importation_id', 'importation_id.import_type_id')
def _compute_show_transport(self):
    for record in self:
        import_type = record.importation_id.import_type_id
        record.show_shipping_company = import_type.show_shipping_company if import_type else False
        record.show_airline = import_type.show_airline if import_type else False
        record.show_transit_agency = import_type.show_transit_agency if import_type else False

@api.onchange('importation_id')
def _onchange_importation_id(self):
    self._inverse_boolean_value()
    self._compute_show_transport()
```

**Depends del método `_inverse_boolean_value` actualizado:**
```python
@api.depends('import_type_id', 'importation_id', 'importation_id.import_type_id')
def _inverse_boolean_value(self):
    for record in self:
        ...
        import_type = record.import_type_id or record.importation_id.import_type_id
        if import_type:
            ...
```

### 2. Vista form inline (modal desde el proceso)

Archivo: `pyxel_import_backend/views/view_importation_progress.xml`

```xml
<group string="Transport">
    <field name="hide_shipping_company" invisible="1"/>
    <field name="hide_airline" invisible="1"/>
    <field name="hide_transit_agency" invisible="1"/>
    <field name="shipping_company" invisible="hide_shipping_company"/>
    <field name="airline" invisible="hide_airline"/>
    <field name="transit_agency" invisible="hide_transit_agency"/>
    ...
</group>
```

### 3. Vista form independiente de la carga

Archivo: `pyxel_import_backend/views/view_importation_load.xml`

```xml
<group string="Transport">
    <field name="hide_shipping_company" invisible="1"/>
    <field name="hide_airline" invisible="1"/>
    <field name="hide_transit_agency" invisible="1"/>
    <field name="shipping_company" invisible="hide_shipping_company"/>
    <field name="airline" invisible="hide_airline"/>
    <field name="transit_agency" invisible="hide_transit_agency"/>
    ...
</group>
```

### 4. Corregir etiquetas en español en BD

Las traducciones al español quedaron con los valores anteriores en BD.
Ejecutar para corregirlas:

```bash
docker exec enetradex_postgres psql -U odoo -d enetradex_dev -c "
UPDATE ir_model_fields
SET field_description = '{\"en_US\": \"Naviera\", \"es_ES\": \"Naviera\"}'
WHERE model='importation.load' AND name='shipping_company';

UPDATE ir_model_fields
SET field_description = '{\"en_US\": \"Transitoria\", \"es_ES\": \"Transitoria\"}'
WHERE model='importation.load' AND name='transit_agency';"
```

### 5. Actualizar módulos y reiniciar

```bash
docker exec enetradex_odoo odoo -u pyxel_import_backend -d enetradex_dev --stop-after-init
docker restart enetradex_odoo
```

---

## Verificación

```sql
-- Confirmar etiquetas corregidas
SELECT name, field_description
FROM ir_model_fields
WHERE model='importation.load'
AND name IN ('shipping_company', 'airline', 'transit_agency');

-- Confirmar flags por tipo de importación
SELECT name, show_shipping_company, show_airline, show_transit_agency
FROM import_type;
```

**Resultado esperado de los flags:**

| name | show_shipping_company | show_airline | show_transit_agency |
|------|-----------------------|--------------|---------------------|
| Ocean Freight | t | | t |
| Air Freight | | t | |
| On Site | | | |

---

## Criterio de aceptación

- Ocean Freight → aparece "Naviera" y "Transitoria" en el modal de carga
- Air Freight → aparece "Aerolínea"
- On Site → no aparece ninguno
- Las etiquetas en español son correctas en todos los formularios

---

*Incidencia resuelta — ODIN 2.0 · ENETEC S.A. · Junio 2026*
