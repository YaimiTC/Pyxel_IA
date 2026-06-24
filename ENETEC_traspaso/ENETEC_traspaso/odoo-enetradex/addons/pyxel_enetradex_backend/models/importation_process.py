from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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
    en_customer_accredited = fields.Boolean(
        related='customer_id.is_accredited', string="Cliente acreditado", readonly=True)
    en_provider_accredited = fields.Boolean(
        related='provider_id.is_accredited', string="Proveedor acreditado", readonly=True)
    # Texto resumen de quién falta por acreditar (para tarjeta y formulario).
    en_accreditation_status = fields.Char(
        compute='_compute_en_accreditation_status', string="Estado de acreditación")
    # Documentos del embarque subidos desde el wizard (Oferta, Factura comercial,
    # Lista de empaque...). Los revisa un comercial. Validación por IA pendiente.
    en_shipment_doc_ids = fields.Many2many(
        'ir.attachment', compute='_compute_en_shipment_docs',
        string="Documentos del embarque")
    en_shipment_doc_count = fields.Integer(
        compute='_compute_en_shipment_docs', string="N.º documentos del embarque")

    # Expediente estructurado de documentos (IA + comercial).
    en_import_document_ids = fields.One2many(
        'pyxel.import.document', 'importation_id',
        string="Expediente de documentos")
    # Sublistas filtradas para la vista.
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
        compute='_compute_en_import_doc_count', string="Documentos del expediente")
    en_import_doc_approved = fields.Integer(
        compute='_compute_en_import_doc_count', string="Documentos aprobados")
    en_import_docs_ready = fields.Boolean(
        compute='_compute_en_import_doc_count', store=True,
        string="Expediente listo")

    @api.depends('en_import_document_ids.portal_state')
    def _compute_en_import_doc_count(self):
        for rec in self:
            docs = rec.en_import_document_ids
            rec.en_import_doc_count = len(docs)
            approved = len(docs.filtered(lambda d: d.portal_state == 'approved'))
            rec.en_import_doc_approved = approved
            rec.en_import_docs_ready = bool(docs) and approved == len(docs)

    # Campos de la Declaración de Mercancía (los rellena el apoderado de aduana).
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
        # Implementación base: siempre False hasta que pyxel_customs_agent
        # sobreescribe este método con la lógica de dm_confirmed.
        for rec in self:
            rec.en_customs_dm_done = False

    # True cuando: solicitud aprobada + BL/AWB aprobado + oferta/factura/lista de OC aprobados.
    en_ready_for_customs = fields.Boolean(
        compute='_compute_en_ready_for_customs', store=True,
        string='Lista para despacho aduanero')

    @api.depends('en_request_approved',
                 'en_import_document_ids.document_key',
                 'en_import_document_ids.portal_state')
    def _compute_en_ready_for_customs(self):
        required_keys = {'bl_awb', 'factura_comercial', 'lista_empaque'}
        for rec in self:
            if not rec.en_request_approved:
                rec.en_ready_for_customs = False
                continue
            approved_keys = {
                d.document_key
                for d in rec.en_import_document_ids
                if d.portal_state == 'approved'
            }
            rec.en_ready_for_customs = required_keys.issubset(approved_keys)

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
            if not rec.en_import_document_ids:
                self.env['pyxel.import.document'].build_expediente(rec)

    # --- Datos de la solicitud de importación (capturados en el wizard) ---
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
    # Líneas de producto de la solicitud (multiproducto).
    en_request_line_ids = fields.One2many(
        'en.import.request.line', 'process_id', string="Productos solicitados")

    # --- Generación de órdenes al aprobar la solicitud ---
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
                 'customer_id', 'provider_id')
    def _compute_en_can_approve_request(self):
        solic = self.env.ref('pyxel_import_backend.importation_stage_solicitud',
                             raise_if_not_found=False)
        for rec in self:
            rec.en_can_approve_request = bool(
                solic and rec.stage_id.id == solic.id
                and rec.en_both_accredited and not rec.en_request_approved
                and rec.customer_id and rec.provider_id)

    def _en_request_lines_for_orders(self):
        """Líneas de mercancía para PO/oferta. Usa las líneas multiproducto y, si
        no hay, cae al producto/cantidad único (compatibilidad)."""
        self.ensure_one()
        lines = []
        for ln in self.en_request_line_ids:
            if ln.product_id:
                lines.append((ln.product_id, ln.qty or 0.0))
        if not lines and self.en_requested_product_id:
            lines.append((self.en_requested_product_id, self.en_requested_qty or 0.0))
        return lines

    def action_en_approve_request(self):
        """Decisión del comercial: aprueba la solicitud, crea la orden de compra
        (ENETEC → proveedor) y la oferta de venta al cliente (ENETEC → cliente),
        ambas en BORRADOR, y mueve la operación a «SOLICITUDES APROBADAS».
        El precio de la mercancía se rellenará en fase 2 (extracción por IA)."""
        Stage = self.env['importation.stage']
        approved_stage = self.env.ref(
            'pyxel_import_backend.importation_stage_tramites_origen',
            raise_if_not_found=False)
        PO = self.env['purchase.order']
        SO = self.env['sale.order']
        margin_product = self.env.ref(
            'pyxel_enetradex_backend.en_product_margin', raise_if_not_found=False)
        for rec in self:
            if rec.en_request_approved:
                raise ValidationError(_("La solicitud «%s» ya fue aprobada.") % rec.name)
            if not rec.en_both_accredited:
                raise ValidationError(_(
                    "No se puede aprobar: %s") % rec.en_accreditation_status)
            if not (rec.customer_id and rec.provider_id):
                raise ValidationError(_("Faltan cliente o proveedor en la solicitud."))
            goods = rec._en_request_lines_for_orders()
            ccy = rec.en_operation_currency_id or rec.currency_id

            # 1) Orden de compra: ENETEC compra al proveedor (precio = oferta del
            #    proveedor; se completará en fase 2 con la extracción por IA).
            po_lines = [(0, 0, {
                'product_id': p.id, 'name': p.display_name,
                'product_qty': q or 0.0, 'price_unit': 0.0,
                'product_uom': p.uom_po_id.id or p.uom_id.id,
            }) for p, q in goods]
            po = PO.create({
                'partner_id': rec.provider_id.id,
                'importation_id': rec.id,
                'currency_id': ccy.id if ccy else False,
                'origin': rec.name,
                'order_line': po_lines,
            })

            # 2) Oferta de venta al cliente: mercancía + gastos asociados + margen.
            so_lines = [(0, 0, {
                'product_id': p.id, 'name': p.display_name,
                'product_uom_qty': q or 0.0, 'price_unit': 0.0,
                'product_uom': p.uom_id.id,
            }) for p, q in goods]
            # Gastos asociados a la importación (líneas de costo del proceso).
            for cl in rec.cost_line_ids:
                if not cl.product_id:
                    continue
                so_lines.append((0, 0, {
                    'product_id': cl.product_id.id,
                    'name': _("Gasto: %s") % (cl.name or cl.product_id.display_name),
                    'product_uom_qty': 1.0,
                    'price_unit': cl.amount or 0.0,
                    'product_uom': cl.product_id.uom_id.id,
                }))
            # Línea de margen/comisión de ENETEC (% sobre la mercancía).
            if margin_product:
                so_lines.append((0, 0, {
                    'product_id': margin_product.id,
                    'name': _("Margen ENETEC (%.2f%%)") % (rec.en_margin_percent or 0.0),
                    'product_uom_qty': 1.0,
                    'price_unit': 0.0,  # = margen% * mercancía (fase 2, con precios)
                    'product_uom': margin_product.uom_id.id,
                }))
            so_vals = {
                'partner_id': rec.customer_id.id,
                'importation_process_id': rec.id,
                'order_type': 'importation_process',
                'origin': rec.name,
                'order_line': so_lines,
            }
            if ccy:
                so_vals['pricelist_id'] = rec._en_pricelist_for_currency(ccy).id
                so_vals['currency_id'] = ccy.id
            so = SO.create(so_vals)

            rec.en_client_sale_order_id = so.id

            # 3) Precargar las líneas de costos: una por cada producto de la
            #    categoría "Costos de importación" (el comercial pone el monto).
            cost_categ = self.env.ref(
                'pyxel_enetradex_backend.en_product_categ_import_cost',
                raise_if_not_found=False)
            if cost_categ and not rec.cost_line_ids:
                cost_products = self.env['product.product'].search([
                    ('categ_id', 'child_of', cost_categ.id),
                    ('detailed_type', '=', 'service')])
                for cp in cost_products:
                    rec.cost_line_ids = [(0, 0, {
                        'product_id': cp.id, 'amount': 0.0,
                        'distribution_type': 'fixed',
                    })]

            rec.en_request_approved = True
            if approved_stage:
                rec.with_context(en_auto_event=True, en_skip_expediente_gate=True).stage_id = approved_stage.id
        return True

    @api.model
    def _en_pricelist_for_currency(self, ccy):
        """Tarifario para una moneda (en Odoo la moneda de la venta viene del
        tarifario). Reutiliza uno existente o crea uno para esa moneda."""
        PL = self.env['product.pricelist'].sudo()
        pl = PL.search([('currency_id', '=', ccy.id)], limit=1)
        if not pl:
            pl = PL.create({'name': 'ENETEC %s' % ccy.name, 'currency_id': ccy.id})
        return pl

    def action_create_cost_sale_order(self):
        """Genera la(s) venta(s) de costos al cliente. Como una factura/venta tiene
        una sola moneda, se agrupan las líneas de costo por su moneda y se crea
        UNA venta por cada moneda (p. ej. una en USD y otra en CUP)."""
        self.ensure_one()
        if self.sale_order_id and not self.customer_id:
            return super().action_create_cost_sale_order()
        partner = self.customer_id or self.sale_order_id.partner_id
        if not partner:
            raise ValidationError(_("Falta el cliente en la solicitud de importación."))
        default_ccy = self.en_operation_currency_id or self.currency_id

        # Agrupar por moneda -> {ccy_id: {ccy, prods: {product_id: {...}}}}
        by_currency = {}
        for cost_line in self.cost_line_ids:
            if not cost_line.purchase_ids:
                continue  # sin órdenes asociadas, no se reparte
            total_value = 0.0
            if cost_line.distribution_type == 'fixed':
                total_value = cost_line.amount * len(cost_line.purchase_ids)
            elif cost_line.distribution_type == 'percentage':
                for purchase in cost_line.purchase_ids:
                    total_value += purchase.amount_total * (cost_line.amount / 100.0)
            ccy = cost_line.currency_id or default_ccy
            grp = by_currency.setdefault(ccy.id, {'ccy': ccy, 'prods': {}})
            pa = grp['prods'].setdefault(cost_line.product_id.id, {
                'product': cost_line.product_id, 'price_unit': 0.0,
                'name': cost_line.name or cost_line.product_id.name})
            pa['price_unit'] += total_value

        if not by_currency:
            raise ValidationError(_(
                "No hay costos con órdenes de compra asociadas para facturar."))

        SaleOrder = self.env['sale.order']
        created = SaleOrder
        for grp in by_currency.values():
            pl = self._en_pricelist_for_currency(grp['ccy'])
            new_lines = [(0, 0, {
                'product_id': val['product'].id, 'name': val['name'],
                'product_uom_qty': 1.0, 'price_unit': val['price_unit'],
                'product_uom': val['product'].uom_id.id,
            }) for val in grp['prods'].values()]

            existing = SaleOrder.search([
                ('importation_process_id', '=', self.id),
                ('is_cost_order', '=', True),
                ('currency_id', '=', grp['ccy'].id),
            ], limit=1)

            if existing:
                # Forzar a borrador sin tocar facturas (Odoo gestiona el resto nativamente)
                if existing.state not in ('draft', 'sent'):
                    existing.sudo().write({'state': 'draft'})
                # Actualizar líneas existentes por producto, agregar las nuevas
                lines_by_product = {l.product_id.id: l for l in existing.order_line}
                for val in grp['prods'].values():
                    pid = val['product'].id
                    if pid in lines_by_product:
                        lines_by_product[pid].write({
                            'price_unit': val['price_unit'],
                            'name': val['name'],
                        })
                    else:
                        existing.write({'order_line': [(0, 0, {
                            'product_id': pid,
                            'name': val['name'],
                            'product_uom_qty': 1.0,
                            'price_unit': val['price_unit'],
                            'product_uom': val['product'].uom_id.id,
                        })]})
                so = existing
            else:
                so = SaleOrder.create({
                    'partner_id': partner.id,
                    'importation_process_id': self.id,
                    'origin': self.name,
                    'order_type': 'importation_process',
                    'pricelist_id': pl.id,
                    'currency_id': grp['ccy'].id,
                    'is_cost_order': True,
                    'order_line': new_lines,
                })
            created |= so
        if created:
            self.final_sale_order_id = created[0].id
        return {
            'type': 'ir.actions.act_window', 'name': _("Ventas de costos"),
            'res_model': 'sale.order',
            'domain': [('id', 'in', created.ids)],
            'view_mode': 'tree,form' if len(created) > 1 else 'form',
            'res_id': created.id if len(created) == 1 else False,
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

    @api.depends('customer_id.is_accredited', 'provider_id.is_accredited')
    def _compute_en_both_accredited(self):
        for rec in self:
            cli_ok = (not rec.customer_id) or rec.customer_id.is_accredited
            prov_ok = (not rec.provider_id) or rec.provider_id.is_accredited
            rec.en_both_accredited = bool(cli_ok and prov_ok)

    @api.depends('customer_id.is_accredited', 'provider_id.is_accredited',
                 'customer_id.name', 'provider_id.name')
    def _compute_en_accreditation_status(self):
        for rec in self:
            faltan = []
            if rec.customer_id and not rec.customer_id.is_accredited:
                faltan.append(_("cliente «%s»") % rec.customer_id.name)
            if rec.provider_id and not rec.provider_id.is_accredited:
                faltan.append(_("proveedor «%s»") % rec.provider_id.name)
            if not faltan:
                rec.en_accreditation_status = _("Ambas partes acreditadas")
            else:
                rec.en_accreditation_status = _("Falta por acreditar: %s") % _(" y ").join(faltan)

    @api.model_create_multi
    def create(self, vals_list):
        # Etapa inicial: si AMBAS partes ya están acreditadas, la operación entra
        # directa a "SOLICITUDES PARA ATENDER" (operar con contrapartes acreditadas);
        # si falta alguna, entra al gate "Pendiente de acreditación".
        gate = self.env.ref('pyxel_enetradex_backend.en_stage_pending_accreditation',
                             raise_if_not_found=False)
        solic = self.env.ref('pyxel_import_backend.importation_stage_solicitud',
                              raise_if_not_found=False)
        Partner = self.env['res.partner']
        for vals in vals_list:
            if not vals.get('stage_id'):
                cust = Partner.browse(vals['customer_id']) if vals.get('customer_id') else Partner
                prov = Partner.browse(vals['provider_id']) if vals.get('provider_id') else Partner
                both = (not cust or cust.is_accredited) and (not prov or prov.is_accredited)
                if both and solic:
                    vals['stage_id'] = solic.id
                elif gate:
                    vals['stage_id'] = gate.id
        records = super().create(vals_list)
        # Seguimiento: primer evento de la operación en la línea de tiempo del cliente.
        Ev = self.env['en.tracking.event']
        for rec in records:
            Ev.en_log_event(
                rec, 'importation', rec.stage_id.name, rec.customer_id,
                source='auto', event_type='created',
                note="Operación de importación registrada.")
        # Crear expediente de documentos para todos los procesos nuevos.
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
        """Cuando se acredita una empresa, sus operaciones en el gate avanzan a
        "SOLICITUDES PARA ATENDER" — pero SOLO las que ya tienen acreditadas a
        AMBAS partes (la operación común espera a que aprueben a los dos)."""
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
        # No se puede avanzar a una etapa operable (después del gate) si cliente
        # y proveedor no están ambos acreditados.
        gate = self.env.ref('pyxel_enetradex_backend.en_stage_pending_accreditation',
                             raise_if_not_found=False)
        if not gate:
            return
        for rec in self:
            if rec.stage_id and rec.stage_id.id != gate.id and rec.stage_id.sequence > gate.sequence:
                if not rec.en_both_accredited:
                    faltan = []
                    if rec.customer_id and not rec.customer_id.is_accredited:
                        faltan.append(_("el cliente «%s»") % rec.customer_id.name)
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
