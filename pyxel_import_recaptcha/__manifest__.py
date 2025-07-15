# -*- coding: utf-8 -*-
# Part of Pyxel Solutions. See LICENSE file for full copyright and licensing details.
{
    'name': 'Portal reCAPTCHA for Import',
    'version': '1.0',
    'author': 'Pyxel Solutions',
    'contributors': [
        'Adnielys Abday Rojas Tadeo <adnielys.rojas89@gmail.com>',
     ],
    'license': 'LGPL-3',
    'website': "https://pyxelsolution.com",
    'category': 'Website',
    'summary': 'Integración de reCAPTCHA en el portal',
    'description': """
        Este módulo integra Google reCAPTCHA en el portal de Odoo para mejorar la seguridad.
    """,
    'depends': ['base', 'web', 'auth_signup', 'google_recaptcha', 'pyxel_import_website'],
    'data': [
        # 'views/assets.xml',
        'data/recaptcha_assets.xml',
        'views/login_recaptcha_template.xml',
        'views/auth_signup_template.xml'
        # 'views/import_registration_recaptcha.xml',
        # 'views/res_config_settings_view.xml',

    ],
    'assets': {
        'web.assets_frontend': [
             'pyxel_import_recaptcha/static/src/js/recaptcha_loader.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}


