# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ExportDepositWizard(models.TransientModel):
    _name = 'export.deposit.wizard'
    _description = 'Exportar para Depósito'

    destination_ids = fields.Many2many(
        'importation.destination', string='Destino(s)',
        help="Vacío = todos los destinos.")
    load_ids = fields.Many2many(
        'importation.load', string='Contenedores a exportar (vista previa)',
        compute='_compute_load_ids', store=False)
    load_count = fields.Integer(compute='_compute_load_ids')

    @api.depends('destination_ids')
    def _compute_load_ids(self):
        for wizard in self:
            domain = [('arrival_date', '!=', False), ('state', 'not in', ['to_return', 'returned'])]
            if wizard.destination_ids:
                domain.append(('destination_id', 'in', wizard.destination_ids.ids))
            recs = self.env['importation.load'].search(domain)
            wizard.load_ids = recs
            wizard.load_count = len(recs)

    def action_export(self):
        return self.load_ids.action_export_deposit_package()
