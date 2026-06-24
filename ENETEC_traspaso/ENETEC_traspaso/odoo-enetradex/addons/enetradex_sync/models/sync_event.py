# -*- coding: utf-8 -*-
import json
import logging
import uuid as uuid_lib
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Versión del contrato de evento. Si no coincide entre planos -> se pausa el sync (P8).
SCHEMA_VERSION = '1.0'

# Campos del catálogo que se publican local -> nube.
CATALOG_FIELDS = ['name', 'default_code', 'list_price']


class SyncEvent(models.Model):
    """Outbox + inbox unificado, idempotente por `uuid` (§6.1)."""
    _name = 'sync.event'
    _description = 'Evento de sincronización (outbox/inbox)'
    _order = 'id asc'

    uuid = fields.Char(string='Idempotency UUID', required=True, index=True, copy=False,
                       default=lambda self: str(uuid_lib.uuid4()))
    schema_version = fields.Char(default=SCHEMA_VERSION, required=True)
    direction = fields.Selection([('out', 'Saliente'), ('in', 'Entrante')],
                                 required=True, index=True)
    domain = fields.Selection([('catalog', 'Catálogo'), ('order', 'Pedido')],
                              required=True, index=True)
    operation = fields.Selection([('create', 'create'), ('write', 'write'), ('unlink', 'unlink')],
                                 required=True, default='write')
    res_model = fields.Char(string='Modelo')
    record_uuid = fields.Char(string='UUID del registro', index=True)
    payload = fields.Text()
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('acked', 'Confirmado'),
        ('applied', 'Aplicado'),
        ('failed', 'Error'),
    ], default='pending', required=True, index=True)
    attempts = fields.Integer(default=0)
    last_error = fields.Text()

    _sql_constraints = [
        ('uuid_uniq', 'unique(uuid)', 'El UUID del evento debe ser único (idempotencia).'),
    ]

    # ───────────────────── OUTBOX (productor) ─────────────────────
    @api.model
    def enqueue_out(self, domain, operation, record):
        """Encola un evento saliente con el snapshot del registro."""
        return self.create({
            'direction': 'out',
            'domain': domain,
            'operation': operation,
            'res_model': record._name,
            'record_uuid': record.sync_uuid,
            'payload': json.dumps(self._serialize(domain, record)),
            'state': 'pending',
        })

    @api.model
    def _serialize(self, domain, record):
        if domain == 'catalog':
            data = {f: record[f] for f in CATALOG_FIELDS}
            data['sync_uuid'] = record.sync_uuid
            return data
        if domain == 'order':
            return record._sync_serialize()
        return {}

    def _to_wire(self):
        """Representación de transporte (lo que viaja por el enlace)."""
        self.ensure_one()
        return {
            'uuid': self.uuid,
            'schema_version': self.schema_version,
            'domain': self.domain,
            'operation': self.operation,
            'res_model': self.res_model,
            'record_uuid': self.record_uuid,
            'payload': json.loads(self.payload or '{}'),
        }

    # ───────────────────── INBOX (consumidor) ─────────────────────
    @api.model
    def ingest(self, events):
        """Aplica eventos entrantes de forma idempotente.
        Devuelve (applied_uuids, error). error != None -> pausar."""
        applied = []
        for ev in (events or []):
            if ev.get('schema_version') != SCHEMA_VERSION:
                return applied, 'schema_version_mismatch'
            if self.search_count([('uuid', '=', ev['uuid'])]):
                applied.append(ev['uuid'])  # ya conocido -> idempotente
                continue
            rec = self.create({
                'uuid': ev['uuid'],
                'schema_version': ev['schema_version'],
                'direction': 'in',
                'domain': ev['domain'],
                'operation': ev.get('operation', 'write'),
                'res_model': ev.get('res_model'),
                'record_uuid': ev.get('record_uuid'),
                'payload': json.dumps(ev.get('payload', {})),
                'state': 'pending',
            })
            try:
                self._apply(ev['domain'], ev.get('operation', 'write'), ev.get('payload', {}))
                rec.state = 'applied'
                applied.append(ev['uuid'])
            except Exception as e:  # noqa: BLE001
                rec.state = 'failed'
                rec.last_error = str(e)
                _logger.exception('Fallo aplicando evento %s', ev.get('uuid'))
        return applied, None

    @api.model
    def _apply(self, domain, operation, payload):
        if domain == 'catalog':
            self._apply_catalog(operation, payload)
        elif domain == 'order':
            self._apply_order(operation, payload)

    @api.model
    def _apply_catalog(self, operation, payload):
        """Upsert por sync_uuid en product.template (la nube es solo lectura: local gana)."""
        Product = self.env['product.template'].sudo().with_context(sync_no_outbox=True)
        su = payload.get('sync_uuid')
        rec = Product.search([('sync_uuid', '=', su)], limit=1)
        if operation == 'unlink':
            if rec:
                rec.unlink()
            return
        vals = {k: payload.get(k) for k in CATALOG_FIELDS}
        if rec:
            rec.write(vals)
        else:
            vals['sync_uuid'] = su
            Product.create(vals)

    @api.model
    def _apply_order(self, operation, payload):
        """Append-only: crea el pedido captado en local en 'pendiente de adjudicar'."""
        Order = self.env['enetradex.sync.order'].sudo().with_context(sync_no_outbox=True)
        su = payload.get('sync_uuid')
        if Order.search_count([('sync_uuid', '=', su)]):
            return  # ya existe
        Order.create({
            'sync_uuid': su,
            'partner_name': payload.get('partner_name'),
            'product_summary': payload.get('product_summary'),
            'note': payload.get('note'),
            'state': 'pendiente',
        })

    # ───────────────────── Servicio de PULL (lado nube) ─────────────────────
    @api.model
    def serve_pull(self, domains, limit=100):
        evs = self.search([
            ('direction', '=', 'out'),
            ('domain', 'in', domains),
            ('state', 'in', ['pending', 'sent']),
        ], order='id asc', limit=limit)
        return [e._to_wire() for e in evs]

    @api.model
    def mark_acked(self, uuids):
        evs = self.search([('uuid', 'in', uuids or []), ('direction', '=', 'out')])
        evs.write({'state': 'acked'})
        return len(evs)
