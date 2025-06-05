import base64
import os
import tempfile
import xlwt
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ImportErrorLog(models.Model):
    _name = 'import.error.log'
    _description = 'Log de Errores de Importación'

    name = fields.Char(string='Nombre del Archivo', required=True)
    import_date = fields.Datetime(string='Fecha de Importación', default=fields.Datetime.now())
    error_lines = fields.One2many('import.error.line', 'log_id', string='Líneas con Error')
    import_file = fields.Binary(string="Archivo de Importación")
    filename = fields.Char(string="Nombre del Archivo")

    def action_generate_error_report(self, data=None):
        """Genera el reporte en Excel de líneas con error y devuelve la URL de descarga."""
        _logger.info("action_generate_error_report!!!!!!: %s", data)

        # Definir los campos que deseas incluir en el reporte
        columns = [
            ('No', 'index'),
            ('BL', 'bl_number'),
            ('Contenedor', 'container_number'),
            ('Fecha de Arribo', 'arrival_date'),
            ('Fecha DM', 'dm_date'),
            ('Fecha de Liberación', 'release_date'),
            ('Fecha Cita Previa', 'date_prior_to_appointment'),
            ('Fecha de Cita', 'appointment_date'),
            ('Fecha de Extracción', 'extraction_date'),
            ('Fecha de Devolución', 'return_date'),
        ]

        # Obtener las líneas de error asociadas al log
        lines = self.env['import.error.line'].search([('log_id', '=', self.id)])

        if not lines:
            raise UserError("No hay líneas con error en este log.")

        # Crear archivo temporal
        fd_worked_time, path_worked_time = tempfile.mkstemp()
        with os.fdopen(fd_worked_time, 'w', newline='') as tmp:
            workbook = xlwt.Workbook(tmp, {'in_memory': True})
            sheet = workbook.add_sheet('Reporte de Errores')

            # Definir estilos
            header_style = xlwt.easyxf("font: bold on; align: horiz center;")
            date_style = xlwt.easyxf("align: horiz center;")

            # Encabezado
            sheet.write(0, 0, "Reporte de Líneas con Error", header_style)
            sheet.write(1, 0, f"Log de Errores: {self.name}", date_style)

            # Escribir encabezados en negrita
            style_bold = xlwt.easyxf('font: bold 1; align: horiz center; borders: bottom thin;')
            for col_num, (header, _) in enumerate(columns):
                sheet.write(3, col_num, header, style_bold)

            # Escribir los datos de las líneas de error
            row = 4
            for row_num, line in enumerate(lines, start=1):
                for col_num, (_, field_name) in enumerate(columns):
                    value = getattr(line, field_name, '')

                    # Validar si el valor es una fecha y formatearla
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d')  # Formatear fecha
                    elif not value:
                        value = ''  # Si no hay valor, asignar cadena vacía

                    # Si el campo es el índice, agregarlo como número de fila
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
        file_name = f"reporte_errores_{self.name}.xls"

        # Crear el adjunto
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'mimetype': 'application/vnd.ms-excel',
            'datas': file_data,
            'res_model': 'import.error.log',
            'res_id': self.id,
        })
        _logger.info("Se generó el attachment: %s", attachment.name)

        # Devolver la URL de descarga
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class ImportErrorLine(models.Model):
    _name = 'import.error.line'
    _description = 'Línea con Error en la Importación'

    log_id = fields.Many2one('import.error.log', string='Log de Errores')
    line_number = fields.Integer(string='Número de Línea')
    error_message = fields.Text(string='Mensaje de Error')
    data = fields.Text(string='Datos de la Línea')

    container_number = fields.Char(string='Número de Contenedor')
    bl_number = fields.Char(string='Número de BL')

    arrival_date = fields.Datetime(string='Fecha de Llegada')
    release_date = fields.Datetime(string='Fecha de Liberación')
    extraction_date = fields.Datetime(string='Fecha de Extracción')
    return_date = fields.Datetime(string='Fecha de Retorno')
    date_prior_to_appointment = fields.Datetime(string='Fecha de Pre-Cita')
    appointment_date = fields.Datetime(string='Fecha de Cita')
    dm_date = fields.Datetime(string='Fecha DM')
