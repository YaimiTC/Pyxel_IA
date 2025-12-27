{
    "name": "Pyxel - Import Conciliation Report",
    "version": "17.0.1.0.0",
    "category": "Accounting",
    "summary": "Conciliación de ventas (Excel + PDF) con formato estable.",
    "depends": [
        "account",
        "purchase",
        # Si tus campos x_studio viven en un módulo específico, agrega aquí ese módulo.
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/conciliation_wizard_views.xml",
        "views/conciliation_menu.xml",
        "reports/report_conciliation_templates.xml",
        "reports/report_conciliation_actions.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "external_dependencies": {
        "python": ["xlwt"],
    },
}
