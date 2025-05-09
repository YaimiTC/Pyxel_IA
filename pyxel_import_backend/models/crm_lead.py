from odoo import models, fields, api, _


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    sale_order_ids = fields.One2many('sale.order', 'opportunity_id', string='Presupuestos')
    sale_order_count = fields.Integer(compute='_compute_sale_order_count', string='Cantidad de Presupuestos')

    can_create_quotation = fields.Boolean(compute='_compute_can_create_quotation')

    @api.depends('stage_id')
    def _compute_can_create_quotation(self):
        for lead in self:
            lead.can_create_quotation = lead.stage_id.is_won

    def _compute_sale_order_count(self):
        for lead in self:
            lead.sale_order_count = len(lead.sale_order_ids)

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Presupuestos'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('opportunity_id', '=', self.id)],
            'context': {'default_opportunity_id': self.id, 'default_partner_id': self.partner_id.id},
        }

    def action_create_quotation(self):
        self.ensure_one()
        return {
            'name': 'Presupuesto',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_opportunity_id': self.id,
                'default_origin': self.name,
                # Agrega aquí otros campos default que desees
            }
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    opportunity_id = fields.Many2one('crm.lead', string="Oportunidad")
