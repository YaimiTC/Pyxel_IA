from odoo import models, fields, api
from datetime import datetime


class SaleOrderProcessCustom(models.Model):
    _inherit = "sale.order.process"

    start_year = fields.Char(
        string="Año Inicio",
        compute='_compute_years',
        store=True,
        readonly=True
    )
    end_year = fields.Char(
        string="Año Fin",
        compute='_compute_years',
        store=True,
        readonly=True
    )

    @api.depends('sale_order_ids.date_order', 'importation_id.date_import_closed')
    def _compute_years(self):
        for process in self:
            # Año de inicio: primer orden de venta vinculada
            start_year = False
            if process.sale_order_ids:
                first_order = process.sale_order_ids.sorted(key=lambda o: o.date_order)[0]
                start_year = first_order.date_order.strftime('%y') if first_order.date_order else False

            # Año de fin: fecha de cierre de la importación
            end_year = False
            if process.importation_id and process.importation_id.date_import_closed:
                end_year = process.importation_id.date_import_closed.strftime('%y')

            process.start_year = start_year or fields.Date.today().strftime('%y')
            process.end_year = end_year or process.start_year

    @api.model
    def create(self, vals):
        # Obtener el número secuencial SIN el prefijo
        sequence_num = self.env['ir.sequence'].next_by_code('sale.process.sli.seq')

        # Si no se obtuvo secuencia, usar valor por defecto
        if not sequence_num:
            sequence_num = "0000"

        # Crear registro primero con nombre temporal
        vals['name'] = "TEMP-" + sequence_num
        record = super().create(vals)

        # Actualizar nombre con formato SLI-0000/25/25
        record._update_process_name(sequence_num)

        return record

    def _update_process_name(self, sequence_num):
        """Actualiza el nombre del proceso con el formato correcto"""
        for record in self:
            # Asegurarse que los años están calculados
            if not record.start_year or not record.end_year:
                record._compute_years()

            # Formatear secuencia a 4 dígitos
            sequence_str = sequence_num.zfill(4)
            new_name = f"SLI-{sequence_str}-{record.start_year}-{record.end_year}"

            # Actualizar sin disparar recursión
            if record.name != new_name:
                self.env.cr.execute("""
                    UPDATE sale_order_process
                    SET name = %s
                    WHERE id = %s
                """, (new_name, record.id))
                self.invalidate_recordset(['name'])
