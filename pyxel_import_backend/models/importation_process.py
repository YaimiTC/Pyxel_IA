import json
from datetime import timedelta, datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

STATE_SELECTION = [
    ('new', 'New'),
    ('in_progress', 'Importation in Progress'),
    ('done', 'Completed'),
    ('cancelled', 'Cancelled'),
]


class ImportationProcess(models.Model):
    _name = 'importation.process'
    _description = 'Importation Process'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, default='New')
    stage_id = fields.Many2one('importation.stage', string='Process Stage',
                               default=lambda self: self.env['importation.stage'].search([], limit=1),
                               group_expand='_group_expand_stage_id',
                               ondelete='restrict', tracking=True)
    state = fields.Selection(
        STATE_SELECTION,
        string='State',
        default='new',
        tracking=True,
    )
    purchase_order_ids = fields.Many2many('purchase.order', string='Purchase Orders')
    purchase_order_count = fields.Integer(string='Purchase Order Count', compute='_compute_purchase_order_count')
    cost_line_ids = fields.One2many('importation.cost.line', 'importation_id', string='Additional Costs')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_total_cost')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    sale_order_id = fields.Many2one('sale.order', string='Evaluation Quotation')

    origin_sale_order_id = fields.Many2one('sale.order', string="Origin Quotation",
                                           compute="_compute_origin_sale_order_id", store=True)

    @api.depends('sale_order_id')
    def _compute_origin_sale_order_id(self):
        for rec in self:
            # Aquí se asume que la evaluación tiene una relación hacia la venta original
            rec.origin_sale_order_id = rec.sale_order_id.evaluation_apply_id.sale_order_id \
                if rec.sale_order_id and rec.sale_order_id.evaluation_apply_id else False

    final_sale_order_id = fields.Many2one('sale.order', string='Final Generated Offer', readonly=True)
    customer_id = fields.Many2one('res.partner', string='Customer', required=False)
    provider_id = fields.Many2one('res.partner', string='Supplier', required=True)

    country_origin_id = fields.Many2one('res.country', string='Country of Origin', required=True)

    declaration = fields.Char(string='Goods Declaration')

    estimated_start_date = fields.Date(string='Estimated Start Date', required=True)
    estimated_end_date = fields.Date(string='Estimated End Date', required=True)
    departure_date = fields.Date(string='Departure Date from Origin')
    declaration_date = fields.Date(string='Goods Declaration Date')
    documentation_sent_date = fields.Date(string='Documentation Sent Date')

    date_import_closed = fields.Date(string='Date on which the import closed')

    filtered_airport = fields.Char(default=json.dumps([]), store=True)
    filtered_port = fields.Char(default=json.dumps([]), store=True)

    port = fields.Many2one(comodel_name='transport.hub', string='Port')
    airport = fields.Many2one(comodel_name='transport.hub', string='Airport')

    purchase_condition = fields.Selection([
        ('FCL', 'FCL'),
        ('AWB', 'AWB'),
        ('LCL', 'LCL'),
        ('DAP', 'DAP'),
    ], string='Purchase Condition', default='FCL')

    purchase_condition_number = fields.Char(string='Number/Reference by Condition')

    is_third_party_contract = fields.Boolean(
        string='Third-Party Contract',
        compute='_compute_is_third_party_contract',
        store=True
    )
    # Attached documents
    origin_certificate = fields.Binary(string='Certificate of Origin')
    origin_certificate_filename = fields.Char()

    export_certificate = fields.Binary(string='Export Certificate')
    export_certificate_filename = fields.Char()

    quality_certificate = fields.Binary(string='Quality Certificate')
    quality_certificate_filename = fields.Char()

    documentation_file = fields.Binary(string='Documentation (FCL / AWB)')
    documentation_file_filename = fields.Char()

    packing_list = fields.Binary(string='Packing List')
    packing_list_filename = fields.Char()

    packing_list_filename_date = fields.Datetime(string="Packing List upload date")  # custom
    alerted_late = fields.Boolean(string="Packing List uploaded late", default=False)

    load_tracking_ids = fields.One2many(
        'importation.load',
        'importation_id',
        string="Cargo Model"
    )
    load_tracking_count = fields.Integer(string='Load Tracking Count', compute='_compute_load_tracking_count')

    sale_order_count = fields.Integer(string='Sale Orders Count', compute='_compute_sale_order_count')

    stage_enter_date = fields.Datetime(string="Stage date")
    days_in_stage = fields.Integer(string="State days", compute='_compute_days_in_stage', store=True)

    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')

    process_id = fields.Many2one(
        'sale.order.process',
        string="Process Related",
        compute='_compute_process_id',
        inverse='_inverse_process_id',
        store=True,
        readonly=False
    )

    filtered_incoterm = fields.Char(default=json.dumps([]), store=True)

    filtered_import_type = fields.Char(default=json.dumps([]), store=True)

    incoterm_id = fields.Many2one(string='Incoterm', comodel_name='account.incoterms')

    import_type_id = fields.Many2one(string='Import Type', comodel_name='import.type')

    incoterm_import_type_id = fields.Many2one(string='Incoterm - Import Type', comodel_name='incoterm.import.type',
                                              compute='_compute_incoterm_import_type')

    # Documentation block
    has_bl = fields.Boolean(string='BL', related='import_type_id.has_bl')
    has_awb = fields.Boolean(string='AWB', related='import_type_id.has_awb')
    has_packing_list = fields.Boolean(string='Packing List', related='import_type_id.has_packing_list')

    has_quality_certificate = fields.Boolean(string='Quality Certificate',
                                             related='import_type_id.has_quality_certificate')
    has_export_certificate = fields.Boolean(string='Export Certificate',
                                            related='import_type_id.has_export_certificate')
    has_origin_certificate = fields.Boolean(string='Origin Certificate',
                                            related='import_type_id.has_origin_certificate')
    use_port = fields.Boolean(string='Use Port?', related='import_type_id.use_port')
    use_airport = fields.Boolean(string='Use Airport?', related='import_type_id.use_airport')

    @api.depends('final_sale_order_id.process_id')
    def _compute_process_id(self):
        for record in self:
            # Obtener el proceso de la orden final
            if record.final_sale_order_id and record.final_sale_order_id.process_id:
                record.process_id = record.final_sale_order_id.process_id
            else:
                record.process_id = False

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = self.env['sale.order'].search_count([
                '|',
                '|',
                ('id', '=', rec.origin_sale_order_id.id),
                ('id', '=', rec.sale_order_id.id),
                ('id', '=', rec.final_sale_order_id.id)
            ])

    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = self.env['account.move'].search_count([
                ('importation_process_id', '=', record.id)
            ])

    def action_view_related_invoices(self):
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('importation_process_id', '=', self.id)],
            'context': {
                'default_importation_process_id': self.id,
                'default_invoice_type': 'operative'
            },
        }

    @api.depends('stage_enter_date')
    def _compute_days_in_stage(self):
        for record in self:
            if record.stage_enter_date:
                delta = fields.Datetime.now() - record.stage_enter_date
                record.days_in_stage = delta.days
            else:
                record.days_in_stage = 0

    @api.constrains('estimated_start_date', 'estimated_end_date')
    def _check_date_range(self):
        for record in self:
            if record.estimated_start_date and record.estimated_end_date:
                if record.estimated_end_date < record.estimated_start_date:
                    raise ValidationError("The end date cannot be earlier than the start date.")

    def action_view_sale_orders(self):
        self.ensure_one()
        domain = ['|', '|', ('id', '=', self.origin_sale_order_id.id), ('id', '=', self.sale_order_id.id),
                  ('id', '=', self.final_sale_order_id.id)]
        return {
            'name': 'Sales Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'search_default_group_by_order_type': 1}
        }

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    def action_view_purchase_orders(self):
        self.ensure_one()
        domain = [('id', 'in', self.purchase_order_ids.ids)]
        return {
            'name': 'Purchase Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {}
        }

    @api.depends('load_tracking_ids')
    def _compute_load_tracking_count(self):
        for rec in self:
            rec.load_tracking_count = len(rec.load_tracking_ids)

    def action_view_load_tracking(self):
        self.ensure_one()
        domain = [('id', 'in', self.load_tracking_ids.ids)]
        return {
            'name': 'Load tracking',
            'type': 'ir.actions.act_window',
            'res_model': 'importation.load',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {}
        }

    @api.depends('cost_line_ids.amount')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(line.amount for line in rec.cost_line_ids)

    @api.model
    def _get_final_stage(self):
        """Obtiene la última etapa por secuencia"""
        return self.env['importation.stage'].search(
            [('is_final', '=', True)],
            order='sequence desc',
            limit=1
        )

    @api.model
    def create(self, vals):

        if vals.get('name', 'New') == 'New':
            sequence = self.env['ir.sequence'].next_by_code('importation.process')
            vals['name'] = sequence or 'New'

        return super().create(vals)

    def write(self, vals):
        # Validación de cambio de etapa

        # Preparar valores a actualizar en vals para evitar múltiples writes
        final_stage = self._get_final_stage()
        for record in self:
            # Si el archivo NO existe en el registro actual y no está explícito en vals, poner fecha a False
            if ('packing_list' in vals and not vals.get('packing_list')) or (
                    not record.packing_list and 'packing_list' not in vals):
                vals['packing_list_filename_date'] = False
            else:
                # Si el archivo existe y se está cambiando el archivo
                if 'packing_list_filename' in vals:
                    vals['packing_list_filename_date'] = fields.Datetime.now()

            if 'stage_id' in vals:
                if vals['stage_id'] == final_stage.id:
                    # Solo actualizar si no está ya cerrado
                    if not record.date_import_closed:
                        record.date_import_closed = fields.Date.today()
                else:
                    # Si sale de la etapa final, resetear fecha
                    if record.date_import_closed:
                        record.date_import_closed = False

            if 'date_import_closed' in vals and record.process_id:

                if not record.final_sale_order_id:
                    raise UserError("No se puede cerrar/reabrir importación sin Orden Final asignada")

                if not record.process_id:
                    raise UserError("No hay un Proceso asignado a esta importación")

                    # Cambiar estado del proceso
                if vals['date_import_closed']:  # Cierre
                    if record.process_id.state != 'closed':
                        # Actualizar proceso y registrar relación inversa
                        record.process_id.write({
                            'state': 'closed',
                            'importation_id': record.id
                        })
                else:  # Reapertura
                    if record.process_id.state == 'closed':
                        record.process_id.write({
                            'state': 'open',
                            'importation_id': False
                        })

        res = super().write(vals)

        # # Después de guardar, hacer validación para enviar alerta y mensajes (sin modificar registros)
        # for record in self:
        #     if record.packing_list_filename_date and record.documentation_sent_date:
        #         doc_sent_dt = datetime.combine(record.documentation_sent_date, datetime.min.time())
        #         delay = record.packing_list_filename_date - doc_sent_dt
        #         if delay.total_seconds() > 72 * 3600 and not record.alerted_late:
        #             # Enviar email y mensaje
        #             record._send_alert_email_to_creator()
        #             record.message_post(
        #                 body="⚠ El archivo 'Packing List' fue subido más de 72 horas después de la fecha de envío de la documentación.",
        #                 message_type="notification"
        #             )
        #             record.write({'alerted_late': True})

        return res

    def _send_alert_email_to_creator(self):
        template = self.env.ref('pyxel_import_backend.email_template_bl_upload_delay', raise_if_not_found=False)
        if template and self.create_uid and self.create_uid.partner_id.email:
            # Enviar correo
            template.send_mail(self.id, force_send=True)

    def action_start_progress(self):
        self.write({'state': 'in_progress'})

    def action_finish_progress(self):
        self.write({'state': 'done'})

    @api.model
    def _group_expand_stage_id(self, stages, domain, order):
        return self.env['importation.stage'].search([], order=order)

    def action_create_cost_sale_order(self):
        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']

        if not self.provider_id:
            raise ValidationError("Debe estar definido el proveedor en el proceso de importación.")

        product_amounts = {}

        for cost_line in self.cost_line_ids:
            total_value = 0.0

            if not cost_line.purchase_ids:
                continue  # si no hay órdenes asociadas, omitir

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

        # providers_names = self.purchase_order_ids.mapped('partner_id.name')

        # Crear el sale.order con líneas acumuladas por producto
        sale_order = SaleOrder.create({
            'partner_id': self.sale_order_id.partner_id.id,
            'importation_process_id': self.id,
            # 'providers_names':  ', '.join(sorted(set(providers_names))),
            'origin': self.name,
            'order_type': 'importation_process',
            'order_line': [(0, 0, {
                'product_id': val['product'].id,
                'name': val['name'],
                'product_uom_qty': 1.0,
                'price_unit': val['price_unit'],
                'product_uom': val['product'].uom_id.id,
            }) for val in product_amounts.values()]
        })

        self.final_sale_order_id = sale_order.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('purchase_order_ids.is_third_party_contract')
    def _compute_is_third_party_contract(self):
        for rec in self:
            if rec.purchase_order_ids:
                rec.is_third_party_contract = all(po.is_third_party_contract for po in rec.purchase_order_ids)
            else:
                rec.is_third_party_contract = False  # O True, según lo que prefieras por defecto si no hay compras

    @api.onchange('import_type_id')
    def _compute_available_incoterms(self):
        for record in self:
            domain = []
            if record.import_type_id:
                # Buscar relaciones activas entre import_type y incoterms
                relations = self.env['incoterm.import.type'].search([
                    ('import_type_id', '=', record.import_type_id.id),
                    ('active', '=', True)
                ])
                incoterm_ids = relations.mapped('incoterm_id.id')
                domain = [('id', 'in', incoterm_ids)]
            record.filtered_incoterm = json.dumps(domain)

    @api.onchange('incoterm_id')
    def _compute_available_import_type(self):
        for record in self:
            domain = []
            if record.incoterm_id:
                # Buscar relaciones activas entre import_type y incoterms
                relations = self.env['incoterm.import.type'].search([
                    ('incoterm_id', '=', record.incoterm_id.id),
                    ('active', '=', True)
                ])
                import_type_ids = relations.mapped('import_type_id.id')
                domain = [('id', 'in', import_type_ids)]
            record.filtered_import_type = json.dumps(domain)

    @api.depends('import_type_id', 'incoterm_id')
    def _compute_incoterm_import_type(self):
        for record in self:
            record.incoterm_import_type_id = False
            if record.incoterm_id and record.import_type_id:
                get_record = self.env['incoterm.import.type'].search(
                    [('active', '=', True), ('incoterm_id', '=', record.incoterm_id.id),
                     ('import_type_id', '=', record.import_type_id.id)], limit=1)
                record.incoterm_import_type_id = get_record if get_record else False

    @api.constrains('incoterm_id', 'import_type_id')
    def _check_incoterm_relation(self):
        for record in self:
            if record.incoterm_id and record.import_type_id:
                exists = self.env['incoterm.import.type'].search_count([
                    ('incoterm_id', '=', record.incoterm_id.id),
                    ('import_type_id', '=', record.import_type_id.id),
                    ('active', '=', True)
                ])
                if not exists:
                    raise ValidationError(_("The selected Incoterm is not related to the type of import."))

    @api.onchange('country_origin_id')
    def _compute_filtered_hubs(self):
        for record in self:
            airport_domain = []
            port_domain = []
            record.port = False
            record.airport = False
            if record.country_origin_id:
                airport_domain = [
                    ('country_id', '=', record.country_origin_id.id),
                    ('hub_type', '=', 'Airport')
                ]
                port_domain = [
                    ('country_id', '=', record.country_origin_id.id),
                    ('hub_type', '=', 'Port')
                ]

            record.filtered_airport = json.dumps(airport_domain)
            record.filtered_port = json.dumps(port_domain)


