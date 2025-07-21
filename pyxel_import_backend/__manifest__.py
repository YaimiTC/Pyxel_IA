# -*- coding: utf-8 -*-
# Part of Pyxel Solutions. See LICENSE file for full copyright and licensing details.

{
    "name": "Import",
    "summary": """""",
    "version": "1.0",
    "author": "Pyxel Solutions",
    'contributors': [
        'Adnielys Abday Rojas Tadeo <adnielys.rojas89@gmail.com>',
        'Sandy Comas Becerra <sandytechboy00@gmail.com>',
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
        'contacts',
        'account',
    ],
    "data": [
        'data/crm_stage_data.xml',
        'data/res_partner_management_type_data.xml',
        'data/res_partner_category_data.xml',
        'data/res_partner_contact_type_data.xml',
        'data/importation_sequence.xml',
        'data/importation_stage_data.xml',
        "security/ir.model.access.csv",
        'data/email_payment_to_supplier_template.xml',
        "views/res_partner_view.xml",
        "views/product_template_views.xml",
        "views/crm_lead_views.xml",
        "views/view_load_fill_wizard.xml",
        "views/view_importation_progress.xml",
        "views/view_importation_load.xml",
        "views/view_importation_stage.xml",
        "views/wizard_evaluate_providers_view.xml",
        "views/view_purchase_provider_evaluation.xml",
        "views/sale_order_views.xml",
        "views/purchase_order_view.xml",
        "views/view_importation_cost_wizard.xml",
        "views/account_move_views.xml",
        "views/wizard_import_tcm_view.xml",
        "views/view_import_error_log.xml",
        "report/average_container_report_views.xml",
        "report/average_container_summary_report_views.xml",
        "views/importation_load_line_views.xml",
        "views/report_purchaseorder_no_code.xml",
        "views/report_saleorder_no_code.xml",



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
