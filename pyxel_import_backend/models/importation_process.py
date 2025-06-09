from odoo import models, fields, api
from odoo.exceptions import ValidationError

STATE_SELECTION = [
    ('new', 'New'),
    ('in_progress', 'Importation in Progress'),
    ('done', 'Completed'),
    ('cancelled', 'Cancelled'),
]


class ImportationProcess(models.Model):
    _name = 'importation.process'
    _description = 'Importation Process'

    name = fields.Char(string='Reference', required=True, default='New')
    stage_id = fields.Many2one('importation.stage', string='Process Stage',
                               default=lambda self: self.env['importation.stage'].search([], limit=1),
                               group_expand='_group_expand_stage_id',
                               ondelete='restrict')
    state = fields.Selection(
        STATE_SELECTION,
        string='State',
        default='new',
        tracking=True,
    )
    purchase_order_ids = fields.Many2many('purchase.order', string='Purchase Orders')
    cost_line_ids = fields.One2many('importation.cost.line', 'importation_id', string='Additional Costs')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_total_cost')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    sale_order_id = fields.Many2one('sale.order', string='Original Quotation')
    final_sale_order_id = fields.Many2one('sale.order', string='Final Generated Offer', readonly=True)

    provider_id = fields.Many2one('res.partner', string='Supplier', required=True)

    country_origin_id = fields.Many2one('res.country', string='Country of Origin', required=True)
    is_third_party_contract = fields.Boolean(string='Third-Party Contract')
    declaration = fields.Char(string='Goods Declaration')

    estimated_start_date = fields.Date(string='Estimated Start Date', required=True)
    estimated_end_date = fields.Date(string='Estimated End Date', required=True)
    departure_date = fields.Date(string='Departure Date from Origin')
    declaration_date = fields.Date(string='Goods Declaration Date')
    documentation_sent_date = fields.Date(string='Documentation Sent Date')

    port = fields.Char(string='Port')
    airport = fields.Char(string='Airport')

    purchase_condition = fields.Selection([
        ('FCL', 'FCL'),
        ('AWB', 'AWB'),
        ('LCL', 'LCL'),
        ('DAP', 'DAP'),
    ], string='Purchase Condition')

    purchase_condition_number = fields.Char(string='Number/Reference by Condition')

    # Attached documents
    origin_certificate = fields.Binary(string='Certificate of Origin')
    origin_certificate_filename = fields.Char()

    export_certificate = fields.Binary(string='Export Certificate')
    export_certificate_filename = fields.Char()

    quality_certificate = fields.Binary(string='Quality Certificate')
    quality_certificate_filename = fields.Char()

    commercial_invoice = fields.Binary(string='Commercial Invoice')
    commercial_invoice_filename = fields.Char()

    signed_offer = fields.Binary(string='Signed Offer')
    signed_offer_filename = fields.Char()

    documentation_file = fields.Binary(string='Documentation (FCL / AWB)')
    documentation_file_filename = fields.Char()

    packing_list = fields.Binary(string='Packing List')
    packing_list_filename = fields.Char()

    load_tracking_ids = fields.One2many(
        'importation.load',
        'importation_id',
        string="Cargo Model"
    )
    sale_order_count = fields.Integer(string='Sale Orders Count', compute='_compute_sale_order_count')

    stage_enter_date = fields.Datetime(string="Stage date")
    days_in_stage = fields.Integer(string="State days", compute='_compute_days_in_stage', store=True)

    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = self.env['sale.order'].search_count([
                '|',
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
        domain = ['|', ('id', '=', self.sale_order_id.id), ('id', '=', self.final_sale_order_id.id)]
        return {
            'name': 'Purchase Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {}
        }

    @api.depends('cost_line_ids.amount')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(line.amount for line in rec.cost_line_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            sequence = self.env['ir.sequence'].next_by_code('importation.process')
            vals['name'] = sequence or 'New'
        if 'stage_id' in vals:
            vals['stage_enter_date'] = fields.Datetime.now()

        return super().create(vals)

    def write(self, vals):
        if 'stage_id' in vals:
            vals['stage_enter_date'] = fields.Datetime.now()
        return super().write(vals)

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

        # Crear el sale.order con líneas acumuladas por producto
        sale_order = SaleOrder.create({
            'partner_id': self.sale_order_id.partner_id.id,
            'importation_process_id': self.id,
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

    name = fields.Char(string='Name', required=True)
    description = fields.Char(string='Description')
    sequence = fields.Integer(required=True, default=1)
    fold = fields.Boolean('Folded in Kanban', default=False)

