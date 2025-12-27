# -*- coding: utf-8 -*-
from odoo import api, models, fields


class ReportPyxelImportConciliationSales(models.AbstractModel):
    _name = "report.pyxel_import_conciliation_report.r_sales"
    _description = "Report - Acta de Conciliación de Ventas (por proceso)"
    _auto = False

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}

        # ✅ NUEVO: 1 fila por proceso
        lines = self.env["pyxel.import.conciliation.service"].get_lines_by_process(data)

        totals = {
            "merchandise_value_usd": sum((l.get("merchandise_value_usd") or 0.0) for l in lines),
            "total_cup": sum((l.get("total_cup") or 0.0) for l in lines),
            "special_cost_cup": sum((l.get("special_cost_cup") or 0.0) for l in lines),
            "total_fx_usd": sum((l.get("total_fx_usd") or 0.0) for l in lines),
            "total_fruta": sum((l.get("total_fruta") or 0.0) for l in lines),
            "total_pyxel": sum((l.get("total_pyxel") or 0.0) for l in lines),
        }

        return {
            "doc_ids": docids,
            "doc_model": "pyxel.import.conciliation.wizard",
            "docs": lines,
            "date_from": data.get("start_date"),
            "date_to": data.get("end_date"),
            "printed_at": fields.Datetime.now(),
            "totals": totals,
        }
