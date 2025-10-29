# -*- coding: utf-8 -*-
import io
import base64
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except Exception:
    xlsxwriter = None


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def _generate_supplier_excel(self, po):
        if not po:
            raise UserError(_("No se puede generar el Excel: no hay orden de compra válida."))

        if not xlsxwriter:
            raise UserError(_("No se puede generar el Excel: falta la librería xlsxwriter en el servidor."))

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Cotizacion')

        fmt_header_label = wb.add_format({
            'bold': True,
            'font_size': 10,
        })
        fmt_table_header = wb.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })
        fmt_cell_border = wb.add_format({
            'border': 1,
            'valign': 'top',
        })
        fmt_cell_center = wb.add_format({
            'border': 1,
            'valign': 'top',
            'align': 'center',
        })
        fmt_cell_right = wb.add_format({
            'border': 1,
            'valign': 'top',
            'align': 'right',
        })

        # Column widths
        ws.set_column('A:A', 50)  # Descripción
        ws.set_column('B:B', 12)  # U.M.
        ws.set_column('C:C', 12)  # Cantidad
        ws.set_column('D:D', 15)  # Precio Unitario (vacío)

        row = 0

        proveedor_name = po.partner_id.display_name or ''
        po_name = po.name or ''
        today_str = date.today().strftime("%d/%m/%Y")

        ws.write(row, 0, _("Proveedor:"), fmt_header_label)
        ws.write(row, 1, proveedor_name)
        row += 1

        ws.write(row, 0, _("Referencia OC / RFQ:"), fmt_header_label)
        ws.write(row, 1, po_name)
        row += 1

        ws.write(row, 0, _("Fecha:"), fmt_header_label)
        ws.write(row, 1, today_str)
        row += 2  # blank line

        # table header
        ws.write(row, 0, _("Descripción"), fmt_table_header)
        ws.write(row, 1, _("U.M."), fmt_table_header)
        ws.write(row, 2, _("Cantidad"), fmt_table_header)
        ws.write(row, 3, _("Precio Unitario"), fmt_table_header)
        row += 1

        # lines
        for line in po.order_line:
            desc = line.name or (line.product_id.display_name or '')
            uom_name = line.product_uom and line.product_uom.name or ''
            qty = line.product_qty or 0.0

            ws.write(row, 0, desc, fmt_cell_border)
            ws.write(row, 1, uom_name, fmt_cell_center)
            ws.write_number(row, 2, qty, fmt_cell_right)
            ws.write(row, 3, "", fmt_cell_right)  # proveedor rellena aquí
            row += 1

        wb.close()
        output.seek(0)
        data_b64 = base64.b64encode(output.read())

        filename = "%s-Cotizacion-%s.xlsx" % (
            po.name.replace('/', '_'),
            date.today().strftime("%Y%m%d"),
        )
        return filename, data_b64

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """
        Adjunta automáticamente el Excel editable con las líneas de la OC al wizard de email,
        SIN quitar el PDF original.

        No llamamos super() porque el padre puede no definir este onchange en tu versión
        y eso rompe. Hacemos todo aquí.
        """
        for wizard in self:
            # Obtener modelo y res_id de todas las formas posibles
            model_name = (
                getattr(wizard, 'model', False)
                or wizard._context.get('default_model')
                or wizard._context.get('active_model')
            )

            po_id = (
                getattr(wizard, 'res_id', False)
                or wizard._context.get('default_res_id')
                or wizard._context.get('active_id')
            )

            # Si todavía no sabemos a qué documento apunta este compose,
            # no hacemos nada (dejamos que el popup siga normal).
            if not model_name or not po_id:
                _logger.debug(
                    "compose:onchange(template_id) -> contexto incompleto "
                    "(model=%s, po_id=%s). Aún no adjunto Excel.",
                    model_name, po_id
                )
                continue

            # Solo nos interesa purchase.order
            if model_name != 'purchase.order':
                continue

            po = wizard.env['purchase.order'].browse(po_id)
            if not po.exists():
                continue

            # ¿ya tiene nuestro Excel adjunto?
            already_xlsx = wizard.attachment_ids.filtered(
                lambda att: att.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                            and att.name.endswith('.xlsx')
            )
            if already_xlsx:
                continue

            # Generar y adjuntar Excel
            try:
                filename, data_b64 = wizard._generate_supplier_excel(po)
            except Exception as e:
                _logger.exception(
                    "No se pudo generar el Excel RFQ para la OC %s: %s",
                    po.name, e
                )
                continue  # no bloqueamos el popup

            attachment = wizard.env['ir.attachment'].create({
                'name': filename,
                'datas': data_b64,
                'res_model': 'purchase.order',
                'res_id': po.id,
                'type': 'binary',
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            })

            wizard.attachment_ids = [(4, attachment.id)]

        return
