# -*- coding: utf-8 -*-
# Part of Pyxel Solutions. See LICENSE file for full copyright and licensing details.

{
    "name": "ENETRADEX website",
    "summary": """""",
    "category": "Website",
    "version": "1.1",
    "author": "Pyxel Solutions",
    'contributors': [
        'Sandy Comas Becerra <sandytechboy00@gmail.com>',
    ],
    "license": "LGPL-3",
    "website": "https://pyxelsolution.com",
    "description": """""",
    "depends": [
        'pyxel_import_website',
        'pyxel_enetradex_backend',
    ],
    "data": [
        'views/business_registration.xml',
        'views/en_wizard.xml',
        'views/en_invited.xml',
        'views/portal_accreditation.xml',
        'views/portal_import.xml',
    ],
    "assets": {
        "web.assets_frontend": [
            "pyxel_enetradex_website/static/src/js/business_registration_override.js",
            "pyxel_enetradex_website/static/src/js/import_camera.js",
        ],
    },
    "installable": True,
    "auto_install": False,

}