class ImportationCostLine(models.Model):
    _name = 'importation.cost.line'
    _description = 'Additional Import Cost Line'

    importation_id = fields.Many2one('importation.process', string='Importation Process')
    product_id = fields.Many2one(
        'product.product',
        string='Service',
        domain=[('detailed_type', '=', 'service')],
        required=True
    )

    name = fields.Char(string='Description', compute='_compute_name', required=True)
    amount = fields.Monetary(string='Amount')
    distribution_type = fields.Selection([
        ('fixed', 'Fixed Amount per Order'),
        ('percentage', 'Percentage on Order'),
    ], string='Distribution Type', required=True)
    currency_id = fields.Many2one('res.currency', related='importation_id.currency_id', readonly=True)
    purchase_ids = fields.Many2many('purchase.order', string='Purchase Orders Applied',
                                    domain="[('id', 'in', parent.purchase_order_ids)]")

    # Validate if it applies to divep (this would need to be identified in the line
    # to know it is considered for differentiation in the billing reconciliation report)
    is_cost_special = fields.Boolean(string='Special Cost', default=False)

    @api.depends('product_id')
    def _compute_name(self):
        for record in self:
            record.name = record.product_id.display_name or ''


class ImportationStage(models.Model):
    _name = 'importation.stage'
    _description = 'Importation Process Stages'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
    description = fields.Char(string='Description')
    sequence = fields.Integer(required=True, default=1)
    fold = fields.Boolean('Folded in Kanban', default=False)
    is_final = fields.Boolean(string="Is Final Stage", default=False)
