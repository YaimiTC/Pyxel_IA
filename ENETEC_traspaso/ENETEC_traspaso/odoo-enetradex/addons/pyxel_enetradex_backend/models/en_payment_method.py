# -*- coding: utf-8 -*-
from odoo import models, fields


class EnPaymentMethod(models.Model):
    """Forma de pago de la solicitud de importación. Lista administrable desde
    el backend (Configuración) para que el comercial/abogada la mantengan."""
    _name = 'en.payment.method'
    _description = "Forma de pago (solicitud de importación)"
    _order = 'sequence, name'

    name = fields.Char(string="Forma de pago", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Char(string="Descripción")
