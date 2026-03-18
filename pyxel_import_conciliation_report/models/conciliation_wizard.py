# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PyxelImportConciliationWizard(models.TransientModel):
    _name = "pyxel.import.conciliation.wizard"
    _description = "Pyxel Import Conciliation Wizard"

    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    partner_id = fields.Many2one("res.partner", string="Cliente")

    supplier_id = fields.Many2one('res.partner', string='Proveedor')

    contract_to_third = fields.Selection(
        selection=[("all", "Todos"), ("yes", "Sí"), ("no", "No")],
        default="all",
        required=True,
        string="Contrato a terceros",
    )

    type_conciliation = fields.Selection(
        selection=[
            ("sales", "Conciliación de Ventas"),
            # ("logistics", "Conciliación Logística")  # si lo activas luego
        ],
        default="sales",
        required=True,
        string="Tipo",
    )

    format_of_report = fields.Selection(
        selection=[("xls", "Excel"), ("pdf", "PDF")],
        default="xls",
        required=True,
        string="Formato",
    )

    def _build_payload(self):
        self.ensure_one()
        return {
            "start_date": self.start_date.isoformat() if self.start_date else False,
            "end_date": self.end_date.isoformat() if self.end_date else False,
            "partner_id": self.partner_id.id or False,
            "supplier_id": self.supplier_id.id or False,
            "contract_to_third": self.contract_to_third,
            "type_conciliation": self.type_conciliation,
        }

    def action_generate_report(self):
        self.ensure_one()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise UserError(_("La fecha inicial no puede ser mayor que la fecha final."))

        payload = self._build_payload()

        if self.format_of_report == "pdf":
            return self.env.ref(
                "pyxel_import_conciliation_report.action_report_pyxel_import_conciliation_sales"
            ).report_action(self, data=payload)

        # XLS (por proceso)
        lines = self.env["pyxel.import.conciliation.service"].get_lines_by_process(payload)
        if not lines:
            raise UserError(_("No existen facturas en el período definido."))
        return self.env["pyxel.import.conciliation.xls_exporter"].export_sales(lines, payload)

    @api.constrains("start_date", "end_date")
    def _check_date_range(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(_("La fecha inicial no puede ser mayor que la fecha final."))
