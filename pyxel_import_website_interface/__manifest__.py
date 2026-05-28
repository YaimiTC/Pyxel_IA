# -*- coding: utf-8 -*-
{
    "name": "Pyxel Import Website Interface",
    "version": "17.0.1.1.0",
    "summary": """Custom web interface for Pyxel Solutions using Bootstrap 5 styling""",
    "author": "Pyxel Solutions",
    "contributors": "Leudis Estrada González <leudix.rafael@gmail.com>",
    "website": "https://pyxel-integracion.pyxelsolution.com/",
    "category": "Website",
    "depends": [
        "pyxel_import_website",
    ],
    "data": [
        "views/layout/base_layout.xml",
        "views/components/navbar.xml",
        "views/components/footer.xml",
        "views/components/portal_home.xml",
        "views/pages/new_home.xml",
        "views/pages/contactus.xml",
    ],
    "assets": {
        "web.assets_frontend": ["pyxel_import_website_interface/static/***/**/*"],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
