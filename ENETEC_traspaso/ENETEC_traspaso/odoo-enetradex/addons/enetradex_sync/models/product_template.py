# -*- coding: utf-8 -*-
from odoo import api, models

CATALOG_TRIGGER_FIELDS = {'name', 'default_code', 'list_price'}


class ProductTemplate(models.Model):
    """Catálogo: dueño = LOCAL. Solo el local publica cambios hacia la nube."""
    _name = 'product.template'
    _inherit = ['product.template', 'sync.uuid.mixin']

    def _sync_role_is_local(self):
        return self.env['sync.peer'].sudo()._get().node_role == 'local'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('sync_no_outbox') and self._sync_role_is_local():
            for rec in records:
                self.env['sync.event'].enqueue_out('catalog', 'create', rec)
        return records

    def write(self, vals):
        res = super().write(vals)
        if (not self.env.context.get('sync_no_outbox')
                and CATALOG_TRIGGER_FIELDS & set(vals.keys())
                and self._sync_role_is_local()):
            for rec in self:
                self.env['sync.event'].enqueue_out('catalog', 'write', rec)
        return res
