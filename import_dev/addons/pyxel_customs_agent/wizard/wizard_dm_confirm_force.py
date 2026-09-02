# -*- coding: utf-8 -*-
from odoo import models, fields, _


class WizardDmConfirmForce(models.TransientModel):
    _name = 'wizard.dm.confirm.force'
    _description = 'Confirmación DM con advertencias'

    message = fields.Text(readonly=True)
    document_ids = fields.Many2many('import.document')

    def action_confirm_force(self):
        self.ensure_one()
        resumen_costos = []
        for doc in self.document_ids.filtered(lambda d: d.document_key == 'dm'):
            doc.write({'dm_confirmed': True})
            resumen_costos.extend(doc._sync_dm_cost_lines())
        return {'type': 'ir.actions.client', 'tag': 'reload'}
