# -*- coding: utf-8 -*-
# Part of Pyxel Solutions. See LICENSE file for full copyright and licensing details.

{
    "name": "Import",
    "summary": """""",
    "version": "1.0",
    "author": "Pyxel Solutions",
    'contributors': [
        'Adnielys Abday Rojas Tadeo <adnielys.rojas89@gmail.com>',
    ],
    "license": "LGPL-3",
    "website": "https://pyxelsolution.com",
    "description": """ Backend Import Process""",
    "depends": [
        'base',
        'crm',
        'sale',
        'sale_management',
        'purchase',
        'stock',
        'contacts'

    ],
    "data": [
        'data/importation_sequence.xml',
        'data/importation_stage_data.xml',
        "security/ir.model.access.csv",
        "views/res_partner_view.xml",
        "views/product_template_views.xml",
        "views/crm_lead_views.xml",
        "views/view_importation_progress.xml",
        "views/view_importation_load.xml",
        "views/view_importation_stage.xml",
        "views/wizard_evaluate_providers_view.xml",
        "views/view_purchase_provider_evaluation.xml",
        "views/sale_order_views.xml",
        "views/purchase_order_view.xml",
        "views/view_importation_cost_wizard.xml",




     ],
    'assets': {
        'web.assets_backend': [
            'pyxel_import_backend/static/src/js/list_view_button.js',
            'pyxel_import_backend/static/src/xml/list_view_button.xml',
        ],
    },
    "installable": True,
    "auto_install": False,

}
