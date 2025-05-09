from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sale_order_id = fields.Many2one('sale.order', string='Presupuesto relacionado')
    evaluation_id = fields.Many2one('purchase.provider.evaluation', string='Evaluación')

    importation_id = fields.Many2one(
        'importation.process',
        string='Proceso de Importación',
        help='Proceso de importación al que pertenece esta orden de compra.')

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

        # Buscar las evaluaciones asociadas a las órdenes confirmadas
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

    sale_order_line_id = fields.Many2one('sale.order.line', string='Línea de venta origen')
