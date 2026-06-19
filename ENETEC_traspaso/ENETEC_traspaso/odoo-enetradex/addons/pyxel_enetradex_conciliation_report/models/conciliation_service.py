# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PyxelEnetradexConciliationService(models.AbstractModel):
    _name = "pyxel.enetradex.conciliation.service"
    _description = "Service Conciliación ENETEC CE-PCT (por proceso)"

    @api.model
    def _get_currency(self, code):
        cur = self.env["res.currency"].search([("name", "=", code)], limit=1)
        if not cur:
            raise UserError(_("No existe la moneda %s en res.currency") % code)
        return cur

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
    def _get_container_names(self, proc):
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

    @api.model
    def _get_sli(self, proc):
        return getattr(getattr(proc, "process_id", False), "name", "") or ""

    @api.model
    def _compute_merchandise_value_usd(self, proc, usd_currency, company):
        po_ids = getattr(proc, "purchase_order_ids", False)
        if not po_ids:
            return 0.0
        total = 0.0
        for po in po_ids:
            amount = po.amount_total or 0.0
            date = (po.date_order.date() if po.date_order else fields.Date.context_today(po))
            total += po.currency_id._convert(amount, usd_currency, company, date)
        return round(total, 2)

    @api.model
    def _process_matches_supplier(self, proc, supplier_id, strict=False):
        """
        True si el proceso tiene POs con ese proveedor.
        - strict=False: con que exista al menos una PO del proveedor => OK
        - strict=True: todas las POs del proceso deben ser de ese proveedor
        """
        if not supplier_id:
            return True

        pos = getattr(proc, "purchase_order_ids", False)
        if not pos:
            return False

        if strict:
            return all(po.partner_id and po.partner_id.id == supplier_id for po in pos)
        return any(po.partner_id and po.partner_id.id == supplier_id for po in pos)

    @api.model
    def _filter_by_supplier_on_process(self, invoices, supplier_id, strict=False):
        """
        Filtra facturas dejando solo aquellas cuyo proceso tenga POs del proveedor.
        """
        if not supplier_id:
            return invoices

        supplier_id = int(supplier_id)

        def _ok(mv):
            proc = getattr(mv, "importation_process_id", False)
            return bool(proc) and self._process_matches_supplier(proc, supplier_id, strict=strict)

        return invoices.filtered(_ok)

    @api.model
    def get_lines(self, data):
        data = data or {}
        date_from = data.get("start_date")
        date_to = data.get("end_date")
        partner_id = data.get("partner_id")
        supplier_id = data.get("supplier_id")
        contract_to_third = data.get("contract_to_third", "all")

        usd = self._get_currency("USD")

        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_type", "=", "import_service"),
            ("importation_process_id", "!=", False),
        ]
        if date_from and date_to:
            domain += [("invoice_date", ">=", date_from), ("invoice_date", "<=", date_to)]
        if partner_id:
            domain += [("partner_id", "=", int(partner_id))]

        moves = self.env["account.move"].search(domain, order="invoice_date,id")
        moves = self._filter_contract_to_third_from_import(moves, contract_to_third)

        # filtro por supplier usando las POs del proceso
        if supplier_id:
            moves = self._filter_by_supplier_on_process(moves, supplier_id, strict=False)

        by_process = {}
        for m in moves:
            pid = m.importation_process_id.id
            by_process.setdefault(pid, self.env["account.move"])
            by_process[pid] |= m

        lines = []
        for pid, invs in by_process.items():
            proc = invs[0].importation_process_id
            company = invs[0].company_id

            invs_cup = invs.filtered(lambda x: self._is_currency(x.currency_id, "CUP"))
            invs_fx = invs - invs_cup

            no_factura_cup = ", ".join(sorted(set([n for n in invs_cup.mapped("name") if n])))
            no_factura_fx = ", ".join(sorted(set([n for n in invs_fx.mapped("name") if n])))

            total_cup = sum((x.amount_total or 0.0) for x in invs_cup)

            total_fx_usd = 0.0
            for mv in invs_fx:
                amount = mv.amount_total or 0.0
                date = mv.invoice_date or fields.Date.context_today(mv)
                total_fx_usd += mv.currency_id._convert(amount, usd, company, date)

            merchandise_value_usd = self._compute_merchandise_value_usd(proc, usd, company)

            client = getattr(getattr(proc, "partner_id", False), "name", "") or invs[0].partner_id.name
            account_date = min([d for d in invs.mapped("invoice_date") if d], default=False)

            lines.append({
                "process_id": pid,
                "process_name": proc.display_name,
                "container": self._get_container_names(proc),
                "client": client,
                "sli_no": self._get_sli(proc),
                "account_date": account_date,
                "merchandise_value_usd": merchandise_value_usd,
                "no_factura_fx": no_factura_fx,
                "total_fx_usd": round(total_fx_usd, 2),
                "no_factura_cup": no_factura_cup,
                "total_cup": round(total_cup, 2),
            })

        lines.sort(key=lambda x: (x.get("account_date") or fields.Date.today(), x.get("sli_no") or ""))
        return lines