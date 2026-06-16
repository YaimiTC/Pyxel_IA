from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    sale_order_ids = fields.One2many('sale.order', 'opportunity_id', string='Sales Orders')
    sale_order_count = fields.Integer(compute='_compute_sale_order_count', string='Number of Sales Orders')

    can_create_quotation = fields.Boolean(compute='_compute_can_create_quotation')

    # Expediente de acreditación
    accreditation_document_ids = fields.One2many(
        'pyxel.lead.document', 'lead_id', string='Documentos de acreditación')
    accreditation_doc_count = fields.Integer(
        compute='_compute_accreditation_counts', string='Documentos')
    accreditation_approved_count = fields.Integer(
        compute='_compute_accreditation_counts', string='Aprobados')
    accreditation_review_count = fields.Integer(
        compute='_compute_accreditation_counts', string='En revisión')
    accreditation_pending_count = fields.Integer(
        compute='_compute_accreditation_counts', string='Pendientes')

    @api.depends('accreditation_document_ids.portal_state',
                 'accreditation_document_ids.is_required')
    def _compute_accreditation_counts(self):
        for lead in self:
            docs = lead.accreditation_document_ids
            required = docs.filtered('is_required')
            lead.accreditation_doc_count = len(required)
            lead.accreditation_approved_count = len(
                required.filtered(lambda d: d.portal_state == 'approved'))
            lead.accreditation_review_count = len(
                required.filtered(lambda d: d.portal_state in ('in_review', 'validating')))
            lead.accreditation_pending_count = len(
                required.filtered(lambda d: d.portal_state in ('pending', 'rejected')))

    def write(self, vals):
        if 'stage_id' in vals:
            accreditation_stage = self.env['crm.stage'].search([('is_accreditation_stage', '=', True,)], limit=1)

            stage_id = self.env['crm.stage'].search([('id', '=', vals['stage_id'])], limit=1)
            if accreditation_stage and stage_id and stage_id.sequence >= accreditation_stage.sequence:
                if 'partner_id' in vals:
                    partner = self.env['res.partner'].search([('id', '=', vals['partner_id'])], limit=1)
                else:
                    partner = self.partner_id

                if partner and not partner.contact_type_id:
                    raise ValidationError(_("No es posible avanzar la solicitud de acreditación a una etapa de aprobación porque el contacto asociado no tiene definido el Tipo de Contacto."))
        return super(CrmLead, self).write(vals)

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
            'name': _('Sales Orders'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('opportunity_id', '=', self.id)],
            'context': {'default_opportunity_id': self.id, 'default_partner_id': self.partner_id.id},
        }

    def action_create_quotation(self):
        self.ensure_one()
        return {
            'name': 'Sales Order',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_opportunity_id': self.id,
                'default_origin': self.name,
                # Add other default fields here as needed
            }
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    opportunity_id = fields.Many2one('crm.lead', string="Opportunity")