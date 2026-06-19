{
    "name": "Ports and Airports",
    "summary": """""",
    "category": "Services",
    "version": "17.0.0.0.1",
    "author": "Pyxel Solutions",
    'contributors': [
        'Omar Crespo Carrazana <ing.omarcc92@gmail.com>',
    ],
    "license": "LGPL-3",
    "website": "https://pyxelsolution.com",
    "description": """""",
    "depends": ['contacts'],
    "data": [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
        'views/transport_hub_views.xml',
        'wizards/ports_import_wizard_views.xml',
        'views/menuitems.xml'
    ],
    "installable": True,
    "application": True,
    "auto_install": False,

}
