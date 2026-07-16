# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Cliente de esta OC en operaciones multi-cliente (una OC por cliente,
    # ver en.import.request.client). Lo lee pyxel.import.document._compute_customer_id
    # y el wizard de acreditación al crear la OC en borrador por cliente.
    customer_id = fields.Many2one('res.partner', string="Cliente")
    cert_no_adeudo = fields.Binary(string="Certificado de no adeudo")
    cert_no_adeudo_filename = fields.Char(string="Nombre de archivo")
    bl_number = fields.Char(string="No. BL / AWB")

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        with_imp = orders.filtered('importation_id')
        if with_imp:
            self.env['pyxel.import.document'].build_oc_expediente(with_imp)
        return orders

    def write(self, vals):
        res = super().write(vals)
        if vals.get('importation_id'):
            self.env['pyxel.import.document'].build_oc_expediente(self.filtered('importation_id'))
        return res
