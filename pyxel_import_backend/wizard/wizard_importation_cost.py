from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class ImportationCostWizard(models.TransientModel):
    _name = 'importation.cost.wizard'
    _description = 'Wizard to add additional costs from evaluation'

    evaluation_id = fields.Many2one('purchase.provider.evaluation', required=True)
    cost_line_ids = fields.One2many('importation.cost.wizard.line', 'wizard_id', string='Costs')

    def action_confirm(self):
        # Guarda temporalmente los costos en la evaluación
        # Crear líneas de costo desde el wizard
        cost_lines = [(0, 0, {
            'product_id': line.product_id.id,
            'name': line.name,
            'amount': line.amount,
            'distribution_type': line.distribution_type,
            'is_cost_special': line.is_cost_special,
        }) for line in self.cost_line_ids]

        provider = self.evaluation_id.purchase_order_ids[0].partner_id
        # Crear el proceso de importación desde la evaluación
        importation = self.env['importation.process'].create({
            'provider_id': provider.id,
            'purchase_order_ids': [(6, 0, self.evaluation_id.purchase_order_ids.ids)],
            'sale_order_id': self.evaluation_id.sale_order_id.id,
            'cost_line_ids': cost_lines,
            'country_origin_id': provider.country_id.id,
            'state': 'draft',
            'stage_id': self.env['importation.stage'].search([], limit=1).id
        })

        # Opcional: marcar evaluación como usada o en otro estado
        self.evaluation_id.importation_process_id = importation.id
        self.evaluation_id.cost_line_temp_ids = cost_lines

        return {'type': 'ir.actions.act_window_close'}


class ImportationCostWizardLine(models.TransientModel):
    _name = 'importation.cost.wizard.line'
    _description = 'Additional Cost Line (wizard)'

    wizard_id = fields.Many2one('importation.cost.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product',
        string='Servicio',
        domain=[('detailed_type', '=', 'service')],
        required=True
    )
    name = fields.Char(string='Descripción',compute='_compute_name', required=True)
    amount = fields.Monetary(string='Monto', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id, readonly=True)
    distribution_type = fields.Selection([
        ('fixed', 'Monto Fijo'),
        ('percentage', 'Porcentaje'),
    ], required=True)
    is_cost_special = fields.Boolean(string='Special cost')

    @api.depends('product_id')
    def _compute_name(self):
        for record in self:
            record.name = record.product_id.display_name or ''


