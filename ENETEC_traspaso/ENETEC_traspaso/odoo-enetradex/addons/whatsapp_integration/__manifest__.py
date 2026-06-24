# -*- coding: utf-8 -*-
{
    "name": "WhatsApp Cloud API Integration",
    "version": "17.0.1.0.0",
    "summary": "Integración Odoo 17 ↔ WhatsApp Cloud API (Meta) — notificaciones automáticas, mensajería bidireccional y mini-CRM de WhatsApp.",
    "category": "Discuss",
    "author": "Pyxel Solutions",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "contacts",
        "sale",
        "account",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/whatsapp_data.xml",
        "views/whatsapp_template_mapping_views.xml",
        "views/whatsapp_message_log_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/whatsapp_menus.xml",
    ],
    "external_dependencies": {"python": ["requests"]},
    "application": True,
    "installable": True,
}
