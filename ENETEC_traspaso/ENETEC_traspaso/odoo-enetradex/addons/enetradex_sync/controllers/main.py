# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SyncController(http.Controller):
    """Endpoints SOLO del plano nube. El local los consume; la nube nunca llama al local."""

    def _check(self):
        peer = request.env['sync.peer'].sudo()._get()
        if peer.node_role != 'cloud':
            return 'endpoint disponible solo en rol cloud'
        token = request.httprequest.headers.get('X-Sync-Token', '')
        if not peer.shared_secret or token != peer.shared_secret:
            return 'token inválido'
        return None

    @http.route('/sync/push', type='json', auth='public', methods=['POST'], csrf=False)
    def push(self, events=None, **kw):
        """Recibe eventos local -> nube (catálogo). Idempotente."""
        err = self._check()
        if err:
            return {'error': err}
        applied, ierr = request.env['sync.event'].sudo().ingest(events or [])
        if ierr:
            return {'error': ierr}
        return {'applied': applied}

    @http.route('/sync/pull', type='json', auth='public', methods=['POST'], csrf=False)
    def pull(self, domains=None, limit=100, **kw):
        """Devuelve eventos nube -> local (pedidos) pendientes, por bloques."""
        err = self._check()
        if err:
            return {'error': err}
        events = request.env['sync.event'].sudo().serve_pull(domains or [], limit=limit)
        return {'events': events}

    @http.route('/sync/ack', type='json', auth='public', methods=['POST'], csrf=False)
    def ack(self, uuids=None, **kw):
        """El local confirma aplicados -> la nube los marca confirmados (base para purga)."""
        err = self._check()
        if err:
            return {'error': err}
        n = request.env['sync.event'].sudo().mark_acked(uuids or [])
        return {'acked': n}
