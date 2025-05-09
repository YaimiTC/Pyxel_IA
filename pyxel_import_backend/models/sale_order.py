from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    purchase_order_count = fields.Integer(string="Órdenes de Compra", compute='_compute_purchase_order_count')

    purchase_provider_evaluation_ids = fields.One2many('purchase.provider.evaluation', 'sale_order_id')

    purchase_evaluation_count = fields.Integer(string="Evaluaciones", compute='_compute_purchase_evaluation_count')

    evaluation_apply_id = fields.Many2one('purchase.provider.evaluation', string='Evaluación Aplicada')

    has_applicable_evaluations = fields.Boolean(
        string='Tiene evaluaciones aplicables',
        compute='_compute_has_applicable_evaluations'
    )

    order_type = fields.Selection([
        ('ordinary', 'Ordinario'),
        ('evaluation_initial', 'Evaluación Inicial'),
        ('evaluation_final', 'Evaluación Final'),
        ('importation_process', 'Proceso de Importación')
    ], string='Tipo de Orden', default='ordinary')

    importation_process_id = fields.Many2one(
        'importation.process',
        string='Proceso de Importación',
        readonly=True,
        help='Proceso de importación generado desde esta evaluación.'
    )

    @api.depends('purchase_provider_evaluation_ids.has_evaluations_to_apply')
    def _compute_has_applicable_evaluations(self):
        for order in self:
            order.has_applicable_evaluations = any(
                ev.has_evaluations_to_apply for ev in order.purchase_provider_evaluation_ids
            )

    def action_initial_process_importation(self):
        cost_lines = [(0, 0, {
            'product_id': line.product_id.id,
            'name': line.name,
            'amount': line.amount,
            'distribution_type': line.distribution_type,
            'is_cost_special': line.is_cost_special,
        }) for line in self.evaluation_apply_id.cost_line_temp_ids]

        provider = self.evaluation_apply_id.purchase_order_ids[0].partner_id
        # Crear el proceso de importación desde la evaluación
        importation = self.env['importation.process'].create({
            'provider_id': provider.id,
            'purchase_order_ids': [(6, 0, self.evaluation_apply_id.purchase_order_ids.ids)],
            'sale_order_id': self.evaluation_apply_id.sale_order_id.id,
            'final_sale_order_id': self.id,
            'cost_line_ids': cost_lines,
            'country_origin_id': provider.country_id.id,
            'state': 'in_progress',
            'stage_id': self.env['importation.stage'].search([], limit=1).id
        })

        self.importation_process_id = importation.id
        self.order_type = 'importation_process'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'importation.process',
            'view_mode': 'form',
            'res_id': importation.id,
            'target': 'current',
        }

    def _compute_purchase_order_count(self):
        for order in self:
            order.purchase_order_count = self.env['purchase.order'].search_count([('sale_order_id', '=', order.id)])

    def _compute_purchase_evaluation_count(self):
        for order in self:
            order.purchase_evaluation_count = self.env['purchase.provider.evaluation'].search_count([('sale_order_id', '=', order.id)])

    def action_view_related_purchase_orders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Órdenes de Compra Relacionadas',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }

