# -*- coding: utf-8 -*-
{
    'name': 'ENETRADEX Sync (local <-> nube)',
    'version': '17.0.1.0.0',
    'summary': 'Sincronización híbrida local/nube: outbox/inbox idempotente + UUID + pull desde local',
    'description': """
Fase 1 (PoC §13.1 de docs/arquitectura.md).
Gemelos idénticos: el comportamiento lo decide el rol del nodo (local | cloud).
- Identidad por UUID (sync.uuid.mixin).
- Outbox/inbox idempotente (sync.event).
- Endpoints solo-nube: /sync/push, /sync/pull, /sync/ack.
- Agente (cron) que SOLO corre en local: empuja catálogo y tira de pedidos.
Dominios: Catálogo (local->nube) y Pedido nuevo (nube->local, 'pendiente de adjudicar').
""",
    'category': 'Technical',
    'author': 'Pyxel Solutions',
    'license': 'LGPL-3',
    'depends': ['base', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/sync_peer_data.xml',
        'data/sync_cron.xml',
        'views/sync_views.xml',
    ],
    'application': True,
    'installable': True,
}
