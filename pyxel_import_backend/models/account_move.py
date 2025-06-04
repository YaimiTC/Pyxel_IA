from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_type = fields.Selection([
        ('normal', 'Normal'),
        ('operative', 'Operative'),
    ], string="Invoice type", default='normal')

    importation_process_id = fields.Many2one(
        'importation.process',
        string="Import process"
    )

    container_ids = fields.One2many(
        related='importation_process_id.load_tracking_ids',
        string='Containers',
        readonly=True
    )

    container_names = fields.Char(
        string="Containers",
        compute='_compute_container_names',
        store=True
    )

    @api.depends('importation_process_id.load_tracking_ids.name')
    def _compute_container_names(self):
        for record in self:
            containers = record.importation_process_id.load_tracking_ids
            record.container_names = ', '.join(containers.mapped('name')) if containers else ''
