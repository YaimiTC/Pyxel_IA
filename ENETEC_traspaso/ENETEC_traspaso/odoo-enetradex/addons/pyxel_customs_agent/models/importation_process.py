# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ImportationProcess(models.Model):
    _inherit = 'importation.process'

    # Override del dominio de en_customs_agent_id para restringir al grupo correcto
    en_customs_agent_id = fields.Many2one(
        domain=lambda self: [('groups_id', 'in', self.env.ref('pyxel_customs_agent.group_customs_agent').id)])

    # Override del compute para incluir dm_confirmed (definido en import_document.py)
    @api.depends('en_import_dm_doc_ids.dm_confirmed')
    def _compute_en_customs_dm_done(self):
        for rec in self:
            dms = rec.en_import_dm_doc_ids
            rec.en_customs_dm_done = bool(dms) and all(d.dm_confirmed for d in dms)
