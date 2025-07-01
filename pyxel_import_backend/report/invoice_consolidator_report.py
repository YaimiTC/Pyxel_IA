# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import logging
from odoo import tools
from odoo import api, fields, models
from odoo.http import request


class InvoiceConsolidatorReport(models.AbstractModel):
    _name = 'report.pyxel_fruxelimport.invoice_consolidator_report_template'
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
        domain = []
        if len(docids) > 0:
            domain = [('id', 'in', docids)]
        if data['start_date'] and data['end_date']:
            date_from = datetime.datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            date_to = datetime.datetime.strptime(data['end_date'], '%Y-%m-%d').date()

            domain = [
                ('invoice_date', '<=', date_to),
                ('invoice_date', '>=', date_from),
                ('move_type', '=', 'out_invoice')
            ]

        if data['contract_to_third'] in ('yes', 'no'):
            domain.append(('x_studio_contract_to_third', '=', True if data['contract_to_third'] == 'yes' else False))

        if data['partner_id']:
            invoice_partner = self.env['res.partner'].browse(data['partner_id'])
            domain.append(('invoice_partner_display_name', '=', invoice_partner.display_name))

        domain.append('|')
        domain.append(('x_studio_type_import', '=', 'operation service'))
        domain.append(('x_studio_type_import', '=', 'tariff'))

        # Agrupación por importación
        groupby_fields = ['x_studio_import_id']
        account_records = self.env['account.move'].read_group(domain, groupby_fields,
                                                              ['x_studio_import_id', 'id:count'])

        result_records = []

        if account_records:
            for move in account_records:
                x_studio_import_id = (
                    move['x_studio_import_id'][0]
                    if isinstance(move.get('x_studio_import_id'), (list, tuple)) and move['x_studio_import_id']
                    else None
                )
                record_count = move.get('x_studio_import_id_count', 0)

                if record_count > 1:
                    account_cup = self.env['account.move'].search(
                        [('x_studio_import_id', '=', x_studio_import_id), ('x_studio_type_import', '=', 'tariff')],
                        limit=1)
                    account_usd = self.env['account.move'].search(
                        [('x_studio_import_id', '=', x_studio_import_id),
                         ('x_studio_type_import', '=', 'operation service')], limit=1)

                    merchandise_value = 0
                    currency_merchandise = ''
                    if account_usd.x_studio_container_ids:
                        for container in account_usd.x_studio_container_ids:
                            for line in container.x_studio_order_lines_by_container:
                                merchandise_value += line.x_studio_total
                                currency_merchandise = line.x_studio_currency_id.name
                            for cost_line in container.x_studio_container_cost_lines:
                                merchandise_value += cost_line.x_studio_total
                    else:
                        merchandise_value = sum(
                            [p.amount_total for p in account_usd.x_studio_import_id.x_studio_purchase_ids])

                    if account_cup and account_usd:
                        # Nuevos cálculos de desglose CUP
                        total_with_margin_cup = 0
                        total_without_margin_cup = 0

                        for line in account_cup.invoice_line_ids:
                            if line.include_in_special_margin:
                                total_with_margin_cup += line.price_subtotal
                            else:
                                total_without_margin_cup += line.price_subtotal

                        vals = {
                            'no_import': account_cup.x_studio_import_id.x_name,
                            'client': account_cup.partner_id.name,
                            'container_by_import': account_cup.x_studio_container_by_import if account_cup.x_studio_container_by_import or account_cup.x_studio_import_id.x_studio_certifies_receipt_load == '(B/L)' else '(AWB)',
                            'merchandise_value': round(merchandise_value, 2),
                            'currency_merchandise': currency_merchandise,
                            'account_date': account_usd.invoice_date,
                            'no_account_cup': account_cup.name,
                            'amount_total_cup': round(account_cup.amount_total_in_currency_signed, 2),
                            'no_account_usd': account_usd.name,
                            'amount_total_usd': round(account_usd.amount_total_in_currency_signed, 2),
                            'total_fruta': round(account_usd.amount_total_in_currency_signed / 2, 2),
                            'total_pyxel': round(account_usd.amount_total_in_currency_signed / 2, 2),
                            # Valores adicionales
                            'cup_total_with_margin': round(total_with_margin_cup, 2),
                            'cup_total_without_margin': round(total_without_margin_cup, 2),
                        }
                        result_records.append(vals)

        return result_records
