# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    importadora_name = fields.Char(
        string='Importadora permitida para importación',
        help='Solo se procesarán las filas cuya columna H coincida con este nombre.'
    )
