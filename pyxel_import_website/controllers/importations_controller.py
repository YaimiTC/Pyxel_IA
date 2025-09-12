# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request, Response
from odoo.exceptions import ValidationError
from .base_controller import BaseController
import base64
import logging
import json
from odoo.addons.web.controllers import report

_logger = logging.getLogger(__name__)


class ImportationsController(BaseController):
    @http.route(['/model/imports'], type='http', auth='public', website=True)
    def importations_list(self, **kw):
        values = self._prepare_page_values('Imports')
        return request.render("pyxel_import_website.importations_list", values)

    @http.route(['/importations/view/<int:record_id>'], type='http', auth='user', website=True)
    def importation_view(self, record_id, **kw):
        record = request.env['importation.process'].sudo().browse(record_id)
        if not record.exists():
            return request.not_found()
        values = self._prepare_page_values('Import')
        values['record'] = record
        values['listing'] = {
            'name': 'Imports',
            'href': '/model/imports',
        }
        return request.render("pyxel_import_website.importation_view", values)

    @http.route(['/update_files/<int:record_id>'], type='http', auth='public', website=True)
    def update_files(self, record_id, **kwargs):
        # Recuperar el registro importation.process por su ID
        record = request.env['importation.process'].sudo().browse(record_id)

        # Renderizar la plantilla y pasar el registro
        return request.render('pyxel_import_website.update_files_template', {
            'record': record,
        })
    
    @http.route('/upload_pdf', type='http', auth='user', methods=['POST'], csrf=True)
    def upload_pdf(self, model, record_id, field_name, **kwargs):
        _logger.info(f"Esto entra en la ruta de upload pdf")
        file = request.httprequest.files.get('file')
        if not file or not file.filename.lower().endswith('.pdf'):
            return Response(json.dumps({'error': 'Solo se permiten archivos PDF.'}), content_type='application/json')

        record = request.env[model].sudo().browse(int(record_id))
        filename_field = f"{field_name}_filename"
        filename = file.filename or getattr(file, 'name', False)
        
        record.write({
            field_name: base64.b64encode(file.read()),
            filename_field: filename
            })

        return Response(json.dumps({'success': True}), content_type='application/json')
