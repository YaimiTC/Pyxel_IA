# -*- coding: utf-8 -*-
import base64
import datetime
import os
import tempfile

from odoo import api, models,fields, _
from odoo.exceptions import UserError


class PyxelEnetradexConciliationXlsExporter(models.AbstractModel):
    _name = "pyxel.enetradex.conciliation.xls_exporter"
    _description = "XLS Exporter ENETEC CE-PCT (USD/CUP/Resumen)"

    @api.model
    def export_excel(self, lines, data):
        try:
            import xlwt
        except Exception:
            xlwt = None
        if xlwt is None:
            raise UserError(_("Falta la dependencia python: xlwt"))

        data = data or {}
        date_from = data.get("start_date") or ""
        date_to = data.get("end_date") or ""

        contract_map = {"all": "Todos", "yes": "Sí", "no": "No"}
        contract_label = contract_map.get(data.get("contract_to_third"), "Todos")

        platform_name = data.get("platform_name") or ""
        provider_import_name = data.get("provider_import_name") or "ENETEC"
        pyxel_name = data.get("pyxel_name") or "PYXEL SOLUTIONS SRL"

        lines = lines or []

        def _f(v):
            try:
                return float(v or 0.0)
            except Exception:
                return 0.0

        def _to_date(v):
            if isinstance(v, datetime.datetime):
                return v.date()
            if isinstance(v, datetime.date):
                return v
            return v or ""

        usd_lines = [l for l in lines if (l.get("no_factura_fx") or _f(l.get("total_fx_usd")))]
        cup_lines = [l for l in lines if (l.get("no_factura_cup") or _f(l.get("total_cup")))]

        filename = f"Conciliacion_CE_PCT_{date_from}_{date_to}.xls"

        # ---------------- Styles ----------------
        st_title_y = xlwt.easyxf(
            "font: bold on; align: horiz left, vert center;"
        )

        st_title = xlwt.easyxf("font: bold on, height 320; align: horiz left, vert center;")

        st_h_y = xlwt.easyxf(
            "font: bold on; "
            "align: horiz center, vert center; "
            "borders: left thin, right thin, top thin, bottom thin"
        )

        st_h = xlwt.easyxf(
            "font: bold on; align: horiz center, vert center; "
            "borders: left thin, right thin, top thin, bottom thin"
        )
        st_c = xlwt.easyxf(
            "align: horiz center, vert center; "
            "borders: left thin, right thin, top thin, bottom thin"
        )
        st_l = xlwt.easyxf(
            "align: horiz left, vert center; "
            "borders: left thin, right thin, top thin, bottom thin"
        )
        st_d = xlwt.easyxf(
            "align: horiz center, vert center; "
            "borders: left thin, right thin, top thin, bottom thin"
        )
        st_d.num_format_str = "dd/mm/yyyy"

        st_m = xlwt.easyxf(
            "align: horiz center, vert center; "
            "borders: left thin, right thin, top thin, bottom thin"
        )
        st_m.num_format_str = "$#,##0.00"

        # Totales (bordes completos)
        st_tot_txt = xlwt.easyxf(
            "font: bold on; align: horiz center, vert center; "
            "borders: left thin, right thin, top thin, bottom thin"
        )
        st_tot_money = xlwt.easyxf(
            "font: bold on; align: horiz center, vert center; "
            "borders: left thin, right thin, top thin, bottom thin"
        )
        st_tot_money.num_format_str = "$#,##0.00"

        # ---------------- Helpers ----------------
        def _write_total_row(ws, row, label_col=2, label="TOTAL", money_map=None, last_col=9):
            """Escribe toda la fila una sola vez (sin overwrite) con bordes completos."""
            money_map = money_map or {}
            for cc in range(0, last_col + 1):
                if cc == label_col:
                    ws.write(row, cc, label, st_tot_txt)
                elif cc in money_map:
                    ws.write(row, cc, float(money_map[cc] or 0.0), st_tot_money)
                else:
                    ws.write(row, cc, "", st_tot_txt)

        def build_sheet(ws, cur_label):
            ws.write_merge(0, 0, 0, 2, "SERVICIO PLATAFORMA:", st_title_y)
            ws.write_merge(0, 0, 3, 9, platform_name or "", st_title_y)
            ws.write_merge(
                1, 1, 0, 9,
                f"ACTA DE CONCILIACIÓN CE-PCT ({cur_label}) | Desde: {date_from} Hasta: {date_to} | Contrato a 3ro: {contract_label}",
                st_title
            )

            headers = [
                ("No.", 6, st_h),
                ("Contenedor", 18, st_h),
                ("Cliente", 38, st_h),
                ("Valor de la mercancia (USD)", 22, st_h_y),
                ("No. SLI", 16, st_h_y),
                ("Fecha de la Factura", 18, st_h),
                (f"No. Factura de CE al cliente ({cur_label})", 36, st_h_y),
                (f"Monto de la Factura ({cur_label})", 22, st_h_y),
                (f"Valor CE ({cur_label})", 22, st_h_y),
                (f"Monto a facturar por el PCT ({cur_label})", 28, st_h_y),
            ]
            for c, (t, w, st) in enumerate(headers):
                ws.write(3, c, t, st)
                ws.col(c).width = 256 * int(w)

        fd, tmp = tempfile.mkstemp()
        try:
            wb = xlwt.Workbook()

            # ---------------- USD sheet ----------------
            ws_usd = wb.add_sheet("MODELO CE-PCT USD")
            build_sheet(ws_usd, "USD")

            r = 4
            total_pct_usd = 0.0
            for idx, l in enumerate(usd_lines, start=1):
                monto = _f(l.get("total_fx_usd"))
                ce = round(monto * 0.7, 2)
                pct = round(monto * 0.3, 2)
                total_pct_usd += pct

                ws_usd.write(r, 0, idx, st_c)
                ws_usd.write(r, 1, l.get("container") or "", st_c)
                ws_usd.write(r, 2, l.get("client") or "", st_l)
                ws_usd.write(r, 3, _f(l.get("merchandise_value_usd")), st_m)
                ws_usd.write(r, 4, l.get("sli_no") or "", st_c)
                ws_usd.write(r, 5, _to_date(l.get("account_date")), st_d)
                ws_usd.write(r, 6, l.get("no_factura_fx") or "", st_c)
                ws_usd.write(r, 7, monto, st_m)
                ws_usd.write(r, 8, ce, st_m)
                ws_usd.write(r, 9, pct, st_m)
                r += 1

            if usd_lines:
                total_monto = sum(_f(x.get("total_fx_usd")) for x in usd_lines)
                total_ce = sum(round(_f(x.get("total_fx_usd")) * 0.7, 2) for x in usd_lines)
                total_pct = round(total_pct_usd, 2)
                _write_total_row(
                    ws_usd, r,
                    label_col=2,
                    label="TOTAL",
                    money_map={7: total_monto, 8: total_ce, 9: total_pct},
                    last_col=9
                )

            # ---------------- CUP sheet ----------------
            ws_cup = wb.add_sheet("MODELO CE-PCT CUP")
            build_sheet(ws_cup, "CUP")

            r = 4
            total_pct_cup = 0.0
            for idx, l in enumerate(cup_lines, start=1):
                monto = _f(l.get("total_cup"))
                ce = round(monto * 0.7, 2)
                pct = round(monto * 0.3, 2)
                total_pct_cup += pct

                ws_cup.write(r, 0, idx, st_c)
                ws_cup.write(r, 1, l.get("container") or "", st_c)
                ws_cup.write(r, 2, l.get("client") or "", st_l)
                ws_cup.write(r, 3, _f(l.get("merchandise_value_usd")), st_m)
                ws_cup.write(r, 4, l.get("sli_no") or "", st_c)
                ws_cup.write(r, 5, _to_date(l.get("account_date")), st_d)
                ws_cup.write(r, 6, l.get("no_factura_cup") or "", st_c)
                ws_cup.write(r, 7, monto, st_m)
                ws_cup.write(r, 8, ce, st_m)
                ws_cup.write(r, 9, pct, st_m)
                r += 1

            if cup_lines:
                total_monto = sum(_f(x.get("total_cup")) for x in cup_lines)
                total_ce = sum(round(_f(x.get("total_cup")) * 0.7, 2) for x in cup_lines)
                total_pct = round(total_pct_cup, 2)
                _write_total_row(
                    ws_cup, r,
                    label_col=2,
                    label="TOTAL",
                    money_map={7: total_monto, 8: total_ce, 9: total_pct},
                    last_col=9
                )

            # ---------------- RESUMEN sheet ----------------
            ws_sum = wb.add_sheet("MODELO PYXEL-PCT")

            # Estilos caja
            st_box = xlwt.easyxf(
                "borders: left thin, right thin, top thin, bottom thin;"
                "align: horiz left, vert center;"
            )
            st_box_bold = xlwt.easyxf(
                "font: bold on;"
                "borders: left thin, right thin, top thin, bottom thin;"
                "align: horiz left, vert center;"
            )
            st_box_center = xlwt.easyxf(
                "borders: left thin, right thin, top thin, bottom thin;"
                "align: horiz center, vert center;"
            )
            st_box_center_bold = xlwt.easyxf(
                "font: bold on;"
                "borders: left thin, right thin, top thin, bottom thin;"
                "align: horiz center, vert center;"
            )
            st_box_money = xlwt.easyxf(
                "borders: left thin, right thin, top thin, bottom thin;"
                "align: horiz center, vert center;"
            )
            st_box_money.num_format_str = "$#,##0.00"

            st_box_title = xlwt.easyxf(
                "font: bold on, height 320;"
                "align: horiz center, vert center;"
                "borders: left thin, right thin, top thin, bottom thin;"
            )

            # Para firmas (solo línea superior)
            st_sig = xlwt.easyxf(
                "font: bold on;"
                "align: horiz center, vert center;"
                "borders: top thin;"
            )

            # Layout: columnas A..E (0..4)
            ws_sum.col(0).width = 256 * 18  # A labels
            ws_sum.col(1).width = 256 * 28  # B
            ws_sum.col(2).width = 256 * 28  # C
            ws_sum.col(3).width = 256 * 18  # D USD
            ws_sum.col(4).width = 256 * 18  # E CUP

            # Título
            ws_sum.write_merge(
                0, 0, 0, 4,
                "ACTA DE CONCILIACIÓN DEL SERVICIO DE IMPORTACIÓN ENETEC",
                st_box_title
            )

            # Encabezados (sin celda “en medio”)
            ws_sum.write_merge(2, 2, 0, 1, "MES:", st_box_bold)
            ws_sum.write_merge(2, 2, 2, 4, "0", st_box_center)

            ws_sum.write_merge(4, 4, 0, 1, "PROVEEDOR DEL SERVICIO DE IMPORTACIÓN:", st_box_bold)
            ws_sum.write_merge(4, 4, 2, 4, provider_import_name, st_box)

            ws_sum.write_merge(6, 6, 0, 1, "SERVICIO PLATAFORMA:", st_box_bold)
            ws_sum.write_merge(6, 6, 2, 4, platform_name or "", st_box)

            ws_sum.write_merge(7, 7, 0, 1, "SERVICIO PLATAFORMA:", st_box_bold)
            ws_sum.write_merge(7, 7, 2, 4, pyxel_name, st_box)

            # Tabla (AHORA con USD + CUP)
            tr = 9
            ws_sum.write_merge(tr, tr, 0, 1, "No.", st_box_center_bold)
            ws_sum.write_merge(tr, tr, 2, 2, "Descripción", st_box_center_bold)  # solo columna C
            ws_sum.write(tr, 3, "Monto (USD)", st_box_center_bold)
            ws_sum.write(tr, 4, "Monto (CUP)", st_box_center_bold)

            # Valores base: TOTAL PCT (0.3) para USD y CUP
            r1 = tr + 1
            ws_sum.write_merge(r1, r1, 0, 1, 1, st_box_center)
            ws_sum.write_merge(r1, r1, 2, 2, "MONTO FACTURADO AL PROVEEDOR DEL SERVICIO DE IMPORTACIÓN", st_box)
            ws_sum.write(r1, 3, round(total_pct_usd, 2), st_box_money)
            ws_sum.write(r1, 4, round(total_pct_cup, 2), st_box_money)

            r2 = r1 + 1
            ws_sum.write_merge(r2, r2, 0, 1, 2, st_box_center)
            ws_sum.write_merge(r2, r2, 2, 2, "PARA PCT", st_box)
            ws_sum.write(r2, 3, round(total_pct_usd * 0.1, 2), st_box_money)
            ws_sum.write(r2, 4, round(total_pct_cup * 0.1, 2), st_box_money)

            r3 = r2 + 1
            ws_sum.write_merge(r3, r3, 0, 1, 3, st_box_center)  # ya no 10, ahora 3
            ws_sum.write_merge(r3, r3, 2, 2, "PARA PYXEL SRL", st_box)
            ws_sum.write(r3, 3, round(total_pct_usd * 0.9, 2), st_box_money)
            ws_sum.write(r3, 4, round(total_pct_cup * 0.9, 2), st_box_money)

            # ---------------- Firmas (con columna intermedia sin borde) ----------------
            sig_row = r3 + 6
            left_sig = platform_name or "PARQUE CIENTÍFICO TECNOLÓGICO DE LA HABANA"

            # Firma izquierda: A..B
            ws_sum.write_merge(sig_row, sig_row, 0, 1, left_sig, st_sig)

            # Columna intermedia C (sin borde)
            ws_sum.write(sig_row, 2, "", xlwt.easyxf(""))

            # Firma derecha: D..E
            ws_sum.write_merge(sig_row, sig_row, 3, 4, pyxel_name, st_sig)

            # Fecha (abajo izquierda)
            date_str = fields.Date.context_today(self).strftime("%d de %B de %Y")
            ws_sum.write_merge(
                sig_row + 3, sig_row + 3, 0, 2,
                f"La Habana, {date_str}",
                xlwt.easyxf("align: horiz left, vert center;")
            )

            # ---------------- Save & download ----------------
            wb.save(tmp)

            attachment = self.env["ir.attachment"].create({
                "name": filename,
                "mimetype": "application/vnd.ms-excel",
                "datas": base64.b64encode(open(tmp, "rb").read()),
                "res_model": "res.user",
                "res_id": self.env.user.id,
            })
            return {"type": "ir.actions.act_url", "target": "new", "url": f"/web/content/{attachment.id}?download=true"}

        finally:
            try:
                os.close(fd)
            except Exception:
                pass
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except Exception:
                pass
