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

    sale_order_refs = fields.Char(
        string="OV origen",
        compute='_compute_so_po_refs'
    )
    purchase_order_refs = fields.Char(
        string="OC relacionadas",
        compute='_compute_so_po_refs'
    )

    @api.depends('importation_process_id.load_tracking_ids.name')
    def _compute_container_names(self):
        for record in self:
            containers = record.importation_process_id.load_tracking_ids
            record.container_names = ', '.join(containers.mapped('name')) if containers else ''

    @api.depends('invoice_line_ids.sale_line_ids.order_id',
                 'importation_process_id.purchase_order_ids.name')
    def _compute_so_po_refs(self):
        for move in self:
            sos = move.invoice_line_ids.sale_line_ids.order_id
            move.sale_order_refs = ', '.join(sorted(set(sos.mapped('name')))) if sos else ''
            if move.importation_process_id:
                pos = move.importation_process_id.purchase_order_ids
                move.purchase_order_refs = ', '.join(sorted(set(pos.mapped('name')))) if pos else ''
            else:
                move.purchase_order_refs = ''

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
        partner = self.partner_id
        commercial = partner.commercial_partner_id
        return proc.en_request_client_ids.filtered(
            lambda b: b.customer_id in (partner, commercial)
        )[:1]

    def _get_dm_number(self, proc, po):
        """Busca el número de DM: primero en el campo manual del proceso,
        luego en el documento DM confirmado de la OC del bloque."""
        if proc and proc.en_dm_number:
            return proc.en_dm_number
        if po:
            dm_doc = self.env['pyxel.import.document'].search([
                ('purchase_order_id', '=', po.id),
                ('document_key', '=', 'dm'),
                ('dm_confirmed', '=', True),
            ], limit=1)
            if dm_doc:
                return dm_doc.dm_number or ''
        return ''

    def _get_comercial_invoice_report_data(self):
        """Devuelve un dict con todos los datos necesarios para el template QWeb
        de la Factura Comercial. Misma lógica que action_export_comercial_invoice_excel."""
        self.ensure_one()
        proc = self.importation_process_id
        importer = proc.importer_id if proc else self.env['importation.importer']
        block = self._get_comercial_invoice_block()
        po = block.purchase_order_id if block else self.env['purchase.order']
        if not po and proc:
            for cl in proc.cost_line_ids:
                match = cl.purchase_ids.filtered(
                    lambda p: p.customer_id == self.partner_id.commercial_partner_id
                              or p.customer_id == self.partner_id
                )
                if match:
                    po = match[:1]
                    break
        partner = self.partner_id.commercial_partner_id

        importer_bank = (
            importer.bank_account_usd if self.currency_id.name == 'USD'
            else importer.bank_account_cup if self.currency_id.name == 'CUP'
            else ''
        ) or ''
        partner_bank = (
            partner.bank_account_usd if self.currency_id.name == 'USD'
            else partner.bank_account_cup if self.currency_id.name == 'CUP'
            else ''
        ) or ''

        import_type_es = {'Ocean Freight': 'Embarque Marítimo'}
        import_type_name = proc.import_type_id.name if proc and proc.import_type_id else ''
        import_type_name = import_type_es.get(import_type_name, import_type_name)

        containers = po._get_po_containers(po) if po else self.env['importation.load']
        container_names = ", ".join(containers.mapped('name')) if containers else (self.container_names or '')
        products = []
        merchandise_lines = self.env['purchase.order.line']
        service_lines = self.env['purchase.order.line']
        fob = 0.0
        if po:
            merchandise_lines = po.order_line.filtered(lambda l: l.product_id.detailed_type == 'product')
            service_lines = po.order_line.filtered(lambda l: l.product_id.detailed_type != 'product')
            products = merchandise_lines.mapped('product_id.display_name')
            fob = sum(merchandise_lines.mapped('price_subtotal'))

        invoice_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )

        return {
            'importer': importer,
            'importer_bank': importer_bank,
            'block': block,
            'po': po,
            'partner': partner,
            'partner_bank': partner_bank,
            'import_type_name': import_type_name,
            'container_names': container_names,
            'products': products,
            'merchandise_lines': merchandise_lines,
            'service_lines': service_lines,
            'fob': fob,
            'invoice_lines': invoice_lines,
            'dm_number': self._get_dm_number(proc, po),
            'invoicing_user': (self.invoice_user_id or self.create_uid).name or '',
        }

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
        # Fallback: si no hay bloque, buscar OC en líneas de costo donde el cliente coincide
        if not po and proc:
            for cl in proc.cost_line_ids:
                match = cl.purchase_ids.filtered(
                    lambda p: p.customer_id == self.partner_id.commercial_partner_id
                              or p.customer_id == self.partner_id
                )
                if match:
                    po = match[:1]
                    break
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
            (_("Declaración de Mercancía (DM)"), self._get_dm_number(proc, po)),
        ])
        r += 1

        if po and self.currency_id.name != 'CUP':
            merchandise_lines = po.order_line.filtered(lambda l: l.product_id.detailed_type == 'product')
            service_lines = po.order_line.filtered(lambda l: l.product_id.detailed_type != 'product')
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


    def action_export_etec_invoice_excel(self):
        """Genera el Excel en formato ETEC con 3 hojas visibles:
        tabla contenido / Hoja de Calculo / Factura."""
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_("Esta descarga solo aplica a facturas de cliente."))

        proc = self.importation_process_id
        importer = proc.importer_id if proc else self.env['importation.importer']
        block = self._get_comercial_invoice_block()
        po = block.purchase_order_id if block else self.env['purchase.order']
        if not po and proc:
            for cl in proc.cost_line_ids:
                match = cl.purchase_ids.filtered(
                    lambda p: p.customer_id == self.partner_id.commercial_partner_id
                              or p.customer_id == self.partner_id
                )
                if match:
                    po = match[:1]
                    break
        if not po and proc:
            po = self.env['purchase.order'].search(
                [('importation_id', '=', proc.id)], limit=1
            )

        partner = self.partner_id.commercial_partner_id

        # Contenedores vinculados a la OC específica vía sus líneas de carga
        if po and proc:
            containers = proc.load_tracking_ids.filtered(
                lambda c: po in c.cargo_line_ids.mapped('purchase_order_id')
            )
        elif proc:
            containers = proc.load_tracking_ids
        else:
            containers = self.env['importation.load']
        loads = proc.load_tracking_ids if proc else self.env['importation.load']
        first_load = containers[:1] or loads[:1]

        merch_lines = po.order_line.filtered(
            lambda l: l.product_id.detailed_type == 'product'
        ) if po else self.env['purchase.order.line']
        service_lines = po.order_line.filtered(
            lambda l: l.product_id.detailed_type != 'product'
        ) if po else self.env['purchase.order.line']
        products = merch_lines.mapped('product_id.display_name')
        fob_amount = sum(merch_lines.mapped('price_subtotal'))
        cif_amount = po.amount_untaxed if po else 0.0
        dm_number = self._get_dm_number(proc, po)

        vessel = ', '.join(set(filter(None, containers.mapped('shipping_company')))) or ''
        bl_numbers = ', '.join(set(filter(None, containers.mapped('bl_number')))) or ''
        dest_names = ', '.join(set(filter(None, containers.mapped('destination_id.name')))) or ''
        purchase_cond = ', '.join(set(filter(None, loads.mapped('purchase_condition')))) or ''
        bl_date = (first_load.mbl_release_date.strftime('%d/%m/%Y')
                   if first_load and first_load.mbl_release_date else '')
        arrival_date = (first_load.arrival_date.strftime('%d/%m/%Y')
                        if first_load and first_load.arrival_date else '')

        # Tasa CUP/USD a la fecha de la factura
        cup_rate = 24.0
        try:
            usd_cur = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            cup_cur = self.env['res.currency'].search([('name', '=', 'CUP')], limit=1)
            if usd_cur and cup_cur:
                converted = round(usd_cur._convert(
                    1.0, cup_cur, self.company_id,
                    self.invoice_date or fields.Date.today()
                ), 2)
                if converted > 1.0:
                    cup_rate = converted
        except Exception:
            pass

        invoice_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})

        ft = wb.add_format({'bold': True, 'font_size': 12, 'align': 'center',
                            'valign': 'vcenter', 'bg_color': '#BDD7EE', 'border': 1})
        fh = wb.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        fl = wb.add_format({'bold': True, 'border': 1})
        fv = wb.add_format({'border': 1, 'text_wrap': True})
        fm = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right'})
        fb = wb.add_format({'bold': True, 'border': 1, 'num_format': '#,##0.00',
                            'align': 'right', 'bg_color': '#FCE4D6'})
        flb = wb.add_format({'bold': True, 'border': 1, 'bg_color': '#FCE4D6'})
        fr = wb.add_format({'align': 'right', 'bold': True})
        fsig = wb.add_format({'top': 1})

        # ── HOJA 1: tabla contenido ──────────────────────────────────────────
        ws1 = wb.add_worksheet('tabla contenido')
        ws1.set_column('A:A', 4)
        ws1.set_column('B:B', 36)
        ws1.set_column('C:C', 42)

        r = 0
        ws1.merge_range(r, 0, r, 2, 'DATOS DEL EMBARQUE', ft)
        r += 1
        embarque_rows = [
            ('Tipo Operación', 'Importación'),
            ('No. De Compra', po.name if po else ''),
            ('No. De Contrato', po.client_contract_id.name if po and po.client_contract_id else ''),
            ('Forma de Pago', po.payment_term_id.name if po else ''),
            ('Proveedor / Cliente', (po.partner_id.name if po else '') + ' / ' + (partner.name or '')),
            ('Condición de Entrega', purchase_cond),
            ('Producto', ', '.join(products)),
            ('Buque', vessel),
            ('Fecha Bill of Lading (B/L)', bl_date),
            ('No. Bill of Lading (B/L)', bl_numbers),
            ('Puertos de Descarga', dest_names),
            ('Puertos de Carga', proc.port.name if proc and proc.port else ''),
            ('Usuario Final', proc.customer_id.name if proc and proc.customer_id else partner.name or ''),
            ('Factura Proveedor', po.partner_ref if po else ''),
            ('No. DM', dm_number),
            ('Referencia ETEC', proc.name if proc else ''),
            ('Fecha Descarga', arrival_date),
        ]
        for label, val in embarque_rows:
            ws1.write(r, 1, label, fl)
            ws1.write(r, 2, val or '', fv)
            r += 1

        r += 1
        ws1.merge_range(r, 0, r, 2, 'TABLA DE CONTENIDO', ft)
        r += 1
        for num, desc in [
            (1, 'Operación de Compra/Venta'),
            (2, 'Solicitud de apertura de Carta de Crédito (Importación)'),
            (3, 'Documentos de embarque y reportes de Supervisión'),
            (4, 'Proforma de factura para DECLARACION MERCANCIA'),
            (5, 'Declaración de Mercancías'),
            (6, 'Hoja de cálculo'),
            (7, 'Factura Comercial de Compra'),
            (8, 'Factura Comercial de Venta'),
        ]:
            ws1.write(r, 0, num, fv)
            ws1.merge_range(r, 1, r, 2, desc, fv)
            r += 1

        # ── HOJA 2: Hoja de Calculo ──────────────────────────────────────────
        ws2 = wb.add_worksheet('Hoja de Calculo')
        ws2.set_column('A:A', 36)
        ws2.set_column('B:B', 14)
        ws2.set_column('C:C', 14)
        ws2.set_column('D:D', 18)
        ws2.set_column('E:E', 18)

        r = 0
        ws2.write(r, 0, 'IMPORTACIÓN  X', fh)
        ws2.write(r, 3, 'REF. FACT:', fl)
        ws2.write(r, 4, proc.name if proc else '', fv)
        r += 1
        ws2.write(r, 3, 'FECHA:', fl)
        ws2.write(r, 4,
                  self.invoice_date.strftime('%d/%m/%Y') if self.invoice_date else '', fv)
        r += 2

        ws2.merge_range(r, 0, r, 4, 'DATOS DEL CONTRATO / DATOS DEL EMBARQUE', fh)
        r += 1
        contract_rows = [
            ('NO. DE COMPRA:', po.name if po else '',
             'BUQUE:', vessel),
            ('Forma de Pago:', po.payment_term_id.name if po else '',
             'CONDIC. ENTREGA:', purchase_cond),
            ('SUMINISTRADOR:', po.partner_id.name if po else '',
             'FECHA B/L:', bl_date),
            ('PAIS ORIGEN:', proc.country_origin_id.name if proc and proc.country_origin_id else '',
             'NO. BL:', bl_numbers),
            ('Factura Proveedor:', po.partner_ref if po else '',
             'PTO. CARGA:', proc.port.name if proc and proc.port else ''),
            ('PRODUCTO:', ', '.join(products),
             'No. DM:', dm_number),
            ('USUARIO FINAL:', proc.customer_id.name if proc and proc.customer_id else partner.name or '',
             'PTO. DESCARGA:', dest_names),
            ('FECHA DESCARGA:', arrival_date, '', ''),
        ]
        for ll, lv, rl, rv in contract_rows:
            ws2.write(r, 0, ll, fl)
            ws2.write(r, 1, lv or '', fv)
            ws2.write(r, 3, rl, fl)
            ws2.write(r, 4, rv or '', fv)
            r += 1

        r += 1
        # Quantities
        ws2.merge_range(r, 0, r, 4, 'CANTIDADES', fh)
        r += 1
        for hdr in ['PRODUCTO', 'CANTIDAD', 'UM', 'PRECIO UNIT (USD)', 'IMPORTE (USD)']:
            ws2.write(r, ['PRODUCTO', 'CANTIDAD', 'UM',
                          'PRECIO UNIT (USD)', 'IMPORTE (USD)'].index(hdr), hdr, fl)
        r += 1
        for ml in merch_lines:
            ws2.write(r, 0, ml.product_id.display_name or '', fv)
            ws2.write_number(r, 1, ml.product_uom_qty, fm)
            ws2.write(r, 2, ml.product_uom.name or '', fv)
            ws2.write_number(r, 3, ml.price_unit, fm)
            ws2.write_number(r, 4, ml.price_subtotal, fm)
            r += 1

        r += 1
        ws2.merge_range(r, 0, r, 4, 'DETERMINACIÓN DEL COSTO EXTERNO', fh)
        r += 1
        ws2.write(r, 0, 'Concepto', fl)
        ws2.write(r, 3, f'IMPORTE (USD)', fl)
        ws2.write(r, 4, f'IMPORTE (CUP)  rate={cup_rate}', fl)
        r += 1

        ws2.write(r, 0, 'VALOR FOB', fl)
        ws2.write_number(r, 3, fob_amount, fm)
        ws2.write_number(r, 4, fob_amount * cup_rate, fm)
        r += 1

        for sl in service_lines:
            ws2.write(r, 0, sl.product_id.display_name or sl.name or '', fl)
            ws2.write_number(r, 3, sl.price_subtotal, fm)
            ws2.write_number(r, 4, sl.price_subtotal * cup_rate, fm)
            r += 1

        ws2.write(r, 0, 'VALOR CIF', flb)
        ws2.write_number(r, 3, cif_amount, fb)
        ws2.write_number(r, 4, cif_amount * cup_rate, fb)
        r += 2

        ws2.merge_range(r, 0, r, 4, 'COSTOS DE DESTINO (FACTURA)', fh)
        r += 1
        ws2.write(r, 0, 'Concepto', fl)
        ws2.write(r, 3, 'IMPORTE (USD)', fl)
        ws2.write(r, 4, 'IMPORTE (CUP)', fl)
        r += 1

        total_dest_usd = 0.0
        total_dest_cup = 0.0
        for il in invoice_lines:
            if self.currency_id and self.currency_id.name == 'CUP':
                il_cup = il.price_subtotal
                il_usd = (il.price_subtotal / cup_rate) if cup_rate else 0.0
            else:
                il_usd = il.price_subtotal
                il_cup = il.price_subtotal * cup_rate
            ws2.write(r, 0, il.name or il.product_id.display_name or '', fv)
            ws2.write_number(r, 3, il_usd, fm)
            ws2.write_number(r, 4, il_cup, fm)
            total_dest_usd += il_usd
            total_dest_cup += il_cup
            r += 1

        ws2.write(r, 0, 'TOTAL GENERAL', flb)
        ws2.write_number(r, 3, cif_amount + total_dest_usd, fb)
        ws2.write_number(r, 4, cif_amount * cup_rate + total_dest_cup, fb)
        r += 1

        # ── HOJA 3: Factura. ─────────────────────────────────────────────────
        ws3 = wb.add_worksheet('Factura.')
        ws3.set_column('A:A', 42)
        ws3.set_column('B:B', 12)
        ws3.set_column('C:C', 18)
        ws3.set_column('D:D', 18)

        r = 0
        logo_rows = 0
        if importer and importer.logo:
            try:
                ws3.insert_image(r, 0, 'logo.png', {
                    'image_data': io.BytesIO(base64.b64decode(importer.logo)),
                    'x_scale': 0.5, 'y_scale': 0.5,
                })
                logo_rows = 4
            except Exception:
                pass

        lh = 0
        if importer:
            ws3.merge_range(lh, 2, lh, 3, importer.name or '', fr)
            lh += 1
            for lbl, val in [
                ('REEUP:', importer.registro_comercial),
                ('DIRECCIÓN:', importer.street),
                ('NIT:', importer.vat),
                ('Cuenta:', importer.bank_account_cup),
            ]:
                ws3.write(lh, 2, lbl, fl)
                ws3.write(lh, 3, val or '', fv)
                lh += 1

        r = max(logo_rows, lh) + 1
        ws3.merge_range(r, 0, r, 3, 'FACTURA COMERCIAL', ft)
        r += 1
        ws3.write(r, 0, 'No.:', fl)
        ws3.write(r, 1, self.name or '', fv)
        ws3.write(r, 2, 'Fecha:', fl)
        ws3.write(r, 3,
                  self.invoice_date.strftime('%d/%m/%Y') if self.invoice_date else '', fv)
        r += 2

        ws3.merge_range(r, 0, r, 3, 'DATOS DEL CLIENTE', fh)
        r += 1
        for lbl, val in [
            ('Nombre:', partner.name or ''),
            ('NIT:', getattr(partner, 'vat', '') or ''),
            ('REEUP:', getattr(partner, 'registro_comercial', '') or ''),
            ('Dirección:', getattr(partner, 'street', '') or ''),
        ]:
            ws3.write(r, 0, lbl, fl)
            ws3.merge_range(r, 1, r, 3, val, fv)
            r += 1
        r += 1

        ws3.merge_range(r, 0, r, 3, 'REFERENCIA DE LA IMPORTACIÓN', fh)
        r += 1
        for lbl, val in [
            ('Proveedor:', po.partner_id.name if po else ''),
            ('No. DM:', dm_number),
            ('Buque:', vessel),
            ('Producto:', ', '.join(products)),
            ('BL:', bl_numbers),
            ('Contenedores:', ', '.join(containers.mapped('name') if containers else [])),
            ('Factura Proveedor:', po.partner_ref if po else ''),
        ]:
            ws3.write(r, 0, lbl, fl)
            ws3.merge_range(r, 1, r, 3, val or '', fv)
            r += 1
        r += 1

        # Mercancía (CIF)
        ws3.merge_range(r, 0, r, 3, 'VALOR MERCANCÍA Y COSTOS', fh)
        r += 1
        ws3.write(r, 0, 'Concepto', fl)
        ws3.write(r, 1, 'Moneda', fl)
        ws3.write(r, 2, 'Importe USD', fl)
        ws3.write(r, 3, 'Importe CUP', fl)
        r += 1

        po_ccy = po.currency_id.name if po and po.currency_id else 'USD'
        ws3.write(r, 0, 'VALOR MERCANCÍA (CIF)', fl)
        ws3.write(r, 1, po_ccy, fv)
        ws3.write_number(r, 2, cif_amount, fm)
        ws3.write_number(r, 3, cif_amount * cup_rate, fm)
        r += 1

        grand_usd = cif_amount
        grand_cup = cif_amount * cup_rate

        for il in invoice_lines:
            if self.currency_id and self.currency_id.name == 'CUP':
                il_cup = il.price_subtotal
                il_usd = (il.price_subtotal / cup_rate) if cup_rate else 0.0
            else:
                il_usd = il.price_subtotal
                il_cup = il.price_subtotal * cup_rate
            ws3.write(r, 0, il.name or il.product_id.display_name or '', fv)
            ws3.write(r, 1, self.currency_id.name if self.currency_id else '', fv)
            ws3.write_number(r, 2, il_usd, fm)
            ws3.write_number(r, 3, il_cup, fm)
            grand_usd += il_usd
            grand_cup += il_cup
            r += 1
        r += 1

        ws3.write(r, 0, 'TOTAL EN USD (FACTURA DEL PROVEEDOR)', flb)
        ws3.write_number(r, 2, cif_amount, fb)
        r += 1
        ws3.write(r, 0, 'TOTAL A PAGAR EN MN', flb)
        ws3.write_number(r, 3, grand_cup, fb)
        r += 2

        obs = 'FACTURA: %s  BL/ %s\nCONTENEDORES: %s' % (
            po.partner_ref or '' if po else '',
            bl_numbers,
            '; '.join(containers.mapped('name') if containers else []),
        )
        ws3.write(r, 0, 'OBSERVACIONES:', fl)
        r += 1
        ws3.merge_range(r, 0, r + 2, 3, obs, fv)
        r += 4

        invoicing_user = (self.invoice_user_id or self.create_uid).name or ''
        ws3.write(r, 2, 'FACTURADO POR:', fl)
        r += 2
        ws3.write(r, 2, invoicing_user, fsig)
        r += 1
        ws3.write(r, 2, 'Especialista Comercial', fv)

        wb.close()
        output.seek(0)
        data = base64.b64encode(output.read())

        filename = ('Factura_ETEC_%s.xlsx' % (self.name or self.id)).replace('/', '_')
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

