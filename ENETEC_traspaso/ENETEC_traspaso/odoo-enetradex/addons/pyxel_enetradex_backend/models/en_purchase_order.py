# -*- coding: utf-8 -*-
from odoo import models, api


class PurchaseOrderExpediente(models.Model):
    _inherit = 'purchase.order'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        to_build = records.filtered('importation_id')
        if to_build:
            self.env['pyxel.import.document'].build_oc_expediente(to_build)
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('importation_id'):
            self.env['pyxel.import.document'].build_oc_expediente(self)
        return res
