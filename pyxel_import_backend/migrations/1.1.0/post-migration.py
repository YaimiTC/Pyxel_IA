# -*- coding: utf-8 -*-
# Migración 1.0.0 → 1.1.0
# Después del upgrade, los registros pyxel.tipo.envase ya existen (cargados desde XML).
# Mapeamos los valores de respaldo a los nuevos IDs Many2one.


def migrate(cr, version):
    value_to_name = {
        'isotanque_20': 'Isotanque 20 pies',
        'isotanque_40': 'Isotanque 40 pies',
        'ibc': 'IBC',
    }

    cr.execute("SELECT id, name FROM pyxel_tipo_envase")
    name_to_id = {row[1]: row[0] for row in cr.fetchall()}

    cr.execute("""
        SELECT id, tipo_envase_bak FROM sale_order_line
        WHERE tipo_envase_bak IS NOT NULL AND tipo_envase_bak != ''
    """)
    for line_id, bak_value in cr.fetchall():
        name = value_to_name.get(bak_value)
        if name and name in name_to_id:
            cr.execute(
                "UPDATE sale_order_line SET tipo_envase = %s WHERE id = %s",
                (name_to_id[name], line_id),
            )

    cr.execute("ALTER TABLE sale_order_line DROP COLUMN IF EXISTS tipo_envase_bak")
