# INCIDENCIA: Vista del apoderado de aduana muestra datos incorrectos

**Contexto del sistema:**
- Proyecto ODIN 2.0 — ENETEC S.A.
- Odoo 17 en Docker, contenedor `enetradex_odoo`, BD `enetradex_dev`
- Módulos afectados: `pyxel_import_backend`, `pyxel_enetradex_backend`
- Modelo: `importation.process`

---

## Problema reportado

El apoderado de aduana accedía al mismo formulario que el comercial, con pestañas
y campos que no le corresponden (Importation Load, Purchase Orders, Import costs, etc.).

El comercial y el apoderado deben ver **vistas completamente diferentes** del mismo modelo.

## Comportamiento esperado

| Rol | Vista |
|-----|-------|
| Comercial | Formulario completo con todas las pestañas |
| Apoderado de aduana | Solo: cabecera resumida + "Documentos de entrada" + "Declaración de Mercancía (DM)" |

---

## Solución aplicada

### Principio

- La vista del comercial **no se toca** — permanece como la vista por defecto del módulo.
- Para el apoderado se crea una **vista formulario standalone** (no heredada) con `priority=100`.
- La acción `action_apoderado_aduana` fuerza esa vista explícitamente con `view_ids`.

### 1. Crear vista y acción del apoderado

