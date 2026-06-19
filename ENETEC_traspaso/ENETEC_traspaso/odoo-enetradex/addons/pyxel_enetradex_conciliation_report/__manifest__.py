# -*- coding: utf-8 -*-
{
    "name": "Enetradex Conciliation CE-PCT (Excel)",
    "version": "17.0.1.0.0",
    "category": "Accounting",
    "summary": "Conciliación CE-PCT en 3 hojas (USD/CUP/Resumen) - solo Excel",
    "depends": [
        "base",
        "sale",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/conciliation_wizard_view.xml",
        "views/conciliation_menu.xml",
    ],
    "installable": True,
    "application": False,
}
