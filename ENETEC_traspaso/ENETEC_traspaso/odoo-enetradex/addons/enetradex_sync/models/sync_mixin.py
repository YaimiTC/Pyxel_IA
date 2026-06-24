# -*- coding: utf-8 -*-
import uuid as uuid_lib
from odoo import api, fields, models


class SyncUuidMixin(models.AbstractModel):
    """Identidad global por UUID (P7). Heredado por los modelos sincronizables.
    Las secuencias seriales de Odoo nunca se usan como identidad entre sitios."""
    _name = 'sync.uuid.mixin'
    _description = 'Identidad UUID para sincronización'

    sync_uuid = fields.Char(string='Sync UUID', index=True, copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sync_uuid'):
                vals['sync_uuid'] = str(uuid_lib.uuid4())
        return super().create(vals_list)
