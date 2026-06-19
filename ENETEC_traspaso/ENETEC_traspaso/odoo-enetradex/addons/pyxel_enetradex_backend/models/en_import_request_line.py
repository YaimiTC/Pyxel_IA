# -*- coding: utf-8 -*-
from odoo import models, fields


class EnImportRequestLine(models.Model):
    """Línea de producto de la solicitud de importación (multiproducto)."""
    _name = 'en.import.request.line'
    _description = "Línea de solicitud de importación"
    _order = 'sequence, id'

    process_id = fields.Many2one(
        'importation.process', string="Solicitud", required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string="Producto")
    product_name = fields.Char(string="Producto (texto)")
    qty = fields.Float(string="Cantidad")
    packaging = fields.Selection(
        [('isotanque', 'Isotanque'), ('isomodulo', 'Isomódulo')],
        string="Tipo de envase")

    def name_get(self):
        res = []
        for rec in self:
            label = rec.product_id.display_name or rec.product_name or '—'
            res.append((rec.id, '%s · %s' % (label, rec.qty or 0)))
        return res
