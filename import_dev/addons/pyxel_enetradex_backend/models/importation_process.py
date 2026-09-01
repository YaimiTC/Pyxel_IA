import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ImportationStage(models.Model):
    _inherit = 'importation.stage'

    # Marca la etapa "Pendiente de acreditación" (gate).
    en_is_gate_stage = fields.Boolean(string="Etapa gate (pendiente de acreditación)")


class ImportationCostLine(models.Model):
    _inherit = 'importation.cost.line'

    # Moneda por línea de costo (editable): permite facturar unos costos en CUP y
    # otros en USD. Antes era related (solo lectura) a la moneda del proceso;
    # se limpia el related y se hace almacenada y editable.
    currency_id = fields.Many2one(
        'res.currency', string="Moneda", required=True,
        related=False, store=True, readonly=False,
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))


class ImportationProcess(models.Model):
    _inherit = 'importation.process'

    en_both_accredited = fields.Boolean(
        compute='_compute_en_both_accredited', string="Ambas partes acreditadas", store=False)
    en_provider_pending = fields.Boolean(
        compute='_compute_en_pending', string="Pendiente proveedor", store=False)
    en_customer_pending = fields.Boolean(
        compute='_compute_en_pending', string="Pendiente cliente", store=False)
    en_customer_accredited = fields.Boolean(
        related='customer_id.is_accredited', string="Cliente acreditado", readonly=True)
    en_customer_ids = fields.Many2many(
        'res.partner', compute='_compute_en_customer_ids', string="Clientes del envío")
    en_provider_accredited = fields.Boolean(
        related='provider_id.is_accredited', string="Proveedor acreditado", readonly=True)
    en_accreditation_status = fields.Char(
        compute='_compute_en_accreditation_status', string="Estado de acreditación")
    en_accreditation_pending = fields.Boolean(
        string="Acreditación por revisar", default=False, copy=False, index=True,
        help="Esta operación se registró por carga masiva sin que cliente y "
             "proveedor estuvieran acreditados. No es un error de datos: es "
             "trabajo pendiente de Comercial. Filtra por aquí para revisarlas.")
    en_shipment_doc_ids = fields.Many2many(
        'ir.attachment', compute='_compute_en_shipment_docs',
        string="Documentos del embarque")
    en_shipment_doc_count = fields.Integer(
        compute='_compute_en_shipment_docs', string="N.º documentos del embarque")

    en_import_document_ids = fields.One2many(
        'pyxel.import.document', 'importation_id',
        string="Expediente de documentos")
    en_import_process_doc_ids = fields.One2many(
        'pyxel.import.document', 'importation_id',
        domain=[('purchase_order_id', '=', False)],
        string="Documentos de la importación")
    en_import_oc_doc_ids = fields.One2many(
        'pyxel.import.document', 'importation_id',
        domain=[('purchase_order_id', '!=', False)],
        string="Documentos por Orden de Compra")
    en_import_dm_doc_ids = fields.One2many(
        'pyxel.import.document', 'importation_id',
        domain=[('document_key', '=', 'dm')],
        string='Declaraciones de Mercancía')
    en_import_doc_count = fields.Integer(
        compute='_compute_en_import_doc_counts', string="Documentos del expediente")
    en_import_doc_approved = fields.Integer(
        compute='_compute_en_import_doc_counts', string="Documentos aprobados")
    en_import_docs_ready = fields.Boolean(
        compute='_compute_en_import_docs_ready', store=True,
        string="Expediente listo")

    @api.depends('en_import_document_ids.portal_state')
    def _compute_en_import_doc_counts(self):
        for rec in self:
            docs = rec.en_import_document_ids
            rec.en_import_doc_count = len(docs)
            rec.en_import_doc_approved = len(docs.filtered(lambda d: d.portal_state == 'approved'))

    @api.depends('en_import_document_ids.portal_state')
    def _compute_en_import_docs_ready(self):
        for rec in self:
            docs = rec.en_import_document_ids
            approved = len(docs.filtered(lambda d: d.portal_state == 'approved'))
            rec.en_import_docs_ready = bool(docs) and approved == len(docs)

    en_dm_number = fields.Char(string='Número DM')
    en_dm_container_number = fields.Char(string='Contenedor (DM)')
    en_dm_cif_value = fields.Float(string='Valor CIF (USD)', digits=(16, 2))
    en_dm_arancel_total = fields.Float(string='Total aranceles (USD)', digits=(16, 2))
    en_dm_impuesto_circulacion = fields.Float(
        string='Impuesto circulación (USD)', digits=(16, 2))
    en_dm_arancel_notes = fields.Text(string='Notas arancelarias')
    en_dm_extraction_state = fields.Selection([
        ('pending',   'Sin DM'),
        ('manual',    'Datos manuales'),
        ('extracted', 'Extraído por IA'),
    ], string='Estado extracción DM', default='pending')

    en_customs_agent_id = fields.Many2one(
        'res.users', string='Apoderado asignado',
        domain=[('share', '=', False)])
    en_customs_dm_done = fields.Boolean(
        compute='_compute_en_customs_dm_done', store=True,
        string='DM completadas')

    @api.depends('en_import_dm_doc_ids')
    def _compute_en_customs_dm_done(self):
        for rec in self:
            rec.en_customs_dm_done = False

    en_ready_for_customs = fields.Boolean(
        compute='_compute_en_ready_for_customs', store=True,
        string='Lista para despacho aduanero')

    @api.depends('en_request_approved',
                 'en_import_document_ids.document_key',
                 'en_import_document_ids.portal_state',
                 'en_import_document_ids.purchase_order_id',
                 'purchase_order_ids')
    def _compute_en_ready_for_customs(self):
        oc_required_keys = {'bl_awb', 'factura_comercial', 'lista_empaque'}
        for rec in self:
            if not rec.en_request_approved or not rec.purchase_order_ids:
                rec.en_ready_for_customs = False
                continue
            ready = False
            for po in rec.purchase_order_ids:
                po_approved = {
                    d.document_key
                    for d in rec.en_import_document_ids
                    if d.purchase_order_id == po and d.portal_state == 'approved'
                }
                if oc_required_keys.issubset(po_approved):
                    ready = True
                    break
            rec.en_ready_for_customs = ready

    en_customs_stage_reached = fields.Boolean(
        compute='_compute_en_customs_stage_reached', store=True,
        string="En tránsito a destino o posterior")

    @api.depends('stage_id')
    def _compute_en_customs_stage_reached(self):
        transito = self.env.ref(
            'pyxel_import_backend.importation_stage_transito_puerto',
            raise_if_not_found=False)
        for rec in self:
            rec.en_customs_stage_reached = bool(
                transito and rec.stage_id and rec.stage_id.sequence >= transito.sequence)

    def _check_import_expediente_complete(self):
        """Llamado al aprobar un documento: notifica si el expediente quedó completo."""
        for rec in self:
            required = rec.en_import_document_ids.filtered('is_required')
            if required and all(d.portal_state == 'approved' for d in required):
                rec.message_post(
                    body=_("Expediente de importación completo: todos los documentos "
                           "obligatorios han sido aprobados."),
                    message_type='notification')

    def action_create_import_expediente(self):
        for rec in self:
            self.env['pyxel.import.document'].build_expediente(rec)

    en_requested_product_id = fields.Many2one(
        'product.product', string="Producto solicitado")
    en_requested_qty = fields.Float(string="Cantidad solicitada")
    en_packaging_type = fields.Selection(
        [('isotanque', 'Isotanque'), ('isomodulo', 'Isomódulo')],
        string="Tipo de envase")
    en_delivery_date = fields.Date(string="Fecha de entrega deseada")
    en_payment_method_id = fields.Many2one(
        'en.payment.method', string="Forma de pago")
    en_currency_usd_id = fields.Many2one(
        'res.currency', string="Moneda (USD)", readonly=True,
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))
    en_budget_usd = fields.Monetary(
        string="Presupuesto disponible (USD)", currency_field='en_currency_usd_id')
    en_specifications = fields.Text(string="Especificaciones")
    en_observations = fields.Text(string="Observaciones")
    en_request_line_ids = fields.One2many(
        'en.import.request.line', 'process_id', string="Productos solicitados")
    en_request_client_ids = fields.One2many(
        'en.import.request.client', 'process_id', string="Clientes del envío")

    en_operation_currency_id = fields.Many2one(
        'res.currency', string="Moneda de la operación",
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        help="Moneda en que se emiten la orden de compra y la oferta al cliente.")
    en_margin_percent = fields.Float(
        string="Margen ENETEC (%)",
        default=lambda self: self.env.company.en_import_margin_percent,
        help="Comisión/margen aplicado a la oferta de venta al cliente.")
    en_client_sale_order_id = fields.Many2one(
        'sale.order', string="Oferta de venta al cliente", readonly=True, copy=False)

    def _compute_cost_sale_order_count(self):
        for rec in self:
            rec.cost_sale_order_count = self.env['sale.order'].search_count([
                ('importation_process_id', '=', rec.id),
                ('is_cost_order', '=', True),
            ])

    en_request_approved = fields.Boolean(
        string="Solicitud aprobada", readonly=True, copy=False)
    en_can_approve_request = fields.Boolean(
        compute='_compute_en_can_approve_request', string="Puede aprobar solicitud")

    @api.depends('stage_id', 'en_both_accredited', 'en_request_approved',
                 'en_request_client_ids.customer_id', 'customer_id', 'provider_id')
    def _compute_en_can_approve_request(self):
        solic = self.env.ref('pyxel_import_backend.importation_stage_solicitud',
                             raise_if_not_found=False)
        for rec in self:
            has_customer = bool(rec.en_request_client_ids.customer_id or rec.customer_id)
            rec.en_can_approve_request = bool(
                solic and rec.stage_id.id == solic.id
                and rec.en_both_accredited and not rec.en_request_approved
                and has_customer and rec.provider_id)

    def _en_request_lines_for_orders(self):
        self.ensure_one()
        lines = []
        for ln in self.en_request_line_ids:
            if ln.product_id:
                lines.append((ln.product_id, ln.qty or 0.0))
        if not lines and self.en_requested_product_id:
            lines.append((self.en_requested_product_id, self.en_requested_qty or 0.0))
        return lines

    def action_en_approve_request(self):
        approved_stage = self.env.ref(
            'pyxel_import_backend.importation_stage_tramites_origen',
            raise_if_not_found=False)
        PO = self.env['purchase.order']

        for rec in self:
            if rec.en_request_approved:
                raise ValidationError(_("La solicitud «%s» ya fue aprobada.") % rec.name)
            if not rec.en_both_accredited:
                if not self.env.context.get('en_carga_masiva'):
                    raise ValidationError(_(
                        "No se puede aprobar: %s") % rec.en_accreditation_status)
                rec.en_accreditation_pending = True
                _logger.warning(
                    "Carga masiva: %s aprobada SIN acreditación completa (%s). "
                    "Queda marcada para que Comercial la revise.",
                    rec.name, rec.en_accreditation_status)
            elif rec.en_accreditation_pending:
                rec.en_accreditation_pending = False
            if not rec.provider_id:
                raise ValidationError(_("Falta el proveedor en la solicitud."))

            client_blocks = rec.en_request_client_ids
            if not client_blocks:
                if not rec.customer_id:
                    raise ValidationError(_("Faltan cliente o bloques de cliente en la solicitud."))
                client_blocks = self.env['en.import.request.client'].new({
                    'process_id': rec.id,
                    'customer_id': rec.customer_id.id,
                    'product_line_ids': [],
                })
                client_blocks = [client_blocks]
                use_legacy_lines = True
            else:
                use_legacy_lines = False

            default_ccy = rec.en_operation_currency_id or rec.currency_id

            for block in client_blocks:
                customer = block.customer_id
                if not customer:
                    continue

                ccy_op = block.en_operation_currency_id or default_ccy

                if use_legacy_lines:
                    goods = rec._en_request_lines_for_orders()
                else:
                    goods = [
                        (ln.product_id, ln.qty or 0.0)
                        for ln in block.product_line_ids if ln.product_id
                    ]

                po = block.purchase_order_id if (not use_legacy_lines and block.purchase_order_id) else False
                if not po:
                    po_lines = [(0, 0, {
                        'product_id': p.id, 'name': p.display_name,
                        'product_qty': q or 0.0, 'price_unit': 0.0,
                        'product_uom': p.uom_po_id.id or p.uom_id.id,
                        'taxes_id': [(6, 0, [])],
                    }) for p, q in goods]
                    po = PO.create({
                        'partner_id': rec.provider_id.id,
                        'customer_id': customer.id,
                        'importation_id': rec.id,
                        'bl_number': block.bl_number or False,
                        'currency_id': ccy_op.id if ccy_op else False,
                        'origin': rec.name,
                        'order_line': po_lines,
                    })
                    if not use_legacy_lines:
                        block.purchase_order_id = po.id

                # Al crear la OC se construye automáticamente su bloque en el
                # expediente y se pre-enlazan los archivos del bloque de solicitud.
                self.env['pyxel.import.document'].build_oc_expediente(po)

            # Certificados a nivel de proceso (calidad, exportación, origen):
            # se crean al aprobar para que aparezcan en el expediente desde el inicio.
            self.env['pyxel.import.document'].build_expediente(rec)

            rec.en_request_approved = True
            if approved_stage:
                rec.with_context(en_auto_event=True, en_skip_expediente_gate=True).stage_id = approved_stage.id
        return True

    @api.model
    def _en_pricelist_for_currency(self, ccy):
        PL = self.env['product.pricelist'].sudo()
        pl = PL.search([('currency_id', '=', ccy.id)], limit=1)
        if not pl:
            pl = PL.create({'name': 'ENETEC %s' % ccy.name, 'currency_id': ccy.id})
        return pl

    def action_create_cost_sale_order(self):
        """Genera (o actualiza) la oferta de venta al cliente con solo los
        costos de importación (margen comercial, etc.) — sin mercancía de las OC."""
        self.ensure_one()
        if not self.provider_id:
            raise ValidationError("Debe estar definido el proveedor en el proceso de importación.")

        ccy = self.en_operation_currency_id or self.currency_id

        product_amounts = {}
        for cost_line in self.cost_line_ids:
            if not cost_line.purchase_ids:
                continue
            total_value = 0.0
            if cost_line.distribution_type == 'fixed':
                total_value = cost_line.amount * len(cost_line.purchase_ids)
            elif cost_line.distribution_type == 'percentage':
                for purchase in cost_line.purchase_ids:
                    total_value += purchase.amount_total * (cost_line.amount / 100.0)
            product_id = cost_line.product_id.id
            if product_id not in product_amounts:
                product_amounts[product_id] = {
                    'product': cost_line.product_id,
                    'price_unit': 0.0,
                    'name': cost_line.name or cost_line.product_id.name,
                }
            product_amounts[product_id]['price_unit'] += total_value

        if not product_amounts:
            raise ValidationError(_("No hay costos con órdenes de compra asociadas para facturar."))

        order_lines = [(0, 0, {
            'product_id': val['product'].id,
            'name': val['name'],
            'product_uom_qty': 1.0,
            'price_unit': val['price_unit'],
            'product_uom': val['product'].uom_id.id,
        }) for val in product_amounts.values()]

        if self.final_sale_order_id:
            so = self.final_sale_order_id
            if so.state not in ('draft', 'sent'):
                so.sudo().write({'state': 'draft'})
            so.sudo().order_line.unlink()
            so.sudo().write({'order_line': order_lines})
        else:
            customers = self.en_request_client_ids.customer_id or self.customer_id
            partner = customers[:1] if customers else self.sale_order_id.partner_id
            if not partner:
                raise ValidationError(_(
                    "No se pudo determinar el cliente (partner_id) para la oferta de venta. "
                    "Añade al menos un cliente en la solicitud."))
            pl = self._en_pricelist_for_currency(ccy)
            so = self.env['sale.order'].create({
                'partner_id': partner.id,
                'importation_process_id': self.id,
                'origin': self.name,
                'order_type': 'importation_process',
                'pricelist_id': pl.id,
                'currency_id': ccy.id,
                'is_cost_order': True,
                'order_line': order_lines,
            })
            self.final_sale_order_id = so.id

        return {
            'type': 'ir.actions.act_window',
            'name': _("Ventas"),
            'res_model': 'sale.order',
            'res_id': so.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _compute_en_shipment_docs(self):
        Att = self.env['ir.attachment']
        for rec in self:
            atts = Att.search([
                ('res_model', '=', 'importation.process'),
                ('res_id', '=', rec.id)]) if rec.id else Att
            rec.en_shipment_doc_ids = atts
            rec.en_shipment_doc_count = len(atts)

    @api.depends('en_request_client_ids.customer_id.is_accredited',
                 'customer_id.is_accredited', 'provider_id.is_accredited')
    def _compute_en_both_accredited(self):
        for rec in self:
            customers = rec.en_request_client_ids.customer_id or rec.customer_id
            cli_ok = all(c.is_accredited for c in customers) if customers else True
            prov_ok = (not rec.provider_id) or rec.provider_id.is_accredited
            rec.en_both_accredited = bool(cli_ok and prov_ok)

    @api.depends('en_request_client_ids.customer_id.is_accredited',
                 'customer_id.is_accredited', 'provider_id.is_accredited')
    def _compute_en_pending(self):
        for rec in self:
            rec.en_provider_pending = bool(rec.provider_id) and not rec.provider_id.is_accredited
            customers = rec.en_request_client_ids.customer_id or rec.customer_id
            rec.en_customer_pending = bool(customers) and not all(c.is_accredited for c in customers)

    @api.depends('en_request_client_ids.customer_id.is_accredited',
                 'en_request_client_ids.customer_id.name',
                 'customer_id.is_accredited', 'provider_id.is_accredited',
                 'customer_id.name', 'provider_id.name')
    def _compute_en_accreditation_status(self):
        for rec in self:
            customers = rec.en_request_client_ids.customer_id or rec.customer_id
            faltan = []
            no_acreditados = [c.name for c in customers if not c.is_accredited]
            if no_acreditados:
                faltan.append(_("cliente(s) «%s»") % ", ".join(no_acreditados))
            if rec.provider_id and not rec.provider_id.is_accredited:
                faltan.append(_("proveedor «%s»") % rec.provider_id.name)
            if not faltan:
                rec.en_accreditation_status = _("Ambas partes acreditadas")
            else:
                rec.en_accreditation_status = _("Falta por acreditar: %s") % _(" y ").join(faltan)

    @api.depends('en_request_client_ids.customer_id', 'customer_id')
    def _compute_en_customer_ids(self):
        for rec in self:
            rec.en_customer_ids = rec.en_request_client_ids.customer_id or rec.customer_id

    @api.model_create_multi
    def create(self, vals_list):
        gate = self.env.ref('pyxel_enetradex_backend.en_stage_pending_accreditation',
                             raise_if_not_found=False)
        solic = self.env.ref('pyxel_import_backend.importation_stage_solicitud',
                              raise_if_not_found=False)
        Partner = self.env['res.partner']
        for vals in vals_list:
            if not vals.get('stage_id'):
                block_customer_ids = [
                    cmd[2]['customer_id']
                    for cmd in (vals.get('en_request_client_ids') or [])
                    if isinstance(cmd, (list, tuple)) and len(cmd) >= 3
                    and cmd[0] == 0 and isinstance(cmd[2], dict) and cmd[2].get('customer_id')
                ]
                if block_customer_ids:
                    customers = Partner.browse(block_customer_ids)
                else:
                    customers = Partner.browse(vals['customer_id']) if vals.get('customer_id') else Partner
                prov = Partner.browse(vals['provider_id']) if vals.get('provider_id') else Partner
                both = (not customers or all(c.is_accredited for c in customers)) and (not prov or prov.is_accredited)
                if both and solic:
                    vals['stage_id'] = solic.id
                elif gate:
                    vals['stage_id'] = gate.id
        records = super().create(vals_list)
        Ev = self.env['en.tracking.event']
        for rec in records:
            Ev.en_log_event(
                rec, 'importation', rec.stage_id.name, rec.customer_id,
                source='auto', event_type='created',
                note="Operación de importación registrada.")
        self.env['pyxel.import.document'].build_expediente(records)
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('stage_id'):
            auto = self.env.context.get('en_auto_event')
            Ev = self.env['en.tracking.event']
            for rec in self:
                Ev.en_log_event(
                    rec, 'importation', rec.stage_id.name, rec.customer_id,
                    source='auto' if auto else 'manual')
        return res

    @api.model
    def _en_advance_for_partners(self, partners):
        gate = self.env.ref('pyxel_enetradex_backend.en_stage_pending_accreditation',
                             raise_if_not_found=False)
        solic = self.env.ref('pyxel_import_backend.importation_stage_solicitud',
                              raise_if_not_found=False)
        if not gate or not solic or not partners:
            return
        ops = self.search([
            ('stage_id', '=', gate.id),
            '|', ('customer_id', 'in', partners.ids), ('provider_id', 'in', partners.ids)])
        for op in ops:
            if op.en_both_accredited:
                op.with_context(en_auto_event=True).write({'stage_id': solic.id})

    @api.constrains('stage_id', 'customer_id', 'provider_id')
    def _check_en_accreditation_gate(self):
        if self.env.context.get('en_carga_masiva'):
            return
        gate = self.env.ref('pyxel_enetradex_backend.en_stage_pending_accreditation',
                             raise_if_not_found=False)
        if not gate:
            return
        for rec in self:
            if rec.stage_id and rec.stage_id.id != gate.id and rec.stage_id.sequence > gate.sequence:
                if not rec.en_both_accredited:
                    faltan = []
                    unaccredited_clients = (rec.en_request_client_ids.customer_id or rec.customer_id).filtered(
                        lambda c: not c.is_accredited)
                    if unaccredited_clients:
                        faltan.append(_("el cliente «%s»") % _(", ").join(unaccredited_clients.mapped('name')))
                    if rec.provider_id and not rec.provider_id.is_accredited:
                        faltan.append(_("el proveedor «%s»") % rec.provider_id.name)
                    raise ValidationError(_(
                        "No se puede avanzar la operación «%(ref)s» a «%(etapa)s»: "
                        "todavía falta acreditar %(faltan)s. La operación permanece en "
                        "«PENDIENTE DE ACREDITACIÓN» hasta que acrediten a esa parte.") % {
                            'ref': rec.name,
                            'etapa': rec.stage_id.name,
                            'faltan': _(" y ").join(faltan),
                        })
