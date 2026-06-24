import logging
import requests
from odoo import models, api

_log = logging.getLogger(__name__)


class WhatsappService(models.AbstractModel):
    _name = 'whatsapp.service'
    _description = 'Servicio de envío WhatsApp'

    @api.model
    def _get_config(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        return {
            'url': get('whatsapp.gateway_url', 'http://host.docker.internal:3001'),
            'key': get('whatsapp.gateway_api_key', 'EnEtRaDex.WaGw.2026!'),
        }

    @api.model
    def send(self, phone, message):
        """Envía un mensaje WhatsApp. Devuelve (ok, info)."""
        if not phone:
            return False, 'Sin número de teléfono'
        number = ''.join(c for c in phone if c.isdigit() or c == '+')
        if not number:
            return False, 'Número inválido'
        cfg = self._get_config()
        try:
            r = requests.post(
                f"{cfg['url']}/send",
                json={'to': number, 'message': message},
                headers={'x-api-key': cfg['key']},
                timeout=15,
            )
            data = r.json()
            if data.get('ok'):
                _log.info('[WA] Enviado a %s', number)
                return True, data.get('messageId', '')
            err = data.get('error', r.text)
            _log.warning('[WA] Error enviando a %s: %s', number, err)
            return False, err
        except Exception as e:
            _log.exception('[WA] Excepción enviando a %s', number)
            return False, str(e)
