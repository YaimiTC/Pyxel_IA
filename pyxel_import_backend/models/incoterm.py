from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class Incoterm(models.Model):
    _name = 'incoterm'
    _description = 'Incoterm'

    name = fields.Char(string='Name')
