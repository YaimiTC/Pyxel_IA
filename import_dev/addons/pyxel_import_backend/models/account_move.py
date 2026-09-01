import io
import base64
import xlsxwriter

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_type = fields.Selection([
        ('normal', 'Normal'),
        ('operative', 'Operativa'),
        ('import_service', 'Servicios de importación'),
        ('tariff_service', 'Aranceles y servicios'),
        ('other_costs', 'Otros gastos'),
    ], string="Invoice type", default='normal')

    importation_process_id = fields.Many2one(
        'importation.process',
        string="Import process"
    )

    container_ids = fields.One2many(
        related='importation_process_id.load_tracking_ids',
        string='Containers',
        readonly=True
    )

    container_names = fields.Char(
        string="Containers",
        compute='_compute_container_names',
        store=True
    )

    @api.depends('importation_process_id.load_tracking_ids.name')
    def _compute_container_names(self):
        for record in self:
            containers = record.importation_process_id.load_tracking_ids
            record.container_names = ', '.join(containers.mapped('name')) if containers else ''

    @api.model
    def default_get(self, fields_list):
        """
        Default inteligente:
        - Si la factura se crea desde un SO en contexto (active_model='sale.order')
          y el SO tiene order_type='importation_process' => import_service
        - En cualquier otro caso => other_costs
        """
        res = super().default_get(fields_list)

        # Solo aplica para facturas de cliente (opcional, si quieres limitarlo)
        move_type = res.get("move_type") or self.env.context.get("default_move_type")
        if move_type and move_type not in ("out_invoice", "out_refund"):
            return res

        if "invoice_type" not in fields_list:
            return res

        ctx = self.env.context
        if ctx.get("active_model") == "sale.order" and ctx.get("active_id"):
            so = self.env["sale.order"].browse(ctx["active_id"])
            if so and so.exists():
                if getattr(so, "order_type", "ordinary") == "importation_process":
                    res["invoice_type"] = "import_service"
                else:
                    # cualquier otro SO => other_costs
                    res["invoice_type"] = "other_costs"

        return res

    def action_post(self):
        res = super().action_post()

        for move in self:
            if move.move_type != "out_invoice":
                continue

            proc = getattr(move, "importation_process_id", False)
            if proc:
                proc.action_plaza_try_close_single_invoice()

        return res

    def _get_comercial_invoice_block(self):
        """Bloque de cliente (en.import.request.client) de esta factura:
        el que corresponde al mismo proceso y al mismo partner facturado."""
        self.ensure_one()
        proc = self.importation_process_id
        if not proc:
            return self.env['en.import.request.client']
        return proc.en_request_client_ids.filtered(
            lambda b: b.customer_id == self.partner_id
        )[:1]

    def action_export_comercial_invoice_excel(self):
        """Descarga la factura como 'Factura Comercial' en Excel: encabezado
        con proveedor (importadora) y cliente lado a lado, referencia de la
        importación, gastos de origen (de la OC del bloque) y gastos de
        destino (las propias líneas de esta factura), y pie con datos del
        transportista y firmas. Las tablas de gastos son dinámicas: una fila
        por cada línea real que exista, no posiciones fijas."""
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_("Esta descarga solo aplica a facturas de cliente."))

        proc = self.importation_process_id
        importer = proc.importer_id if proc else self.env['importation.importer']
        block = self._get_comercial_invoice_block()
        po = block.purchase_order_id
        partner = self.partner_id.commercial_partner_id

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet(_('Factura Comercial'))

        f_title = wb.add_format({
            'bold': True, 'font_size': 14, 'align': 'center',
            'bg_color': '#D9E1F2', 'border': 1,
        })
        f_doc_no = wb.add_format({'bold': True, 'align': 'right', 'font_size': 11})
        f_section = wb.add_format({'bold': True, 'font_size': 11, 'bg_color': '#D9E1F2', 'border': 1})
        f_label = wb.add_format({'bold': True, 'border': 1, 'valign': 'top'})
        f_value = wb.add_format({'border': 1, 'text_wrap': True, 'valign': 'top'})
        f_money = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right'})
        f_total_label = wb.add_format({'bold': True, 'border': 1, 'font_size': 12})
        f_total_money = wb.add_format({
            'bold': True, 'border': 1, 'num_format': '#,##0.00',
            'align': 'right', 'font_size': 12,
        })
        f_sig_label = wb.add_format({'bold': True})
        f_sig_line = wb.add_format({'top': 1})
        f_letterhead_name = wb.add_format({'bold': True, 'font_size': 13, 'align': 'right'})
        f_letterhead = wb.add_format({'align': 'right'})

        ws.set_column('A:A', 26)
        ws.set_column('B:B', 26)
        ws.set_column('C:C', 3)
        ws.set_column('D:D', 26)
        ws.set_column('E:E', 26)

        def write_block(r, col_label, col_value, rows):
            for label, val in rows:
                ws.write(r, col_label, label, f_label)
                ws.write(r, col_value, val or '', f_value)
                r += 1
            return r

        importer_bank_account = (
            importer.bank_account_usd if self.currency_id.name == 'USD'
            else importer.bank_account_cup if self.currency_id.name == 'CUP'
            else False
        )
        partner_bank_account = (
            partner.bank_account_usd if self.currency_id.name == 'USD'
            else partner.bank_account_cup if self.currency_id.name == 'CUP'
            else False
        )

        r = 0
        logo_end_r = 0
        if importer.logo:
            ws.insert_image(
                r, 0, 'logo.png',
                {'image_data': io.BytesIO(base64.b64decode(importer.logo)), 'x_scale': 0.5, 'y_scale': 0.5},
            )
            logo_end_r = r + 3

        lh_r = r
        ws.merge_range(lh_r, 3, lh_r, 4, importer.name or '', f_letterhead_name)
        lh_r += 1
        for label, val in [
            (_("NIT"), importer.vat),
            (_("No. Registro Comercial"), importer.registro_comercial),
            (_("No. Registro Mercantil"), importer.registro_mercantil),
            (_("Dirección"), importer.street),
            (_("Teléfono"), importer.phone),
            (_("Email"), importer.email),
            (_("Cuenta Bancaria (%s)") % self.currency_id.name, importer_bank_account),
        ]:
            ws.merge_range(lh_r, 3, lh_r, 4, "%s: %s" % (label, val or ''), f_letterhead)
            lh_r += 1

        r = max(logo_end_r, lh_r) + 1
        ws.merge_range(r, 0, r, 4, _("FACTURA COMERCIAL"), f_title)
        r += 1
        ws.merge_range(r, 0, r, 4, _("No. Fact. %s") % (self.name or ''), f_doc_no)
        r += 1
        ws.merge_range(r, 0, r, 4, self.invoice_date and self.invoice_date.strftime('%d/%m/%Y') or '', f_doc_no)
        r += 2

        r = write_block(r, 0, 1, [
            (_("Nombre del Cliente"), partner.name),
            (_("NIT"), partner.vat),
            (_("No. Registro Comercial (REEUP)"), partner.registro_comercial),
            (_("No. Registro Mercantil"), partner.registro_mercantil),
            (_("Dirección"), partner.street),
            (_("Cuenta Bancaria (%s)") % self.currency_id.name, partner_bank_account),
        ])
        r += 1

        import_type_es = {
            'Ocean Freight': _("Embarque Marítimo"),
        }
        import_type_name = proc.import_type_id.name if proc and proc.import_type_id else ''
        import_type_name = import_type_es.get(import_type_name, import_type_name)
        ws.merge_range(r, 0, r, 1, _("Tipo de Operación: %s") % import_type_name, f_value)
        ws.merge_range(r, 3, r, 4, _("Forma de Pago: %s") % (block.en_payment_method_id.name if block and block.en_payment_method_id else ''), f_value)
        r += 2

        containers = po._get_po_containers(po) if po else self.env['importation.load']
        container_names = ", ".join(containers.mapped('name')) if containers else (self.container_names or '')
        products = po.order_line.filtered(
            lambda l: l.product_id.detailed_type == 'product'
        ).mapped('product_id.display_name') if po else []

        ws.merge_range(r, 0, r, 4, _("REFERENCIA DE IMPORTACIÓN"), f_section)
        r += 1
        r = write_block(r, 0, 1, [
            (_("Proveedor (mercancía)"), po.partner_id.name if po else ''),
            (_("Booking"), block.bl_number if block else ''),
            (_("Contenedor(es)"), container_names),
            (_("Producto(s)"), ", ".join(products)),
            (_("Factura del Proveedor"), po.partner_ref if po else ''),
            (_("Declaración de Mercancía (DM)"), getattr(proc, 'en_dm_number', '') if proc else ''),
        ])
        r += 1

        if po:
            merchandise_lines = po.order_line.filtered(lambda l: l.product_id.detailed_type == 'product')
            service_lines = po.order_line.filtered(lambda l: l.product_id.detailed_type == 'service')
            fob = sum(merchandise_lines.mapped('price_subtotal'))

            origin_ccy = po.currency_id.name or ''
            ws.merge_range(r, 0, r, 4, _("GASTOS DE ORIGEN"), f_section)
            r += 1
            ws.merge_range(r, 0, r, 3, _("Valor Mercancía (FOB) (%s)") % origin_ccy, f_label)
            ws.write_number(r, 4, fob, f_money)
            r += 1
            for line in service_lines:
                label = line.name or line.product_id.display_name or ''
                ws.merge_range(r, 0, r, 3, "%s (%s)" % (label, origin_ccy), f_label)
                ws.write_number(r, 4, line.price_subtotal, f_money)
                r += 1
            ws.merge_range(r, 0, r, 3, _("Valor Mercancía (CIF) (%s)") % origin_ccy, f_label)
            ws.write_number(r, 4, po.amount_untaxed, f_money)
            r += 1
            r += 1

        ws.merge_range(r, 0, r, 4, _("GASTOS DE DESTINO"), f_section)
        r += 1
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note')):
            ws.merge_range(r, 0, r, 3, line.name or line.product_id.display_name or '', f_label)
            ws.write_number(r, 4, line.price_subtotal, f_money)
            r += 1
        r += 1

        ws.merge_range(r, 0, r, 3, _("IMPORTE FINAL A PAGAR (%s)") % self.currency_id.name, f_total_label)
        ws.write_number(r, 4, self.amount_total, f_total_money)
        r += 2

        ws.merge_range(r, 0, r, 4, _("Observaciones: %s") % "http://www.superpay23.com", f_value)
        r += 2

        sig_cols = [
            (0, _("ENTREGA:")),
            (1, _("RECIBE:")),
            (3, _("Facturación:")),
            (4, _("Contabilidad:")),
        ]
        for col, label in sig_cols:
            ws.write(r, col, label, f_sig_label)
        r += 1
        invoicing_user_name = (self.invoice_user_id or self.create_uid).name or ''
        for col, _label in sig_cols:
            ws.write(r, col, _("Nombre y Apellidos:"))
        r += 1
        for col, _label in sig_cols:
            ws.write(r, col, invoicing_user_name if col == 3 else '', f_sig_line)
        r += 1
        for col, _label in sig_cols:
            ws.write(r, col, _("Firma:"))
        r += 1
        for col, _label in sig_cols:
            ws.write(r, col, '', f_sig_line)
        r += 1
        for col, _label in sig_cols:
            ws.write(r, col, _("Fecha:"))
        r += 1
        for col, _label in sig_cols:
            ws.write(r, col, '', f_sig_line)
        r += 1

        ws.merge_range(r, 3, r, 4, _("Folio No. %s") % (self.name or ''), f_total_label)
        last_row = r

        ws.print_area(0, 0, last_row, 4)
        ws.fit_to_pages(1, 1)
        ws.set_margins(left=0.3, right=0.3, top=0.4, bottom=0.4)
        ws.center_horizontally()

        wb.close()
        output.seek(0)
        data = base64.b64encode(output.read())

        filename = (_("Factura_Comercial_%s.xlsx") % (self.name or self.id)).replace('/', '_')
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': data,
            'res_model': 'account.move',
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'self',
        }


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    is_cost_special = fields.Boolean(string="Special Cost", default=False)

