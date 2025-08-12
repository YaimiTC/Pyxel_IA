from odoo import models, fields, api, _


class IncotermImportType(models.Model):
    _name = 'incoterm.import.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Incoterm - Import Type Relation'

    incoterm_id = fields.Many2one('account.incoterms', string='Incoterm', required=True, ondelete='cascade')
    import_type_id = fields.Many2one('import.type', string='Import Type', required=True, ondelete='cascade')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('unique_combination', 'unique(incoterm_id, import_type_id)', 'This combination already exists.')
    ]
