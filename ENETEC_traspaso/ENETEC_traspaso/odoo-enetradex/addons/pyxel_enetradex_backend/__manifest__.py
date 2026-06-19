# -*- coding: utf-8 -*-
# Part of Pyxel Solutions. See LICENSE file for full copyright and licensing details.

{
    "name": "ENETRADEX backend",
    "summary": """""",
    "version": "1.1",
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
        'security/ir.model.access.csv',
        'security/portal_rules.xml',
        'data/res_partner_management_type_data.xml',
        'data/en_currency_data.xml',
        'data/en_importation_stage_data.xml',
        'data/en_payment_method_data.xml',
        'data/en_import_products_data.xml',
        'views/crm_lead_views.xml',
        'views/en_backend_views.xml',
        'views/lead_document_views.xml',
        'views/import_document_views.xml',
        'views/apoderado_views.xml',
        'report/en_cuban_partner_report.xml',
        'report/en_document_layout.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "pyxel_enetradex_backend/static/src/xml/camera_field.xml",
            "pyxel_enetradex_backend/static/src/js/camera_field.js",
        ],
    },
    "installable": True,
    "auto_install": True,
}
