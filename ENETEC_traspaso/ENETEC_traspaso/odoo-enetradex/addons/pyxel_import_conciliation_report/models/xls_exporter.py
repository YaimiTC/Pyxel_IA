# -*- coding: utf-8 -*-
import base64
import datetime
import os
import tempfile

from odoo import api, models, _
from odoo.exceptions import UserError


class PyxelImportConciliationXlsExporter(models.AbstractModel):
    _name = "pyxel.import.conciliation.xls_exporter"
    _description = "Pyxel Import Conciliation XLS Exporter (por proceso)"

    @api.model
    def export_sales(self, lines, data):
        """
        Exporta 1 fila por proceso con columnas:
          - Valor mercancia (USD) desde POs
          - Facturas CUP concatenadas + Total CUP (incluye especiales)
          - Gastos especiales (CUP) en columna aparte
          - Facturas FX concatenadas + Total FX convertido a USD
        """
        try:
            import xlwt
        except Exception:
            xlwt = None
        if xlwt is None:
            raise UserError(_("Falta la dependencia python: xlwt"))

        data = data or {}
        filename = "Conciliacion_Ventas_Por_Proceso_{}_{}.xls".format(
            data.get("start_date", ""), data.get("end_date", "")
        )

        headers = [
            ("No", 6),
            ("Contenedor", 28),
            ("Cliente", 28),
            ("Valor mercancia (USD)", 20),
            ("No. Importación", 18),
            ("Fecha", 14),
            ("No. Factura (CUP)", 40),
            ("Total (CUP)", 16),
            ("Gastos Especiales (CUP)", 22),
            ("No. Factura (FX)", 40),
            ("Total FX (USD)", 18),
            ("Valor Frutas (USD)", 18),
            ("Valor Pyxel (USD)", 18),
        ]

        fd, tmp_path = tempfile.mkstemp()
        try:
            wb = xlwt.Workbook()
            ws = wb.add_sheet("Conciliacion Ventas")

            # styles
            style_header = xlwt.easyxf(
                "font: bold on; align: horiz center, vert center; "
                "borders: left thin, right thin, top thin, bottom thin"
            )
            style_cell = xlwt.easyxf(
                "align: horiz center, vert center; "
                "borders: left thin, right thin, top thin, bottom thin"
            )
            style_int = xlwt.easyxf(
                "align: horiz center, vert center; "
                "borders: left thin, right thin, top thin, bottom thin"
            )
            style_date = xlwt.easyxf(
                "align: horiz center, vert center; "
                "borders: left thin, right thin, top thin, bottom thin"
            )
            style_date.num_format_str = "dd-mmm-yy"

            style_money = xlwt.easyxf(
                "align: horiz center, vert center; "
                "borders: left thin, right thin, top thin, bottom thin"
            )
            style_money.num_format_str = "$#,##0.00"

            style_total_label = xlwt.easyxf(
                "font: bold on; align: horiz center, vert center; "
                "borders: left thin, right thin, top thin, bottom thin"
            )
            style_total_money = xlwt.easyxf(
                "font: bold on; align: horiz center, vert center; "
                "borders: left thin, right thin, top thin, bottom thin"
            )
            style_total_money.num_format_str = "$#,##0.00"

            style_title = xlwt.easyxf("font: bold on, height 320; align: horiz center, vert center;")
            style_subtitle = xlwt.easyxf("font: bold on; align: horiz center, vert center;")
            style_info = xlwt.easyxf("align: horiz left, vert center;")

            def _to_date(v):
                if isinstance(v, datetime.datetime):
                    return v.date()
                if isinstance(v, datetime.date):
                    return v
                if isinstance(v, str) and v:
                    try:
                        return datetime.datetime.strptime(v, "%Y-%m-%d").date()
                    except Exception:
                        return ""
                return ""

            def _to_float(v):
                try:
                    return float(v or 0.0)
                except Exception:
                    return 0.0

            def _excel_col_name(n):
                name = ""
                while True:
                    n, r = divmod(n, 26)
                    name = chr(ord("A") + r) + name
                    if n == 0:
                        break
                    n -= 1
                return name

            # ---------------------------------------------------------
            # Header (3 filas arriba) + merge
            # ---------------------------------------------------------
            date_from = (data.get("start_date") or "")
            date_to = (data.get("end_date") or "")

            # contrato a terceros label
            contract_map = {
                "all": "Todos",
                "yes": "Sí",
                "no": "No",
            }
            contract_label = contract_map.get(data.get("contract_to_third"), "Todos")

            # Título + subtítulo
            title = "ACTA DE CONCILIACION DE VENTAS"
            subtitle = f"Desde: {date_from}  Hasta: {date_to}  |  Contrato a terceros: {contract_label}"

            # merge sobre todas las columnas (0..12)
            last_col = len(headers) - 1

            ws.write_merge(0, 0, 0, last_col, title, style_title)
            ws.write_merge(1, 1, 0, last_col, subtitle, style_subtitle)

            header_row = 3

            for c, (title, width) in enumerate(headers):
                ws.write(header_row, c, title, style_header)
                ws.col(c).width = 256 * int(width)

            first_data_row = header_row + 1
            r = first_data_row

            # data rows
            for idx, line in enumerate(lines or [], start=1):
                ws.write(r, 0, idx, style_int)
                ws.write(r, 1, (line.get("container") or ""), style_cell)
                ws.write(r, 2, (line.get("client") or ""), style_cell)

                ws.write(r, 3, _to_float(line.get("merchandise_value_usd")), style_money)
                ws.write(r, 4, (line.get("no_import") or ""), style_cell)
                ws.write(r, 5, _to_date(line.get("account_date")), style_date)

                ws.write(r, 6, (line.get("no_factura_cup") or ""), style_cell)
                ws.write(r, 7, _to_float(line.get("total_cup")), style_money)
                ws.write(r, 8, _to_float(line.get("special_cost_cup")), style_money)

                ws.write(r, 9, (line.get("no_factura_fx") or ""), style_cell)
                ws.write(r, 10, _to_float(line.get("total_fx_usd")), style_money)

                ws.write(r, 11, _to_float(line.get("total_fruta")), style_money)
                ws.write(r, 12, _to_float(line.get("total_pyxel")), style_money)

                r += 1

            # totals row
            if lines:
                last_data_row = r - 1
                totals_row = r

                # etiqueta "Total" en Cliente (col 2)
                ws.write(totals_row, 2, "Total", style_total_label)

                def _sum_formula(col_idx):
                    col = _excel_col_name(col_idx)
                    return xlwt.Formula(f"SUM({col}{first_data_row + 1}:{col}{last_data_row + 1})")

                # sumas numéricas
                for col_idx in (3, 7, 8, 10, 11, 12):
                    ws.write(totals_row, col_idx, _sum_formula(col_idx), style_total_money)

            wb.save(tmp_path)

            attachment = self.env["ir.attachment"].create({
                "name": filename,
                "mimetype": "application/vnd.ms-excel",
                "datas": base64.b64encode(open(tmp_path, "rb").read()),
                "res_model": "res.user",
                "res_id": self.env.user.id,
            })
            return {
                "type": "ir.actions.act_url",
                "target": "new",
                "url": f"/web/content/{attachment.id}?download=true",
            }
        finally:
            try:
                os.close(fd)
            except Exception:
                pass
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
