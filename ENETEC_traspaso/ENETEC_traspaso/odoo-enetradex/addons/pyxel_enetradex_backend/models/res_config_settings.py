# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    en_import_margin_percent = fields.Float(
        string="Margen de importación (%)", default=0.3,
        help="Comisión/margen de ENETRADEX aplicado a la oferta de venta al cliente.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    en_import_margin_percent = fields.Float(
        related='company_id.en_import_margin_percent', readonly=False,
        string="Margen de importación (%)")
