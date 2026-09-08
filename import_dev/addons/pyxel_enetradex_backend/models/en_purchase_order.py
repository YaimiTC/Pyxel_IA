# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    cert_no_adeudo = fields.Binary(string="Cert. No Adeudo")
    cert_no_adeudo_filename = fields.Char()
    bl_awb_attachment = fields.Binary(string="BL / AWB")
    bl_awb_attachment_filename = fields.Char()
    en_customer_id = fields.Many2one(
        'res.partner', string="Cliente", related='importation_id.customer_id', readonly=True)

    # Cliente real de ESTA OC en operaciones multi-cliente (una OC por
    # cliente, ver en.import.request.client) -- en_customer_id de arriba es
    # legado, related al customer_id unico del proceso, y queda vacio/erroneo
    # cuando hay varios clientes reales; este es el que escribe el wizard.
    customer_id = fields.Many2one('res.partner', string="Cliente (real, por OC)")
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
