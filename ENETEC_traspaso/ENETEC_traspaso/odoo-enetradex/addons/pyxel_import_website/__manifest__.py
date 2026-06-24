# -*- coding: utf-8 -*-
# Part of Pyxel Solutions. See LICENSE file for full copyright and licensing details.

{
    "name": "Website customization for Imports",
    "summary": """""",
    "category": "Website",
    "version": "2.0",
    "author": "Pyxel Solutions",
    'contributors': [
        'Leonardo García Barreras <leonardogbarreras99@gmail.com>',
        'Sandy Comas Becerra <sandytechboy00@gmail.com>',
    ],
    "license": "LGPL-3",
    "website": "https://pyxelsolution.com",
    "description": """""",
    "depends": [
        'base',
        'web',
        'website',
        'website_sale',
        'website_crm',
        'base_address_extended',
        'sale_management',
        'purchase',
        'project',
        'pyxel_import_backend',
    ],
    "data": [
        'data/ir_model_data.xml',
        'views/business_registration.xml',
        'views/import_registration.xml',
        'views/product_templates_views.xml',
        'views/nomenclator.xml',
        'views/imports_frontend_views.xml',
        'views/update_files_template.xml',
        'views/res_config_setting_views.xml',
        'views/portal_template_view.xml',
        'views/portal_compras_view.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # Select2 LOCAL (antes CDN externo). NO cargamos un segundo jQuery:
            # Odoo 17 ya incluye jQuery en assets_frontend (con el plugin zoomOdoo);
            # Select2 se engancha a ese jQuery. Cargar otro jQuery rompía zoomOdoo.
            'pyxel_import_website/static/lib/select2/select2.min.css',
            'pyxel_import_website/static/lib/select2/select2.min.js',
            'pyxel_import_website/static/src/components/**/*.js',
            'pyxel_import_website/static/src/components/**/*.xml',
            # 'website_sale/static/src/**/*',
            'pyxel_import_website/static/src/js/business_registration.js',
            'pyxel_import_website/static/src/js/import_registration.js',
            'pyxel_import_website/static/src/js/nomenclator_add.js',
            'pyxel_import_website/static/src/js/select2_init_products.js',
            # 'pyxel_import_website/static/src/css/business_register.css',
            'pyxel_import_website/static/src/css/badge_classes.css',
            'pyxel_import_website/static/src/css/nomenclator.css',
            'pyxel_import_website/static/src/css/imports_form.css',

            # 'pyxel_import_website/static/src/scss/provider.scss',
        ]
    },
    "installable": True,
    "auto_install": False,

}