Archivo: `pyxel_enetradex_backend/views/apoderado_views.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <!-- Vista lista -->
    <record id="view_apoderado_process_tree" model="ir.ui.view">
        <field name="name">importation.process.apoderado.tree</field>
        <field name="model">importation.process</field>
        <field name="arch" type="xml">
            <tree string="Trámites de aduana"
                  decoration-success="en_customs_dm_done"
                  decoration-muted="en_customs_agent_id and not en_customs_dm_done">
                <field name="name" string="Referencia"/>
                <field name="provider_id" string="Proveedor"/>
                <field name="customer_id" string="Cliente"/>
                <field name="en_customs_agent_id" string="Apoderado asignado"
                       widget="many2one_avatar_user" optional="show"/>
                <field name="en_customs_dm_done" string="DM lista" widget="boolean" optional="show"/>
            </tree>
        </field>
    </record>

    <!-- Vista formulario exclusiva del apoderado (standalone, NO hereda) -->
    <record id="view_apoderado_process_form" model="ir.ui.view">
        <field name="name">importation.process.apoderado.form</field>
        <field name="model">importation.process</field>
        <field name="priority">100</field>
        <field name="arch" type="xml">
            <form string="Trámites de aduana">
                <sheet>
                    <div class="oe_title">
                        <h1><field name="name" readonly="1"/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="provider_id" readonly="1"/>
                            <field name="customer_id" readonly="1"/>
                            <field name="stage_id" readonly="1"/>
                        </group>
                        <group>
                            <field name="import_type_id" readonly="1"/>
                            <field name="en_ready_for_customs" readonly="1" widget="boolean_toggle"/>
                            <field name="en_customs_agent_id" widget="many2one_avatar_user"/>
                            <field name="en_customs_dm_done" readonly="1" widget="boolean_toggle"/>
                        </group>
                    </group>

                    <notebook>
                        <!-- Pestaña 1: Documentos de entrada (solo lectura) -->
                        <page string="Documentos de entrada" name="ap_input_docs">
                            <div class="alert alert-info" role="alert">
                                Documentos requeridos para iniciar los trámites de aduana.
                                Solo lectura — los sube el proveedor y los revisa el comercial.
                            </div>
                            <separator string="BL / AWB (Proceso de importación)"/>
                            <field name="en_import_process_doc_ids" readonly="1"
                                   domain="[('document_key', '=', 'bl_awb')]">
                                <tree create="0" delete="0" edit="0">
                                    <field name="document_label" string="Documento"/>
                                    <field name="attachment_id" string="Archivo"/>
                                    <field name="ai_state" string="Dictamen IA" widget="badge"
                                           decoration-success="ai_state == 'passed'"
                                           decoration-warning="ai_state == 'doubt'"
                                           decoration-danger="ai_state == 'rejected'"
                                           decoration-info="ai_state == 'validating'"/>
                                    <field name="portal_state" string="Estado" widget="badge"
                                           decoration-success="portal_state == 'approved'"
                                           decoration-danger="portal_state == 'rejected'"
                                           decoration-warning="portal_state == 'in_review'"/>
                                    <button name="action_view_document" type="object"
                                            string="Ver" class="btn-link"
                                            invisible="not attachment_id"/>
                                </tree>
                            </field>
                            <separator string="Documentos por Orden de Compra"/>
                            <field name="en_import_oc_doc_ids" readonly="1">
                                <tree create="0" delete="0" edit="0"
                                      decoration-bf="display_type == 'line_section'"
                                      decoration-success="portal_state == 'approved' and not display_type"
                                      decoration-danger="portal_state == 'rejected' and not display_type"
                                      decoration-warning="portal_state == 'in_review' and not display_type"
                                      decoration-muted="portal_state in ('pending','optional') and not display_type">
                                    <field name="display_type" column_invisible="1"/>
                                    <field name="attachment_id" column_invisible="1"/>
                                    <field name="document_label" string="Documento / OC" readonly="1"/>
                                    <field name="ai_state" string="Dictamen IA" widget="badge"
                                           invisible="display_type == 'line_section'"
                                           decoration-success="ai_state == 'passed'"
                                           decoration-warning="ai_state == 'doubt'"
                                           decoration-danger="ai_state == 'rejected'"/>
                                    <field name="portal_state" string="Estado" widget="badge"
                                           invisible="display_type == 'line_section'"
                                           decoration-success="portal_state == 'approved'"
                                           decoration-danger="portal_state == 'rejected'"
                                           decoration-warning="portal_state == 'in_review'"/>
                                </tree>
                            </field>
                        </page>

                        <!-- Pestaña 2: Declaración de Mercancía (editable) -->
                        <page string="Declaración de Mercancía (DM)" name="ap_dm">
                            <div class="alert alert-warning" role="alert"
                                 invisible="en_ready_for_customs">
                                Los documentos de entrada aún no están aprobados.
                                No es posible gestionar la DM hasta que el expediente esté completo.
                            </div>
                            <field name="en_import_dm_doc_ids"
                                   invisible="not en_ready_for_customs">
                                <tree editable="bottom"
                                      decoration-success="dm_confirmed"
                                      decoration-muted="not attachment_id">
                                    <field name="purchase_order_id" string="OC" readonly="1"/>
                                    <field name="attachment_id" string="PDF DM"/>
                                    <field name="ai_state" string="IA" widget="badge"
                                           decoration-success="ai_state == 'passed'"
                                           decoration-warning="ai_state == 'doubt'"
                                           decoration-danger="ai_state == 'rejected'"
                                           invisible="not attachment_id"/>
                                    <field name="dm_extraction_state" string="Extracción" widget="badge"
                                           decoration-info="dm_extraction_state == 'extracted'"
                                           decoration-warning="dm_extraction_state == 'manual'"/>
                                    <field name="dm_number" string="Nº DM"/>
                                    <field name="dm_container_number" string="Contenedor"/>
                                    <field name="dm_cif_value" string="CIF (USD)"/>
                                    <field name="dm_arancel_total" string="Aranceles (USD)"/>
                                    <field name="dm_impuesto_circulacion" string="Imp. Circulación (USD)"/>
                                    <field name="dm_confirmed" string="Confirmado" readonly="1"/>
                                    <button name="action_view_document" type="object"
                                            string="Ver DM" class="btn-link"
                                            invisible="not attachment_id"/>
                                    <button name="action_confirm_dm" type="object"
                                            string="Confirmar" class="btn-success"
                                            invisible="not attachment_id or dm_confirmed"/>
                                </tree>
                            </field>
                            <separator string="Notas arancelarias"
                                       invisible="not en_ready_for_customs"/>
                            <field name="en_import_dm_doc_ids" invisible="not en_ready_for_customs">
                                <tree editable="bottom" create="0" delete="0">
                                    <field name="purchase_order_id" string="OC" readonly="1"/>
                                    <field name="dm_arancel_notes" string="Notas"/>
                                </tree>
                            </field>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <!-- Acción con vistas explícitas (fuerza el uso de las vistas del apoderado) -->
    <record id="action_apoderado_aduana" model="ir.actions.act_window">
        <field name="name">Trámites de aduana</field>
        <field name="res_model">importation.process</field>
        <field name="view_mode">tree,form</field>
        <field name="domain">[('stage_id.name','=','TRÁMITES EN DESTINO'),('en_ready_for_customs','=',True),('en_customs_dm_done','=',False)]</field>
        <field name="view_ids" eval="[(5,0,0),
            (0,0,{'view_mode':'tree','view_id':ref('view_apoderado_process_tree')}),
            (0,0,{'view_mode':'form','view_id':ref('view_apoderado_process_form')})]"/>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No hay procesos pendientes de despacho aduanero.
            </p>
        </field>
    </record>

    <!-- Menú -->
    <menuitem id="menu_apoderado_aduana"
              name="Trámites de aduana"
              parent="pyxel_import_backend.menu_importation_root"
              action="action_apoderado_aduana"
              sequence="25"/>

</odoo>
```

