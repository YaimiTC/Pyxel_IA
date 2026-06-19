from odoo import api, fields, models


class MiModelo(models.Model):
    _name = 'mi_modulo.mi_modelo'
    _description = 'Mi Modelo de Ejemplo'

    name = fields.Char(string='Nombre', required=True)
    description = fields.Text(string='Descripción')
    active = fields.Boolean(string='Activo', default=True)
    date = fields.Date(string='Fecha', default=fields.Date.today)
