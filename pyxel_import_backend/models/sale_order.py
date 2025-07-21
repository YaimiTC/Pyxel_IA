import datetime
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    purchase_order_count = fields.Integer(string="Purchase Orders", compute='_compute_purchase_order_count', store=True)
    provider_names = fields.Char(string="Providers", compute="_compute_purchase_order_count", store=True)
    invoice_names = fields.Char(string='Invoices', compute='_compute_invoice_names')

    purchase_provider_evaluation_ids = fields.One2many('purchase.provider.evaluation', 'sale_order_id')

    purchase_evaluation_count = fields.Integer(string="Evaluations", compute='_compute_purchase_evaluation_count')

    evaluation_apply_id = fields.Many2one('purchase.provider.evaluation', string='Applied Evaluation')

    has_applicable_evaluations = fields.Boolean(
        string='Has Applicable Evaluations',
        compute='_compute_has_applicable_evaluations'
    )

    order_type = fields.Selection([
        ('ordinary', 'Ordinary'),
        ('evaluation_initial', 'Initial Evaluation'),
        ('evaluation_final', 'Final Evaluation'),
        ('importation_process', 'Importation Process')
    ], string='Order Type', default='ordinary')

    importation_process_id = fields.Many2one(
        'importation.process',
        string='Importation Process',
        readonly=True,
        help='Importation process generated from this evaluation.'
    )
    is_third_party_contract = fields.Boolean(
        string='Third-Party Contract',
        related='importation_process_id.is_third_party_contract',
        store=True,
        readonly=False  # Solo si quieres permitir editar desde el sale.order
    )

    @api.depends('purchase_provider_evaluation_ids.has_evaluations_to_apply')
    def _compute_has_applicable_evaluations(self):
        for order in self:
            order.has_applicable_evaluations = any(
                ev.has_evaluations_to_apply for ev in order.purchase_provider_evaluation_ids
            )

    def action_initial_process_importation(self):
        provider = self.evaluation_apply_id.purchase_order_ids[0].partner_id

        # 🔒 Validación controlada del país de origen
        if not provider.country_id:
            raise UserError("El proveedor seleccionado no tiene definido un país de origen.\nPor favor, complete este"
                            " dato antes de iniciar el proceso de importación.")

        cost_lines = [(0, 0, {
            'product_id': line.product_id.id,
            'name': line.name,
            'amount': line.amount,
            'purchase_ids': [(6, 0, self.evaluation_apply_id.purchase_order_ids.ids)],
            'distribution_type': line.distribution_type,
            'is_cost_special': line.is_cost_special,
        }) for line in self.evaluation_apply_id.cost_line_temp_ids]


        # Create the importation process from the evaluation
        importation = self.env['importation.process'].create({
            'provider_id': provider.id,
            'purchase_order_ids': [(6, 0, self.evaluation_apply_id.purchase_order_ids.ids)],
            'sale_order_id': self.id,
            'customer_id': self.partner_id.id,
            'estimated_start_date': datetime.datetime.now(),
            'estimated_end_date': datetime.datetime.now(),
            # 'final_sale_order_id': self.id, aqui cambie la logica para poder usar esta como resultado del proceso de terminacion de la importacion.
            'cost_line_ids': cost_lines,
            'country_origin_id': provider.country_id.id,
            'state': 'in_progress',
            'stage_id': self.env['importation.stage'].search([], limit=1).id
        })

        self.importation_process_id = importation.id
        # self.order_type = 'importation_process'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'importation.process',
            'view_mode': 'form',
            'res_id': importation.id,
            'target': 'current',
        }

    def _compute_purchase_order_count(self):
        for order in self:
            providers = self.env['purchase.order'].search([('sale_order_id', '=', order.id)])
            order.purchase_order_count = len(providers)
            providers_names = providers.mapped('partner_id.name')
            order.provider_names = ', '.join(sorted(set(providers_names)))

    def _compute_purchase_evaluation_count(self):
        for order in self:
            order.purchase_evaluation_count = self.env['purchase.provider.evaluation'].search_count([('sale_order_id', '=', order.id)])

    @api.depends('invoice_ids.name')
    def _compute_invoice_names(self):
        for order in self:
            invoice_names = order.invoice_ids.mapped('name')
            order.invoice_names = ', '.join(invoice_names)

    def action_view_related_purchase_orders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        if self.importation_process_id:
            invoice_vals['importation_process_id'] = self.importation_process_id.id
        return invoice_vals


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    clean_description = fields.Char(
        string='Clean Description',
        compute='_compute_clean_description',
        store=False
    )

    @api.depends('name')
    def _compute_clean_description(self):
        for line in self:
            if line.name:
                line.clean_description = re.sub(r'^\[[^\]]+\]\s*', '', line.name)
            else:
                line.clean_description = ''
