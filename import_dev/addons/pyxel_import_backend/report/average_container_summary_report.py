# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import logging
from odoo import tools
from odoo import api, fields, models
from odoo.http import request
from datetime import datetime, date


class AverageContainerSummaryReport(models.AbstractModel):
    _name = 'reports.pyxel_fruxelimport.container_summary_report_template'
    _description = 'Average Container Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        container_obj = self.env['x_container']
        docs = self._get_average_container_summary_report(docids, data)

        return {
            'doc_ids': docids,
            'doc_model': container_obj,
            'docs': docs,
            'start_date': data['start_date'],
            'end_date': data['end_date']
        }

    def _get_average_container_summary_report(self, docids, data=None):
        domain = []

        if docids:
            domain = [('id', 'in', docids)]

        if data.get('start_date') and data.get('end_date'):
            date_from = fields.Date.to_date(data['start_date'])
            date_to = fields.Date.to_date(data['end_date'])
            domain.append(('x_studio_arrival_date', '>=', date_from))
            domain.append(('x_studio_arrival_date', '<=', date_to))

        if data.get('partner_id'):
            domain.append(('x_studio_purchase_ids.x_studio_client', '=', data['partner_id']))

        if data.get('type_of_load'):
            domain.append(('x_studio_type_of_load', '=', data['type_of_load']))

        if data['purchase_condition']:
            domain.append(('x_studio_purchase_condition', '=', data['purchase_condition']))

        container_records = self.env['x_container'].search(domain)
        result_records = []


        PURCHASE_SELECTION = {
            '(B/L)': 'Importación marítima con contenedor lleno (FCL)',
            '(AWB)': 'Importación vía aérea (AWB)',
            '(DAP)': 'Compra en plaza (DAP)',
            '(GL)': 'Carga agrupada (LCL)'
        }

        for container in container_records:
            phones, emails = self._get_client_contacts(container)
            last_state = self.get_days_in_last_stage(container)

            vals = {
                'container': container.x_name,
                'import': container.x_studio_many2one_field_15t_1hjr52r0r.x_name,
                'x_studio_bill_of_landing': container.x_studio_bill_of_landing,
                'x_studio_customers': container.x_studio_customers,
                'x_studio_phones': phones,
                'x_studio_emails': emails,
                'x_studio_purchase_condition':  PURCHASE_SELECTION.get(container.x_studio_purchase_condition, 'Desconocido'),
                'x_studio_type_of_load': container.x_studio_type_of_load,
                'x_studio_total_import_lines': container.x_studio_total_import_lines,
                'x_studio_currency': container.x_studio_currency_id.name if container.x_studio_currency_id else '',
                'x_studio_arrival_date': container.x_studio_arrival_date,
                'x_studio_dm_date': container.x_studio_many2one_field_15t_1hjr52r0r.x_studio_dm_date,
                'x_studio_release_date': container.x_studio_release_date,
                'x_studio_date_prior_to_appointment': container.x_studio_date_prior_to_appointment,
                'x_studio_appointment_date': container.x_studio_appointment_date,
                'x_studio_extraction_date': container.x_studio_extraction_date,
                'x_studio_return_date': container.x_studio_return_date,
                'x_studio_state': last_state['last_stage'],
                'days_in_state': last_state['days'],
            }
            result_records.append(vals)

        return result_records


    def _get_client_contacts(self, container):
        phones, emails = set(), set()

        for line in container.x_studio_order_lines_by_container:
            client = line.x_studio_purchase_order_line.order_id.x_studio_client
            if client:
                phones.add(client.phone or '')
                emails.add(client.email or '')

        return ", ".join(phones) if phones else '', ", ".join(emails) if emails else ''

    def get_days_in_last_stage(self, container):
        """Devuelve los días transcurridos entre la última fecha definida y la anterior,
        o desde la última fecha hasta hoy si solo hay una fecha registrada."""

        dates = {
            'No liberado': container.x_studio_arrival_date,
            'Liberado por aduana': container.x_studio_many2one_field_15t_1hjr52r0r.x_studio_dm_date,
            'Liberado por el puerto': container.x_studio_release_date,
            'Contenedor con Pre-Cita': container.x_studio_date_prior_to_appointment,
            'Contenedor con Cita': container.x_studio_appointment_date,
            'Contenedor con fecha de Extracción': container.x_studio_extraction_date,
            'Contenedor con fecha de Retorno': container.x_studio_return_date,
        }

        # Filtrar fechas definidas y ordenarlas cronológicamente
        sorted_dates = sorted([(key, date) for key, date in dates.items() if date], key=lambda x: x[1])
        logging.info(f"sorted_dates: {sorted_dates}")

        if not sorted_dates:
            return {"last_stage": 'No ha arribado', "days": 0}

        if len(sorted_dates) == 1:
            # Solo hay una fecha: calcular días desde esa fecha hasta hoy
            last_stage, last_date = sorted_dates[0]
            today = fields.Date.today()
            days = (today - last_date).days
            return {"last_stage": last_stage, "days": days}

        # Hay al menos dos fechas: calcular días entre las dos últimas
        prev_stage, prev_date = sorted_dates[-2]
        last_stage, last_date = sorted_dates[-1]

        logging.info(f"last_stage: {last_stage}, last_date: {last_date}")

        if not last_date or not prev_date:
            return {"last_stage": last_stage, "days": 0}

        days = (last_date - prev_date).days
        return {"last_stage": last_stage, "days": days}
