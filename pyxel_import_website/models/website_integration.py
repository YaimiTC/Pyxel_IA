from odoo import models, fields


class Website(models.Model):
    _inherit = 'website'

    add_to_cart_action = fields.Char(string="Acción de añadir al carrito", default="default_action")
