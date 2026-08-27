# -*- coding: utf-8 -*-
# Part of Pyxel Solutions. See LICENSE file for full copyright and licensing details.

{
    "name": "ENETRADEX backend",
    "summary": """""",
    "version": "1.3",
    "author": "Pyxel Solutions",
    'contributors': [
       'Sandy Comas Becerra <sandytechboy00@gmail.com>',
    ],
    "license": "LGPL-3",
    "website": "https://pyxelsolution.com",
    "description": """""",
    "depends": [
       'pyxel_import_backend',
    ],
    "data": [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/portal_rules.xml',
        'security/crm_lead_rules.xml',
        'views/menu_access.xml',
        'data/res_partner_management_type_data.xml',
        'data/en_currency_data.xml',
        'data/en_importation_stage_data.xml',
        'data/en_payment_method_data.xml',
        'data/en_import_products_data.xml',
        'views/crm_lead_wizard_views.xml',
        'views/crm_lead_views.xml',
        'views/en_backend_views.xml',
        'views/lead_document_views.xml',
        'views/import_document_views.xml',
        'views/purchase_order_views.xml',
        'report/en_cuban_partner_report.xml',
        'report/en_document_layout.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "pyxel_enetradex_backend/static/src/import_doc_photo/import_doc_photo.js",
            "pyxel_enetradex_backend/static/src/import_doc_photo/import_doc_photo.xml",
            "pyxel_enetradex_backend/static/src/wz_accred/wz_accred.js",
            "pyxel_enetradex_backend/static/src/wz_accred/wz_accred.xml",
            "pyxel_enetradex_backend/static/src/wz_accred/wz_accred.css",
            "pyxel_enetradex_backend/static/src/wz_accred/crm_new_override.js",
            "pyxel_enetradex_backend/static/src/oc_expediente/oc_expediente.css",
        ],
    },
    "installable": True,
    "auto_install": True,
}
