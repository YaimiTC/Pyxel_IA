import io
import base64
from datetime import date
from odoo.exceptions import UserError
import xlsxwriter
from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    partner_id = fields.Many2one(
        domain="[('contact_type_id.type_of_contact', '=', 'Supplier')]",
    )

    sale_order_id = fields.Many2one('sale.order', string='Related Quotation')
    process_id = fields.Many2one(
        'sale.order.process',
        string='Proceso',
        related='sale_order_id.process_id',
        store=True,
        readonly=True,
    )
    evaluation_id = fields.Many2one('purchase.provider.evaluation', string='Evaluation')
    is_third_party_contract = fields.Boolean(string='Third-Party Contract')

    commercial_invoice = fields.Binary(string='Commercial Invoice')
    commercial_invoice_filename = fields.Char()

    signed_offer = fields.Binary(string='Signed Offer')
    signed_offer_filename = fields.Char()

    importation_id = fields.Many2one(
        'importation.process',
        string='Importation Process',
        help='Importation process to which this purchase order belongs.')

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            for po in self:
                eval_rec = po.evaluation_id
                if eval_rec:
                    orders = eval_rec.purchase_order_ids
                    if not orders:
                        eval_rec.state = 'draft'
                    elif all(o.state == 'cancel' for o in orders):
                        eval_rec.state = 'cancelled'
        return res

    def unlink(self):
        evaluations_to_check = self.mapped('evaluation_id')
        res = super().unlink()
        for evaluation in evaluations_to_check:
            if not evaluation.purchase_order_ids:
                evaluation.state = 'draft'
        return res

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()

        # Find evaluations associated with confirmed orders
        for order in self:
            evaluations = self.env['purchase.provider.evaluation'].search([
                ('purchase_order_ids', 'in', order.id),
                ('state', '!=', 'apply')
            ])
            for evaluation in evaluations:
                evaluation.state = 'apply'

        return res

    def _resequence_purchase_lines(self):
        for order in self:
            lines = order.order_line.sorted(lambda l: l.sequence)
            # lines = lines.filtered(lambda l: not l.display_type)
            for idx, line in enumerate(lines, start=1):
                if line.line_number != idx:
                    line.sudo().write({'line_number': idx})

    def action_rfq_send(self):

        self.ensure_one()
        return super().action_rfq_send()

    def action_export_excel_aduana(self):
        """
        Genera el Excel con el formato solicitado para esta PO.
        Si se llama con múltiples POs, devuelve el primero (puedes adaptar a ZIP si lo necesitas).
        """
        if xlsxwriter is None:
            raise UserError(_("Falta la librería 'xlsxwriter' en el servidor."))

        if not self:
            raise UserError(_("No hay órdenes de compra para exportar."))

        po = self[0]  # Exportamos la primera si llega un recordset

        # --- Crear workbook en memoria ---
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Resumen PO')

        # Estilos
        f_title = wb.add_format({'bold': True, 'font_size': 11})
        f_label_red = wb.add_format({'bold': True, 'font_color': 'red'})
        f_head_red_border = wb.add_format({
            'bold': True, 'font_color': 'red', 'border': 1, 'align': 'center'
        })
        f_cell_border = wb.add_format({'border': 1})
        f_cell_border_center = wb.add_format({'border': 1, 'align': 'center'})

        f_num = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right'})
        f_num0 = wb.add_format({'border': 1, 'num_format': '#,##0', 'align': 'right'})

        f_total_num = wb.add_format(
            {'border': 1, 'num_format': '#,##0.00', 'align': 'right', 'bold': True, 'font_color': 'red'})
        f_total_num0 = wb.add_format(
            {'border': 1, 'num_format': '#,##0', 'align': 'right', 'bold': True, 'font_color': 'red'})

        # Anchos de columnas similares al ejemplo
        ws.set_column('A:A', 16)  # ptda aranc
        ws.set_column('B:B', 55)  # Descripción
        ws.set_column('C:C', 10)  # Origen
        ws.set_column('D:D', 10)  # Artículo
        ws.set_column('E:E', 10)  # Bulto
        ws.set_column('F:F', 12)  # Precio
        ws.set_column('G:G', 14)  # Importe
        ws.set_column('H:H', 12)  # Peso Neto
        ws.set_column('I:I', 12)  # Peso Bruto

        # ====== Encabezado izquierdo ======
        r = 0
        proveedor = po.partner_id.display_name or ""
        cliente = po.importation_id.customer_id.display_name or ""
        cont_str = self._get_containers_str(po)
        contracts = po.partner_id.contract_import_ids.filtered(lambda s: s.active_contract)
        contrato = contracts[:1]  # recordset de a lo sumo 1
        contract_name = contrato.contract_number if contrato else ""
        condicion = po.importation_id.import_type_id.name

        importe_fob = po.amount_untaxed or 0.0
        importe_total = po.amount_total or 0.0

        left_rows = [
            (_("Proveedor:"), proveedor),
            (_("Cadena:"), ""),  # no gestionado
            (_("Cliente:"), cliente),
            (_("Contrato:"), contract_name),  # no gestionado
            (_("Contenedor:"), cont_str),
            (_("Condición:"), condicion),  # no gestionado
            (_("Total de Bultos:"), ""),  # no gestionado
            (_("Importe FOB:"), importe_fob),
            (_("Peso Bruto:"), ""),  # no gestionado
            (_("Peso Neto:"), ""),  # no gestionado
            (_("Costo Financiamiento:"), ""),  # no gestionado
            (_("Importe Total:"), importe_total),
            ("----", ""),
        ]

        for label, val in left_rows:
            ws.write(r, 0, label, f_label_red)
            if isinstance(val, (int, float)):
                ws.write_number(r, 1, val, f_num)
            else:
                ws.write(r, 1, val)
            r += 1

        r += 1  # línea en blanco

        # ====== Cabecera de tabla ======
        headers = [
            "ptdaaranc", "Descripcion", "Origen", "Articulo",
            "Bulto", "Precio", "Importe", "Peso Neto", "Peso Bruto",
        ]
        for c, h in enumerate(headers):
            ws.write(r, c, h, f_head_red_border)
        r += 1

        # ====== Cuerpo: líneas de la PO ======
        total_qty = 0.0
        total_bulto = 0.0
        total_precio = 0.0
        total_importe = 0.0
        total_peso_neto = 0.0
        total_peso_bruto = 0.0

        for line in po.order_line:
            hs_code = getattr(line.product_id, 'hs_code', False) or (line.product_id.default_code or '')
            descripcion = line.name or (line.product_id.display_name or '')
            origen = ""  # no gestionado
            articulo = line.product_qty or 0.0
            bulto = ""  # no gestionado
            precio = line.price_unit or 0.0
            importe = (line.product_qty or 0.0) * (line.price_unit or 0.0)
            peso_neto = ""  # no gestionado
            peso_bruto = ""  # no gestionado

            ws.write(r, 0, hs_code, f_cell_border)
            ws.write(r, 1, descripcion, f_cell_border)
            ws.write(r, 2, origen, f_cell_border_center)
            ws.write_number(r, 3, articulo, f_num0)
            ws.write(r, 4, bulto, f_cell_border_center)
            ws.write_number(r, 5, precio, f_num)
            ws.write_number(r, 6, importe, f_num)
            ws.write(r, 7, peso_neto, f_cell_border_center)
            ws.write(r, 8, peso_bruto, f_cell_border_center)

            total_qty += articulo
            total_precio += precio
            total_importe += importe
            r += 1

        # Totales (alineados a la derecha)
        ws.write(r, 0, "", f_cell_border)
        ws.write(r, 1, "", f_cell_border)
        ws.write(r, 2, "", f_cell_border)
        ws.write_number(r, 3, total_qty, f_total_num0)
        ws.write_number(r, 4, total_bulto, f_total_num0)
        ws.write_number(r, 5, total_precio, f_total_num)
        ws.write_number(r, 6, total_importe, f_total_num)
        ws.write_number(r, 7, total_peso_neto, f_total_num)
        ws.write_number(r, 8, total_peso_bruto, f_total_num)

        wb.close()
        output.seek(0)
        data = base64.b64encode(output.read())

        # Nombre archivo: <PO>-dd-mm-YYYY.xlsx
        today_str = date.today().strftime("%d-%m-%Y")
        filename = f"{po.name}-{today_str}.xlsx"

        # Crear attachment y devolver descarga
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': data,
            'res_model': 'purchase.order',
            'res_id': po.id,
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        url = f"/web/content/{attachment.id}?download=true"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }

        # ------------------------------------------------------------
        # Helpers
        # ------------------------------------------------------------

    def _get_po_containers(self, po):
        """
        Contenedores (x_container) que contienen líneas de esta PO:
        x_container.x_studio_order_lines_by_container (o2m intermedio)
          -> x_containerlineorder.x_studio_purchase_order_line (m2o pol)
        """
        Container = self.env['importation.load'].sudo()
        if not po.order_line:
            return Container.browse()
        return Container.search([
            ('cargo_line_ids.purchase_order_line_id', 'in', po.order_line.ids)
        ])

    def _get_containers_str(self, po):
        containers = self._get_po_containers(po)
        return ", ".join(containers.mapped('name')) if containers else ""


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    sale_order_line_id = fields.Many2one('sale.order.line', string='Source Sales Line')

    currency_id = fields.Many2one(
        related='order_id.currency_id',
        string='Currency',
        store=True,
        readonly=True
    )

    container_fix_ids = fields.One2many(
        comodel_name='importation.load.line',
        inverse_name='purchase_order_line_id',
        string='Container Lines'
    )

    quantity_allocated = fields.Float(
        string='Allocated Quantity for Containers',
        compute='_compute_quantity_allocated',
        store=True,
    )

    quantity_available = fields.Float(
        string='Available Quantity for Containers',
        compute='_compute_quantity_available',
        store=True,
    )

    @api.depends('container_fix_ids.quantity')
    def _compute_quantity_allocated(self):
        for line in self:
            line.quantity_allocated = sum(line.container_fix_ids.mapped('quantity') or [])

    @api.depends('product_uom_qty', 'quantity_allocated')
    def _compute_quantity_available(self):
        for line in self:
            line.quantity_available = (line.product_uom_qty or 0.0) - (line.quantity_allocated or 0.0)

    # Helpers para reutilizar desde importation.load.line
    def _get_allocated_qty(self, exclude_line=None):
        """Devuelve la cantidad asignada, opcionalmente excluyendo una línea concreta."""
        self.ensure_one()
        lines = self.container_fix_ids
        if exclude_line:
            lines = lines - exclude_line
        return sum(lines.mapped('quantity') or [])

    def _get_available_qty(self, exclude_line=None):
        """Cantidad disponible respetando una línea concreta (útil en onchange)."""
        self.ensure_one()
        allocated = self._get_allocated_qty(exclude_line=exclude_line)
        return (self.product_uom_qty or 0.0) - allocated

    line_number = fields.Integer(
        string="N°",
        compute="_compute_line_number",
        store=True,
        readonly=True,
        help="Número de línea autocalculado, inicia en 1 y se reenumera sin huecos."
    )

    @api.depends('order_id.order_line.sequence', 'order_id.order_line.display_type')
    def _compute_line_number(self):
        orders = self.mapped('order_id')
        for order in orders:
            if not order:
                continue
            lines = order.order_line.sorted(lambda l: l.sequence)
            # lines = lines.filtered(lambda l: not l.display_type)
            for idx, line in enumerate(lines, start=1):
                line.line_number = idx

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        (records.mapped('order_id'))._resequence_purchase_lines()
        return records

    def write(self, vals):
        orders_before = self.mapped('order_id')
        res = super().write(vals)
        (self.mapped('order_id') | orders_before)._resequence_purchase_lines()
        return res

    def unlink(self):
        orders = self.mapped('order_id')
        res = super().unlink()
        orders._resequence_purchase_lines()
        return res
