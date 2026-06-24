# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import api, models

_logger = logging.getLogger(__name__)

PUBLISHED_OUT_DOMAINS = ['catalog']   # lo que el local publica hacia la nube
PULL_DOMAINS = ['order']              # lo que el local tira de la nube
TIMEOUT = 30
BATCH = 200


class SyncAgent(models.AbstractModel):
    """Agente de sincronización. SOLO trabaja en rol local (P5: el local inicia)."""
    _name = 'sync.agent'
    _description = 'Agente de sincronización (cron, lado local)'

    @api.model
    def cron_run(self):
        peer = self.env['sync.peer'].sudo()._get()
        if peer.node_role != 'local':
            _logger.info('sync.agent: rol=%s, nada que hacer (solo corre en local).', peer.node_role)
            return
        endpoint = (peer.remote_endpoint or '').rstrip('/')
        if not endpoint:
            _logger.warning('sync.agent: remote_endpoint sin configurar.')
            return
        secret = peer.shared_secret or ''
        self._push(endpoint, secret)
        self._pull(endpoint, secret)

    def _headers(self, secret):
        return {'X-Sync-Token': secret, 'Content-Type': 'application/json'}

    def _call(self, url, params, secret):
        body = {'jsonrpc': '2.0', 'method': 'call', 'params': params}
        r = requests.post(url, data=json.dumps(body), headers=self._headers(secret), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get('result') or {}

    @api.model
    def _push(self, endpoint, secret):
        Event = self.env['sync.event']
        evs = Event.search([
            ('direction', '=', 'out'),
            ('domain', 'in', PUBLISHED_OUT_DOMAINS),
            ('state', 'in', ['pending', 'failed']),
        ], order='id asc', limit=BATCH)
        if not evs:
            return
        try:
            res = self._call('%s/sync/push' % endpoint, {'events': [e._to_wire() for e in evs]}, secret)
            if res.get('error'):
                _logger.warning('push rechazado por la nube: %s', res['error'])
                return
            acked = set(res.get('applied', []))
            for e in evs:
                if e.uuid in acked:
                    e.state = 'sent'
                else:
                    e.attempts += 1
        except Exception as e:  # noqa: BLE001
            _logger.exception('Error en push')
            for ev in evs:
                ev.attempts += 1
                ev.last_error = str(e)

    @api.model
    def _pull(self, endpoint, secret):
        Event = self.env['sync.event']
        try:
            res = self._call('%s/sync/pull' % endpoint, {'domains': PULL_DOMAINS, 'limit': BATCH}, secret)
            events = res.get('events', [])
            if not events:
                return
            applied, error = Event.ingest(events)
            if error:
                _logger.warning('pull: %s -> se pausa el sync de este dominio.', error)
                return
            if applied:
                self._call('%s/sync/ack' % endpoint, {'uuids': applied}, secret)
        except Exception:  # noqa: BLE001
            _logger.exception('Error en pull')
