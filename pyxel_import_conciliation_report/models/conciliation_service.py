# -*- coding: utf-8 -*-
from odoo import api, models, fields


class PyxelImportConciliationService(models.AbstractModel):
    _name = "pyxel.import.conciliation.service"
    _description = "Pyxel Import Conciliation Service"

    @api.model
    def _get_currency(self, code):
        return self.env["res.currency"].search([("name", "=", code)], limit=1)

    @api.model
    def _is_currency(self, currency, code):
        return bool(currency and (currency.name or "").upper() == code.upper())

    @api.model
    def _filter_contract_to_third_from_import(self, moves, contract_to_third):
        if contract_to_third not in ("yes", "no"):
            return moves
        require_third = (contract_to_third == "yes")
        return moves.filtered(
            lambda m: bool(getattr(getattr(m, "importation_process_id", False), "is_third_party_contract", False)) == require_third
        )

    @api.model
    def _get_container_names_from_process(self, proc):
        load_trackings = getattr(proc, "load_tracking_ids", False)
        if not load_trackings:
            return ""
        seen = set()
        out = []
        for lt in load_trackings:
            n = (lt.name or "").strip()
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return ", ".join(out)

    # -----------------------------
    # Valor mercancía desde POs (convertido a USD)
    # -----------------------------
    @api.model
    def _compute_merchandise_value_usd(self, proc, usd_currency, company):
        """
        'Valor de la mercancía' = suma de POs del proceso.
        Se basa en purchase_order_ids y suma el TOTAL de cada PO.
        Cada PO se convierte a USD según la fecha de la PO (date_order).
        """
        po_ids = getattr(proc, "purchase_order_ids", False)
        if not po_ids:
            return 0.0

        total_usd = 0.0
        for po in po_ids:
            amount = po.amount_total or 0.0  # total en moneda de la PO
            date = (po.date_order.date() if po.date_order else fields.Date.context_today(po))
            total_usd += po.currency_id._convert(amount, usd_currency, company, date)

        return round(total_usd, 2)

    # -----------------------------
    # Public
    # -----------------------------
    @api.model
    def get_lines_by_process(self, data):
        data = data or {}
        date_from = data.get("start_date")
        date_to = data.get("end_date")
        partner_id = data.get("partner_id")
        contract_to_third = data.get("contract_to_third", "all")

        usd = self._get_currency("USD")
        cup = self._get_currency("CUP")
        if not usd:
            raise ValueError("No existe la moneda USD en res.currency")
        if not cup:
            raise ValueError("No existe la moneda CUP en res.currency")

        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("importation_process_id", "!=", False),
        ]
        if date_from and date_to:
            domain += [("invoice_date", ">=", date_from), ("invoice_date", "<=", date_to)]
        if partner_id:
            domain += [("partner_id", "=", int(partner_id))]

        invoices = self.env["account.move"].search(domain, order="invoice_date,id")
        invoices = self._filter_contract_to_third_from_import(invoices, contract_to_third)

        # agrupar por proceso
        by_process = {}
        for inv in invoices:
            pid = inv.importation_process_id.id
            by_process.setdefault(pid, self.env["account.move"])
            by_process[pid] |= inv

        lines = []
        for pid, invs in by_process.items():
            proc = invs[0].importation_process_id
            company = invs[0].company_id

            invs_cup = invs.filtered(lambda m: self._is_currency(m.currency_id, "CUP"))
            invs_fx = invs - invs_cup  # todo lo no-CUP es “extranjero”

            # ---- concatenación nombres
            no_factura_cup = ", ".join(sorted(set([n for n in invs_cup.mapped("name") if n])))
            no_factura_fx = ", ".join(sorted(set([n for n in invs_fx.mapped("name") if n])))

            # ---- FX: convertir cada factura NO-CUP a USD por fecha factura
            total_fx_usd = 0.0
            for mv in invs_fx:
                amount = mv.amount_total or 0.0  # en moneda de la factura
                date = mv.invoice_date or fields.Date.context_today(mv)
                total_fx_usd += mv.currency_id._convert(amount, usd, company, date)

            # ---- CUP TOTAL (✅ incluye especiales, NO se excluyen)
            total_cup = sum((mv.amount_total or 0.0) for mv in invs_cup)

            # ---- Gastos especiales CUP (solo indicador por líneas)
            cup_lines = invs_cup.mapped("invoice_line_ids")
            special_cost_cup = sum(
                (l.price_subtotal or 0.0)
                for l in cup_lines
                if bool(getattr(l, "is_cost_special", False))
            )

            # ---- Valor mercancía desde POs del proceso (en USD)
            merchandise_value_usd = self._compute_merchandise_value_usd(proc, usd, company)

            # ---- campos base
            client = proc.partner_id.name if getattr(proc, "partner_id", False) else invs[0].partner_id.name
            no_import = getattr(proc, "name", "") or getattr(proc, "x_name", "") or proc.display_name
            container = self._get_container_names_from_process(proc)
            account_date = min([d for d in invs.mapped("invoice_date") if d], default=False)

            lines.append({
                "process_id": pid,
                "process_name": proc.display_name,
                "container": container,
                "client": client,
                "no_import": no_import,
                "account_date": account_date,

                # ✅ mercancía (USD)
                "merchandise_value_usd": merchandise_value_usd,

                # facturas concatenadas
                "no_factura_cup": no_factura_cup,
                "no_factura_fx": no_factura_fx,

                # ✅ totales
                "total_cup": round(total_cup, 2),                 # incluye especiales
                "special_cost_cup": round(special_cost_cup, 2),   # indicador aparte

                "total_fx_usd": round(total_fx_usd, 2),

                # si mantienes reparto 50/50:
                "total_fruta": round(total_fx_usd / 2.0, 2),
                "total_pyxel": round(total_fx_usd / 2.0, 2),
            })

        lines.sort(key=lambda x: (x.get("account_date") or fields.Date.today(), x.get("no_import") or ""))
        return lines
