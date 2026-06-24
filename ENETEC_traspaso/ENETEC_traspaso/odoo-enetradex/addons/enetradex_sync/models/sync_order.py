# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SyncOrder(models.Model):
    """Pedido captado en la nube (ingesta nube -> local).
    Dueño = NUBE (captación), append-only; el LOCAL adjudica al recibir."""
    _name = 'enetradex.sync.order'
    _inherit = ['sync.uuid.mixin']
    _description = 'Pedido captado (sync nube -> local)'
    _order = 'create_date desc'

    partner_name = fields.Char(string='Cliente', required=True)
    product_summary = fields.Char(string='Productos solicitados')
    note = fields.Text(string='Notas')
    state = fields.Selection([
        ('pendiente', 'Pendiente de adjudicar'),
        ('adjudicado', 'Adjudicado'),
        ('rechazado', 'Rechazado'),
    ], default='pendiente', required=True, index=True)

    _sql_constraints = [
        ('sync_uuid_uniq', 'unique(sync_uuid)', 'El sync_uuid del pedido debe ser único.'),
    ]

    def _sync_role_is_cloud(self):
        return self.env['sync.peer'].sudo()._get().node_role == 'cloud'

    def _sync_serialize(self):
        self.ensure_one()
        return {
            'sync_uuid': self.sync_uuid,
            'partner_name': self.partner_name,
            'product_summary': self.product_summary,
            'note': self.note,
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Solo la NUBE produce eventos salientes de pedido (para que el local los tire).
        if not self.env.context.get('sync_no_outbox') and self._sync_role_is_cloud():
            for rec in records:
                self.env['sync.event'].enqueue_out('order', 'create', rec)
        return records
