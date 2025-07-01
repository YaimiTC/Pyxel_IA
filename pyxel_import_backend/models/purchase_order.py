from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sale_order_id = fields.Many2one('sale.order', string='Related Quotation')
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


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    sale_order_line_id = fields.Many2one('sale.order.line', string='Source Sales Line')

    quantity_available = fields.Float(
        string='Available Quantity for Containers',
        compute='_compute_quantity_available',
        store=False
    )
    container_fix_ids = fields.One2many(
        comodel_name='importation.load.line',
        inverse_name='purchase_order_line_id',
        string='Container Lines'
    )

    @api.depends('product_uom_qty', 'container_fix_ids')
    def _compute_quantity_available(self):
        for record in self:
            records = self.env['importation.load.line'].search([
                ('purchase_order_line_id', '=', record.id),
                ('cargo_id', 'in', record.container_fix_ids.ids)
            ])
            record.quantity_available = record.product_uom_qty - sum(
                r.quantity for r in records
            )
