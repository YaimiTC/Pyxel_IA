from odoo import models, fields, api
from odoo.exceptions import ValidationError

STATE_SELECTION = [
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
        default='draft',
        tracking=True,
    )
    purchase_order_ids = fields.Many2many('purchase.order', string='Purchase Orders')
    cost_line_ids = fields.One2many('importation.cost.line', 'importation_id', string='Additional Costs')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_total_cost')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    sale_order_id = fields.Many2one('sale.order', string='Original Quotation')
    final_sale_order_id = fields.Many2one('sale.order', string='Final Generated Offer', readonly=True)

    provider_id = fields.Many2one('res.partner', string='Supplier')

    country_origin_id = fields.Many2one('res.country', string='Country of Origin')
    is_third_party_contract = fields.Boolean(string='Third-Party Contract')
    declaration = fields.Text(string='Goods Declaration')

    estimated_start_date = fields.Date(string='Estimated Start Date')
    estimated_end_date = fields.Date(string='Estimated End Date')
    departure_date = fields.Date(string='Departure Date from Origin')
    declaration_date = fields.Date(string='Goods Declaration Date')
    documentation_sent_date = fields.Date(string='Documentation Sent Date')

    port = fields.Char(string='Port')
    airport = fields.Char(string='Airport')

    purchase_condition = fields.Selection([
        ('fcl', 'Maritime Import with Full Container Load (FCL)'),
        ('air', 'Air Import'),
        ('local', 'Local Purchase'),
        ('grouped', 'Grouped Cargo'),
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

    @api.depends('cost_line_ids.amount')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(line.amount for line in rec.cost_line_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            sequence = self.env['ir.sequence'].next_by_code('importation.process')
            vals['name'] = sequence or 'New'
        return super().create(vals)

    def action_start_progress(self):
        self.write({'state': 'in_progress'})

    def action_finish_progress(self):
        self.write({'state': 'done'})

    @api.model
    def _group_expand_stage_id(self, stages, domain, order):
        return self.env['importation.stage'].search([], order=order)


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