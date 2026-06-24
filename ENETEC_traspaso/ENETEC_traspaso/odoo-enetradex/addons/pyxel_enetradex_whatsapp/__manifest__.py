{
    'name': 'ENETRADEX WhatsApp',
    'version': '17.0.1.0.0',
    'summary': 'Notificaciones automáticas por WhatsApp',
    'depends': ['sale', 'pyxel_enetradex_backend'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'wizard/whatsapp_send_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
