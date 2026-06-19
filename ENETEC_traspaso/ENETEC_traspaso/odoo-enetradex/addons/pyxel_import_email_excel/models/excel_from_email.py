from odoo import models, fields, api
import base64
import xlrd
import logging

_logger = logging.getLogger(__name__)


class ExcelFromEmail(models.Model):
    _name = 'excel.from.email'
    _description = 'Email Excel Processor'

    subject = fields.Char(string='Asunto')
    body = fields.Text(string='Cuerpo')
    attachment = fields.Binary(string='Adjunto')
    attachment_filename = fields.Char(string='Nombre del Adjunto')

    @api.model
    def process_incoming_email(self, attachment):
        _logger.info("RECIBIDO EL ADJUNTO")
        # Extraer el archivo adjunto del diccionario
        filename = attachment.get('filename')
        content = attachment.get('content')

        if not filename or not content:
            _logger.info("No se encuentra un adjunto válido")
            return

        _logger.info("NOMBRE DEL ARCHIVO: %s", filename)
        _logger.info("CONTENIDO DEL ARCHIVO (BASE64): %s", content[:100])  # Mostrar solo los primeros 100 caracteres

        # Decodificar el contenido del adjunto
        try:
            file_content = base64.b64decode(content)
            _logger.info("CONTENIDO DECODIFICADO: %s", file_content[:100])  # Mostrar solo los primeros 100 caracteres
        except Exception as e:
            _logger.error("Error al decodificar el contenido del adjunto: %s", e)
            return

        if 'csv' in filename:
            # Procesar el archivo Excel utilizando la funcionalidad del wizard
            wizard = self.env['import.wizard'].create({
                'file': base64.b64encode(file_content),
                'filename': filename
            })
            _logger.info("ENVIADO EL ADJUNTO AL WIZARD")
            wizard.import_data_from_excel()
        else:
            _logger.info("No se encuentra un adjunto válido")
