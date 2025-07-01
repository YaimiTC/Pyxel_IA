# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
from odoo import api, fields, models


class AverageContainerReport(models.AbstractModel):
    _name = 'report.pyxel_fruxelimport.average_container_report_template'
    _description = 'Average Container Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        container_model = self.env['importation.load']
        docs = self._get_average_container_report(docids, data)

        return {
            'doc_ids': docids,
            'doc_model': container_model,
            'docs': docs,
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
        }

    def _get_average_container_report(self, docids, data=None):
        domain = []

        if docids:
            domain = [('id', 'in', docids)]

        if data.get('start_date') and data.get('end_date'):
            date_from = data['start_date'] if isinstance(data['start_date'], datetime.date) else datetime.datetime.strptime(data['start_date'], '%Y-%m-%d')
            date_to = data['end_date'] if isinstance(data['end_date'], datetime.date) else datetime.datetime.strptime(data['end_date'], '%Y-%m-%d')

            domain += [('arrival_date', '>=', date_from), ('arrival_date', '<=', date_to)]

        if data.get('partner_id'):
            domain += [('import_id.purchase_order_ids.partner_id', '=', data['partner_id'])]

        if data.get('type_of_load'):
            domain += [('type_of_load', '=', data['type_of_load'])]

        if data.get('purchase_condition'):
            domain += [('purchase_condition', '=', data['purchase_condition'])]

        STATE_SELECTION = {
            'to_extract': 'Por extraer',
            'to_arrive': 'Por arribar',
            'to_return': 'Por devolver',
            'returned': 'Devuelto',
        }

        PURCHASE_SELECTION = {
            'FCL': 'Importación marítima con contenedor lleno (FCL)',
            'AWB': 'Importación vía aérea (AWB)',
            'DAP': 'Compra en plaza (DAP)',
            'GL': 'Carga agrupada (LCL)',
        }

        containers = self.env['importation.load'].search(domain)
        result_records = []

        for container in containers:
            vals = {
                'container': container.name,
                'import': container.import_id.name if container.import_id else '',
                'bill_of_lading': container.importation_id.purchase_condition_number,
                'type_of_load': container.cargo_type,
                'total_import_lines': container.total_cargo_line,
                'currency': container.currency_id.name if container.currency_id else '',
                'state': STATE_SELECTION.get(container.state, 'Desconocido'),
                'days_to_arrival': self.calculate_difference(container.x_studio_arrival_date, container.x_studio_release_date),
                'days_to_extraction': self.calculate_difference(container.x_studio_release_date,
                                                        container.x_studio_extraction_date),
                'days_to_return': self.calculate_difference(container.x_studio_extraction_date,
                                                    container.x_studio_return_date),
                'purchase_condition': PURCHASE_SELECTION.get(container.purchase_condition, 'Desconocido'),
            }
            result_records.append(vals)

        return result_records

    def calculate_difference(self, date_start, date_end):
        if date_start and date_end:
            return (fields.Date.from_string(date_end) - fields.Date.from_string(date_start)).days
        return 0
