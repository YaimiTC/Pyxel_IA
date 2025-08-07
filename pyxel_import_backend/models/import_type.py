from odoo import models, fields


class ImportType(models.Model):
    _name = 'import.type'
    _description = 'Import Type'

    name = fields.Char(string='Name')
