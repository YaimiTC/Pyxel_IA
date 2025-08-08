# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import logging
from odoo import tools
from odoo import api, fields, models
from odoo.http import request


class InvoiceConsolidatorLogisticReport(models.AbstractModel):
    _name = 'reports.pyxel_fruxelimport.invoice_logistics_template'
    _description = 'Invoice Consolidator Logistic Report'

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
            # date_from = datetime.strptime(data['start_date'], '%Y-%m-%d')
            # date_to = datetime.strptime(data['end_date'], '%Y-%m-%d')
            date_from = data['start_date']
            date_to = data['end_date']
            domain = [
                ('invoice_date', '<=', date_to), ('invoice_date', '>=', date_from),
                ('move_type', '=', 'out_invoice'), ('x_studio_type_import', '=', 'logistics service')]
        if data['contract_to_third'] in ('yes', 'no'):
            domain.append(('x_studio_contract_to_third', '=', True if data['contract_to_third'] == 'yes' else False))

        if data['partner_id']:
            invoice_partner = self.env['res.partner'].browse(data['partner_id'])
            domain.append(('invoice_partner_display_name', '=', invoice_partner.display_name))

        account_records = self.env['account.move'].search(domain)

        result_records = []
        for move_log in account_records:
            merchandise_value = 0
            currency_merchandise = ''

            container = move_log.x_studio_container_id
            for line in container.x_studio_order_lines_by_container:
                merchandise_value += line.x_studio_total
                currency_merchandise = line.x_studio_currency_id.name
            for cost_line in container.x_studio_container_cost_lines:
                merchandise_value += cost_line.x_studio_total

            vals = {
                'no_import': move_log.x_studio_import_id.x_name,
                'client': move_log.partner_id.name,
                'container_by_import': container.x_name,
                'container_state': container.x_studio_state,
                'container_extract': container.x_studio_extraction_date,
                'container_return': container.x_studio_return_date,
                'merchandise_value': round(merchandise_value, 2),
                'currency_merchandise': currency_merchandise,
                'account_date': move_log.invoice_date,
                'no_account': move_log.name,
                'amount_total': round(move_log.amount_total_in_currency_signed, 2),
                'currency_account': move_log.currency_id.name,
            }
            result_records.append(vals)

        return result_records
