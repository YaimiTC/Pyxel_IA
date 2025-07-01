import base64
import os
import tempfile
from datetime import datetime
from io import BytesIO
import pytz
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import xlwt
import logging
_logger = logging.getLogger(__name__)


class AverageContainer(models.TransientModel):
    _name = 'average.container'
    _description = 'Average Container'

    start_date = fields.Date('Fecha de Inicio')
    end_date = fields.Date('Fecha Fin')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    purchase_condition = fields.Selection(
        selection=[
            ('(B/L)', 'Importación marítima con contenedor lleno (FCL)'),
            ('(AWB)', 'Importación vía aérea (AWB)'),
            ('(DAP)', 'Compra en plaza (DAP)'),
            ('(GL)', 'Carga agrupada (LCL)')],

        string='Condición de compra',
    )
    type_of_load = fields.Selection(
        selection=[
            ('refrigerated', 'Refrigerada'),
            ('dry', 'Seca'),
            ('grouped', 'Agrupada')],
        string='Tipo de Carga',
    )

    type_of_summary = fields.Selection(
        selection=[
            ('average_container', 'Reporte de Días en Tránsito de Contenedores'),
            ('average_container_summary', 'Reporte de Seguimiento de Contenedores')],
        string='Nombre del Reporte',  default='average_container')

    format_of_report = fields.Selection(
        selection=[
            ('PDF', 'PDF'),
            ('XLS', 'XLS')],
        string='Formato del reporte',

        default='PDF',
    )

    def action_get_report_average_container(self):
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'partner_id': self.partner_id.id,
            'type_of_load': self.type_of_load,
            'purchase_condition': self.purchase_condition,
            'type_of_summary': self.type_of_summary,
            'format_of_report': self.format_of_report
        }
        _logger.info("format_of_report!!!!!!: %s", self.format_of_report)
        if data['format_of_report'] == 'PDF':
            if data['type_of_summary'] == 'average_container_summary':
                return self.env.ref('pyxel_fruxelimport.report_average_container_summary').report_action(self, data=data)
            return self.env.ref('pyxel_fruxelimport.report_average_container').report_action(self, data=data)
        else:
            return self.action_generate_excel_report(data)

    def action_cancel(self):
        pass
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree',
            'target': 'new',
        }

    def action_generate_excel_report(self, data=None):
        """Genera el reporte en Excel y devuelve la URL de descarga."""
        _logger.info("action_generate_excel_report!!!!!!: %s", data)

        if self.type_of_summary == 'average_container':
            report_model = self.env['report.pyxel_fruxelimport.average_container_report_template']
            records = report_model._get_average_container_report([], data)
            columns = [
                ('No', 'index'),
                ('Contenedor', 'container'),
                ('Importación', 'import'),
                ('Bill of Landing', 'x_studio_bill_of_landing'),
                ('Tipo de Carga', 'x_studio_type_of_load'),
                ('Condición de compra', 'x_studio_purchase_condition'),
                ('Total', 'x_studio_total_import_lines'),
                ('Moneda', 'x_studio_currency'),
                ('Estado', 'x_studio_state'),
                ('Días por Arribar', 'days_to_arrival'),
                ('Días por Extraer', 'days_to_extraction'),
                ('Días por Devolver', 'days_to_return'),
            ]
        elif self.type_of_summary == 'average_container_summary':
            report_model = self.env['report.pyxel_fruxelimport.container_summary_report_template']
            records = report_model._get_average_container_summary_report([], data)
            columns = [
                ('No', 'index'),
                ('Contenedor', 'container'),
                ('Condición de compra', 'x_studio_purchase_condition'),
                ('No. condición de compra', 'x_studio_bill_of_landing'),
                ('Clientes', 'x_studio_customers'),
                ('Teléfonos', 'x_studio_phones'),
                ('Emails', 'x_studio_emails'),
                ('Fecha de Arribo', 'x_studio_arrival_date'),
                ('Fecha DM', 'x_studio_dm_date'),
                ('Fecha de Liberación', 'x_studio_release_date'),
                ('Fecha Cita Previa', 'x_studio_date_prior_to_appointment'),
                ('Fecha de Cita', 'x_studio_appointment_date'),
                ('Fecha de Extracción', 'x_studio_extraction_date'),
                ('Fecha de Retorno', 'x_studio_return_date'),
                ('Estado', 'x_studio_state'),
                ('Días en Estado', 'days_in_state'),
            ]
        else:
            raise UserError("Tipo de reporte no válido.")

        _logger.info("_get_report_data!!!!!!!!!!: %s", records)
        if not records:
            raise UserError("No hay datos disponibles para el rango seleccionado.")

        DATE_FIELDS = {
            'arrival_date',
            'dm_date',
            'release_date',
            'date_prior_to_appointment',
            'appointment_date',
            'extraction_date',
            'return_date',
        }
        # Crear archivo temporal
        fd_worked_time, path_worked_time = tempfile.mkstemp()
        with os.fdopen(fd_worked_time, 'w', newline='') as tmp:
            workbook = xlwt.Workbook(tmp, {'in_memory': True})
            sheet = workbook.add_sheet('Reporte Contenedores')

            # Definir estilos
            header_style = xlwt.easyxf("font: bold on; align: horiz center;")
            date_style = xlwt.easyxf("align: horiz center;")

            # Encabezado
            sheet.write(0, 0, "Reporte de Contenedores", header_style)
            sheet.write(1, 0, f"Desde: {data['start_date']} Hasta: {data['end_date']}", date_style)

            # Escribir encabezados en negrita
            style_bold = xlwt.easyxf('font: bold 1; align: horiz center; borders: bottom thin;')
            for col_num, (header, _) in enumerate(columns):
                sheet.write(3, col_num, header, style_bold)

            row = 3
            for row_num, record in enumerate(records, start=1):
                for col_num, (_, field_name) in enumerate(columns):
                    value = record.get(field_name, '')
                    # Si el campo está en la lista de fechas, lo formatea
                    if field_name in DATE_FIELDS:
                        value = self._format_date_xlsx(value)

                    if field_name == 'index':
                        sheet.write(row_num + row, col_num, row_num)  # Número de fila como índice
                    else:
                        sheet.write(row_num + row, col_num, value)

            # Guardar el archivo
            workbook.save(path_worked_time)

        # Leer el archivo y convertirlo a base64
        with open(path_worked_time, 'rb') as file:
            file_data = base64.b64encode(file.read())

        # Nombre del archivo
        file_name = f"{self.type_of_summary}_reporte_contenedores.xls"

        # Crear el adjunto
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'mimetype': 'application/vnd.ms-excel',
            'datas': base64.b64encode(open(path_worked_time, 'rb').read()),
            'res_model': 'res.user',
            'res_id': self.env.user.id,
        })
        _logger.info("Se generó el attachment: %s", attachment.name)

        # Devolver la URL de descarga
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def _format_date_xlsx(self, date_value):
        """ Formatea una fecha para el reporte en XLSX (DD-MM-YYYY) """
        if date_value:
            return datetime.strftime(date_value, '%d-%m-%Y')
        return ''