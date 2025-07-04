# -*- coding: utf-8 -*-
# Part of Pyxel Solutions. See LICENSE file for full copyright and licensing details.

{
    "name": "TCM Data Automation",
    "summary": """""",
    "version": "17.0.0.0.2",
    "author": "Pyxel Solutions",
    'contributors': [
        'Omar Crespo Carrazana <ing.omarcc92@gmail.com>',
    ],
    "license": "LGPL-3",
    "website": "https://pyxelsolution.com",
    "description": """ TCM Email automation and all email notifications""",
    "depends": [
        'base', 
        'mail', 
        # 'studio_customization', 
        # 'pyxel_fruxelimport'
        ],
    "data": [
        'security/ir.model.access.csv',
        'data/scheduled_task_cron.xml',
        'views/res_config_setting_views.xml',
    ],
    "installable": True,
    "auto_install": False,

}
