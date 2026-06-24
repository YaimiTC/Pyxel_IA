# -*- coding: utf-8 -*-
from odoo import models, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

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
