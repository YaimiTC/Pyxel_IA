# -*- coding: utf-8 -*-
from odoo import api, fields, models
from .sync_event import SCHEMA_VERSION


class SyncPeer(models.Model):
    """Configuración del enlace de sincronización (singleton).
    Mismo módulo en ambos planos; el rol decide el comportamiento."""
    _name = 'sync.peer'
    _description = 'Configuración del enlace de sincronización'

    name = fields.Char(default='Configuración de sync', required=True)
    node_role = fields.Selection([
        ('local', 'Local (maestro)'),
        ('cloud', 'Nube (borde)'),
    ], default='local', required=True,
        help="Local: fuente de verdad, inicia el sync. Nube: expone endpoints, no llama al local.")
    remote_endpoint = fields.Char(
        string='Endpoint de la nube',
        help="Solo en LOCAL. URL base de la nube, ej. http://178.104.186.167")
    shared_secret = fields.Char(string='Token compartido', help="Mismo valor en ambos planos.")
    schema_version = fields.Char(default=SCHEMA_VERSION, readonly=True)

    @api.model
    def _get(self):
        peer = self.search([], limit=1)
        if not peer:
            peer = self.create({'name': 'Configuración de sync'})
        return peer

    def action_sync_now(self):
        """Disparo manual del agente (útil cuando max_cron_threads=0 en local)."""
        self.env['sync.agent'].cron_run()
        return True
