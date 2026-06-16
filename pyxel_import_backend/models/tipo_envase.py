# -*- coding: utf-8 -*-
from odoo import models, fields


class PyxelTipoEnvase(models.Model):
    _name = 'pyxel.tipo.envase'
    _description = 'Tipo de Envase/Embalaje'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(default=True)
