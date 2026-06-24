import requests
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    whatsapp_gateway_url = fields.Char(
        string='URL Gateway WhatsApp',
        config_parameter='whatsapp.gateway_url',
        groups='base.group_system',
    )
    whatsapp_gateway_api_key = fields.Char(
        string='API Key Gateway',
        config_parameter='whatsapp.gateway_api_key',
        groups='base.group_system',
    )

    def action_test_whatsapp(self):
        url = (self.whatsapp_gateway_url or '').rstrip('/')
        key = self.whatsapp_gateway_api_key or ''
        if not url:
            return self._wa_notif('warning', 'Sin URL', 'Configura primero la URL del gateway.')
        try:
            r = requests.get(f"{url}/health", headers={'x-api-key': key}, timeout=8)
            if r.ok:
                d = r.json()
                inst = d.get('instance') or d.get('status') or 'ok'
                return self._wa_notif('success', 'Gateway OK', f"Conexión exitosa — {inst}")
            return self._wa_notif('warning', 'Gateway error', f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            return self._wa_notif('danger', 'Sin conexión', str(e)[:200])

    def _wa_notif(self, notif_type, title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': notif_type, 'sticky': False},
        }
