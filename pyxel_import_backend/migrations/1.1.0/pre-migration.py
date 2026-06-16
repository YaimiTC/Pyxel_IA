# -*- coding: utf-8 -*-
# Migración 1.0.0 → 1.1.0
# Se ejecuta antes de que Odoo altere el esquema.
# 1. Elimina los ir.model.fields.selection del campo tipo_envase para evitar
#    el crash en _process_end (el campo ya es Many2one en Python, ondelete=str).
# 2. Guarda los valores actuales del campo en una columna de respaldo.
# 3. Limpia la columna para que ALTER VARCHAR→INTEGER no falle.


def migrate(cr, version):
    # --- 1. Eliminar selection values viejos ---
    cr.execute("""
        SELECT s.id FROM ir_model_fields_selection s
        JOIN ir_model_fields f ON f.id = s.field_id
        WHERE f.model = 'sale.order.line' AND f.name = 'tipo_envase'
    """)
    selection_ids = [row[0] for row in cr.fetchall()]

    if selection_ids:
        # Quitar los xml-id que los referencian para evitar IntegrityErrors
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE model = 'ir.model.fields.selection'
              AND res_id = ANY(%s)
        """, (selection_ids,))
        cr.execute(
            "DELETE FROM ir_model_fields_selection WHERE id = ANY(%s)",
            (selection_ids,)
        )

    # --- 2. Respaldar y limpiar la columna tipo_envase ---
    cr.execute("""
        ALTER TABLE sale_order_line
        ADD COLUMN IF NOT EXISTS tipo_envase_bak VARCHAR
    """)
    cr.execute("""
        UPDATE sale_order_line
        SET tipo_envase_bak = tipo_envase
        WHERE tipo_envase IS NOT NULL AND tipo_envase != ''
    """)
    # Poner NULL para que ALTER TABLE varchar→integer no falle
    cr.execute("UPDATE sale_order_line SET tipo_envase = NULL")
