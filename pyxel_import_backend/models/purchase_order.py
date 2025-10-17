from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)


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

    def _resequence_purchase_lines(self):
        for order in self:
            lines = order.order_line.sorted(lambda l: (l.sequence, l.id))
            # Para ignorar secciones/notas:
            # lines = lines.filtered(lambda l: not l.display_type)
            for idx, line in enumerate(lines, start=1):
                if line.line_number != idx:
                    line.sudo().write({'line_number': idx})


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    sale_order_line_id = fields.Many2one('sale.order.line', string='Source Sales Line')

    currency_id = fields.Many2one(
        related='order_id.currency_id',
        string='Currency',
        store=True,
        readonly=True
    )

    quantity_available = fields.Float(
        string='Available Quantity for Containers',
        compute='_compute_quantity_available',
        store=True
    )
    container_fix_ids = fields.One2many(
        comodel_name='importation.load.line',
        inverse_name='purchase_order_line_id',
        string='Container Lines'
    )

    @api.depends('product_uom_qty', 'container_fix_ids')
    def _compute_quantity_available(self):
        for record in self:
            _logger.info("Lineas de contendores")
            for line in record.container_fix_ids:
                _logger.info("line.order: %s", line)

            total_assigned = sum(record.container_fix_ids.mapped('quantity'))
            record.quantity_available = record.product_uom_qty - total_assigned

    line_number = fields.Integer(
        string="N°",
        compute="_compute_line_number",
        store=True,
        readonly=True,
        help="Número de línea autocalculado, inicia en 1 y se reenumera sin huecos."
    )

    @api.depends('order_id', 'sequence', 'display_type')
    def _compute_line_number(self):
        for order in self.mapped('order_id'):
            lines = order.order_line.sorted(lambda l: (l.sequence, l.id))
            # Para ignorar secciones/notas:
            # lines = lines.filtered(lambda l: not l.display_type)
            num = 1
            for line in lines:
                line.line_number = num
                num += 1

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        orders = records.mapped('order_id')
        orders._resequence_purchase_lines()
        return records

    def write(self, vals):
        orders_before = self.mapped('order_id')
        res = super().write(vals)
        orders_after = (self.mapped('order_id') | orders_before)
        orders_after._resequence_purchase_lines()
        return res

    def unlink(self):
        orders = self.mapped('order_id')
        res = super().unlink()
        orders._resequence_purchase_lines()
        return res
