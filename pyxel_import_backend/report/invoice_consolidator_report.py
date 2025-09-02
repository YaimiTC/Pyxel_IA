# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import logging
from odoo import tools
from odoo import api, fields, models
from odoo.http import request


class InvoiceConsolidatorReport(models.AbstractModel):
    _name = 'reports.pyxel_fruxelimport.invoice_consolidator_report_template'
    _description = 'Invoice Consolidator Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        account_move_obj = self.env['account.move']
        docs = self._get_invoice_report(docids, data)

        return {
            'doc_ids': docids,
            'doc_model': account_move_obj,
            'docs': docs,
            'start_date': data['start_date'],
            'end_date': data['end_date'],
            'partner_id': data['partner_id'],
            'contract_to_third': data['contract_to_third'],
        }

    def _get_invoice_report(self, docids, data=None):
        data = data or {}
        result = []

        # === Dominio base (todas las facturas de cliente de importación) ===
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('x_studio_type_import', 'in', ['operation service', 'tariff']),
        ]
        if docids:
            domain.append(('id', 'in', docids))

        start = data.get('start_date');
        end = data.get('end_date')
        if start and end:
            dfrom = datetime.date.fromisoformat(start)
            dto = datetime.date.fromisoformat(end)
            domain += [('invoice_date', '>=', dfrom), ('invoice_date', '<=', dto)]

        ctt = data.get('contract_to_third')
        if ctt in ('yes', 'no'):
            domain.append(('x_studio_contract_to_third', '=', ctt == 'yes'))

        partner_id = data.get('partner_id')
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id).commercial_partner_id
            domain.append(('commercial_partner_id', '=', partner.id))

        moves = self.env['account.move'].search(domain)
        if not moves:
            return result

        # === Agrupar por importación ===
        by_import = {}
        for m in moves:
            imp_id = m.x_studio_import_id.id if m.x_studio_import_id else False
            by_import.setdefault(imp_id, self.env['account.move'])
            by_import[imp_id] |= m

        # --- helpers ---
        def _guess_po_ids_from_move(move):
            """Intenta detectar PO(s) asociados a una factura (por campo directo o contenedores/lineas)."""
            po_ids = set()
            # 1) Campo directo custom (si existe)
            x_po = getattr(move, 'x_studio_purchase_id', False)
            if x_po:
                po_ids.add(x_po.id)

            # 2) Vía contenedores y sus líneas
            for c in getattr(move, 'x_studio_container_ids', self.env['x.container'].browse()):
                c_po = getattr(c, 'x_studio_purchase_id', False)
                if c_po:
                    po_ids.add(c_po.id)
                for ol in getattr(c, 'x_studio_order_lines_by_container', []):
                    # distintos posibles nombres de campo
                    if getattr(ol, 'order_id', False):
                        po_ids.add(ol.order_id.id)
                    elif getattr(ol, 'purchase_id', False):
                        po_ids.add(ol.purchase_id.id)
                    elif getattr(ol, 'purchase_line_id', False):
                        po_ids.add(ol.purchase_line_id.order_id.id)

            # 3) Si no se encontró nada, cuélgalo en None (grupo “sin PO”)
            if not po_ids:
                po_ids.add(None)
            return po_ids

        def _compute_merch_value_for_po(src_move, po_id):
            """Calcula valor de mercancía por PO (usando contenedores; si no, el total de la PO)."""
            merchandise_value = 0.0
            currency_merch = ''
            # Preferir contenedores (y filtrar por PO si es posible)
            if src_move and getattr(src_move, 'x_studio_container_ids', False):
                for c in src_move.x_studio_container_ids:
                    for ol in getattr(c, 'x_studio_order_lines_by_container', []):
                        rel_po_id = (
                                            getattr(ol, 'order_id', False) and ol.order_id.id
                                    ) or (getattr(ol, 'purchase_id', False) and ol.purchase_id.id) or (
                                            getattr(ol, 'purchase_line_id', False) and ol.purchase_line_id.order_id.id
                                    ) or None
                        if po_id is None or (rel_po_id and rel_po_id == po_id):
                            merchandise_value += (getattr(ol, 'x_studio_total', 0.0) or 0.0)
                            cur = getattr(getattr(ol, 'x_studio_currency_id', False), 'name', '')
                            currency_merch = cur or currency_merch
                    # Los costos suelen no estar por PO; se incluyen (o limita si necesitas)
                    for cl in getattr(c, 'x_studio_container_cost_lines', []):
                        merchandise_value += (getattr(cl, 'x_studio_total', 0.0) or 0.0)
            else:
                # Fallback: total de la PO
                if po_id:
                    po = self.env['purchase.order'].browse(po_id)
                    if po.exists():
                        merchandise_value = po.amount_total
                        currency_merch = po.currency_id.name
            return round(merchandise_value, 2), currency_merch

        # === Por cada importación, agrupar por PO y emparejar USD+CUP ===
        for imp_id, imp_moves in by_import.items():
            # Mapa: PO -> {'usd': recordset, 'cup': recordset}
            per_po = {}
            for m in imp_moves:
                for po_id in _guess_po_ids_from_move(m):
                    per_po.setdefault(po_id, {'usd': self.env['account.move'], 'cup': self.env['account.move']})
                    if m.x_studio_type_import == 'operation service':
                        per_po[po_id]['usd'] |= m
                    else:
                        per_po[po_id]['cup'] |= m

            # Emparejar por fecha dentro de cada PO
            for po_id, bucket in per_po.items():
                usd_list = bucket['usd'].sorted(key=lambda r: (r.invoice_date or r.create_date or fields.Date.today()))
                cup_list = bucket['cup'].sorted(key=lambda r: (r.invoice_date or r.create_date or fields.Date.today()))
                max_pairs = max(len(usd_list), len(cup_list))

                # Obtener nombre de importación/cliente/PO para imprimir
                def _imp_name(rec):
                    return (rec.x_studio_import_id and rec.x_studio_import_id.x_name) or ''

                def _client_name(usd, cup):
                    return (cup and cup.partner_id.name) or (usd and usd.partner_id.name) or ''

                po_name = '(Sin PO)'
                if po_id:
                    po = self.env['purchase.order'].browse(po_id)
                    if po.exists():
                        po_name = po.name

                for i in range(max_pairs):
                    usd = usd_list[i] if i < len(usd_list) else self.env['account.move']
                    cup = cup_list[i] if i < len(cup_list) else self.env['account.move']

                    # Valor mercancía por PO (tomando preferentemente contenedores del USD; si no, CUP)
                    src_for_merch = usd or cup
                    merchandise_value, currency_merch = _compute_merch_value_for_po(src_for_merch, po_id)

                    # Desglose CUP con/sin margen
                    with_margin = 0.0
                    without_margin = 0.0
                    if cup:
                        for line in cup.invoice_line_ids:
                            if getattr(line, 'include_in_special_margin', False):
                                with_margin += line.price_subtotal
                            else:
                                without_margin += line.price_subtotal

                    # Contenedor por importación (AWB/B-L)
                    def _container_flag(rec):
                        if not rec:
                            return '(AWB)'
                        imp = rec.x_studio_import_id
                        cbi = rec.x_studio_container_by_import
                        if cbi or (imp and getattr(imp, 'x_studio_certifies_receipt_load', None) == '(B/L)'):
                            return cbi or '(B/L)'
                        return '(AWB)'

                    usd_total = round((usd.amount_total or 0.0), 2) if usd else 0.0
                    vals = {
                        'import_id': imp_id,
                        'no_import': _imp_name(usd) or _imp_name(cup),
                        'purchase_id': po_id,
                        'purchase_name': po_name,
                        'client': _client_name(usd, cup),
                        'container_by_import': _container_flag(cup) if cup else _container_flag(usd),
                        'merchandise_value': merchandise_value,
                        'currency_merchandise': currency_merch,
                        'account_date': usd.invoice_date or cup.invoice_date,
                        'no_account_cup': cup.name or '',
                        'amount_total_cup': round((cup.amount_total or 0.0), 2) if cup else 0.0,
                        'no_account_usd': usd.name or '',
                        'amount_total_usd': usd_total,
                        'total_fruta': round(usd_total / 2.0, 2),
                        'total_pyxel': round(usd_total / 2.0, 2),
                        'cup_total_with_margin': round(with_margin, 2),
                        'cup_total_without_margin': round(without_margin, 2),
                    }
                    result.append(vals)

        return result
