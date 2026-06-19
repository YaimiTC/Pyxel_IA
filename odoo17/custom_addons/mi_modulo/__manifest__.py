{
    'name': 'Mi Módulo',
    'version': '17.0.1.0.0',
    'category': 'Tools',
    'summary': 'Módulo de ejemplo para desarrollo custom',
    'description': """
Módulo de ejemplo
=================
Plantilla base para desarrollar módulos personalizados sobre Odoo 17.
    """,
    'author': 'Pyxel',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/mi_modelo_views.xml',
    ],
    'installable': True,
    'application': True,
}