### 2. Registrar el archivo en el manifest

Archivo: `pyxel_enetradex_backend/__manifest__.py`

Asegurarse de que `views/apoderado_views.xml` esté en la lista `data`:

```python
'data': [
    ...
    'views/apoderado_views.xml',
    ...
],
```

### 3. Actualizar módulo

```bash
docker exec enetradex_odoo odoo -u pyxel_enetradex_backend -d enetradex_dev --stop-after-init
docker restart enetradex_odoo
```

### 4. Forzar vista en la acción (fix en BD si el módulo ya existía)

Si la acción ya existía en BD y Odoo no actualiza `view_id` correctamente:

```bash
# 1. Obtener el ID de la vista y la acción
docker exec enetradex_postgres psql -U odoo -d enetradex_dev -c "
SELECT id, name FROM ir_ui_view
WHERE name = 'importation.process.apoderado.form';

SELECT id, name FROM ir_act_window
WHERE name = 'Trámites de aduana';"

# 2. Forzar la vista en la acción (sustituir los IDs reales)
docker exec enetradex_postgres psql -U odoo -d enetradex_dev -c "
UPDATE ir_act_window SET view_id = <ID_VISTA_FORM> WHERE id = <ID_ACCION>;"
```

> **Nota:** Este fix en BD se necesita cuando el módulo tenía previamente otra vista
> heredada o cuando Odoo cachea el `view_id` anterior y no lo actualiza con `-u`.

---

## Crear usuario y contacto para el apoderado de aduana

### Desde la interfaz de Odoo (recomendado)

1. Ir a **Ajustes → Usuarios → Nuevo**
2. Nombre: `Apoderado Aduana`
3. Email: `apoderado@enetradex.cu` (o el que corresponda)
4. Contraseña: `apoderado`
5. Perfil: **Usuario interno** (o el grupo que corresponda)
6. Guardar y activar

### Desde la consola de Odoo (alternativa rápida)

```bash
docker exec enetradex_odoo odoo shell -d enetradex_dev --no-http << 'EOF'
env['res.users'].create({
    'name': 'Apoderado Aduana',
    'login': 'apoderado',
    'password': 'apoderado',
    'email': 'apoderado@enetradex.cu',
    'groups_id': [(6, 0, [env.ref('base.group_user').id])],
})
env.cr.commit()
EOF
```

---

## Advertencia: priority=100 y la vista del comercial

La vista del apoderado tiene `priority=100`. Esto significa que si el comercial
abre un proceso desde la URL directa (sin pasar por la acción), verá esta vista.

Para evitarlo, la vista del comercial debe cargarse **siempre a través de su propia
acción** (`action_importation_process`), que no tiene `view_id` forzado y por
tanto Odoo usa la vista con menor prioridad (la del comercial, priority=16).

El botón "Trámites de aduana" del menú usa `action_apoderado_aduana`, que sí
fuerza la vista del apoderado. Mientras no se modifique esa acción, el flujo
es correcto.

---

## Verificación

1. Iniciar sesión como **comercial** → Imports → abrir un proceso → debe verse el formulario
   completo con todas las pestañas.
2. Iniciar sesión como **apoderado** → Trámites de aduana → abrir un proceso → debe verse
   solo "Documentos de entrada" y "Declaración de Mercancía (DM)".
3. Si el comercial entra por el menú **Trámites de aduana**, verá la vista del apoderado
   (esto es intencional — esa acción es exclusiva del flujo de aduana).

---

*Incidencia resuelta — ODIN 2.0 · ENETEC S.A. · Junio 2026*
