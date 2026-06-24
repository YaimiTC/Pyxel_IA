# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError


class WizardGenerarExpediente(models.TransientModel):
    _name = 'wizard.generar.expediente'
    _description = 'Seleccionar tipo de entidad para generar expediente'

    lead_id = fields.Many2one('crm.lead', required=True)
    client_type = fields.Selection([
        ('Pymes', 'Pyme'),
        ('Estatal', 'Estatal'),
        ('CNA', 'CNA'),
        ('Sucursal Extranjera', 'Sucursal Extranjera'),
        ('Proveedor', 'Proveedor'),
    ], string="Tipo de entidad", required=True)

    def action_confirmar(self):
        self.ensure_one()
        lead = self.lead_id
        if lead.accreditation_document_ids:
            raise UserError(_("Este lead ya tiene un expediente generado."))
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', lead.id)])
        uploaded = {att.name.rsplit('.', 1)[0]: att.id for att in attachments}
        self.env['pyxel.lead.document'].sudo().build_expediente(lead, self.client_type, uploaded)
        return {'type': 'ir.actions.act_window_close'}
