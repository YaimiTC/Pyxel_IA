# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from .base_controller import BaseController
import base64
import logging
from odoo.addons.web.controllers import report

_logger = logging.getLogger(__name__)


class ImportationsController(BaseController):
    @http.route(['/model/imports'], type='http', auth='public', website=True)
    def importations_list(self, **kw):
        values = self._prepare_page_values('Imports')
        return request.render("pyxel_import_website.importations_list", values)

    @http.route(['/importation/view/<int:id>'], type='http', auth='user', website=True)
    def importation_view(self, **kw):
        values = self._prepare_page_values('Import')
        return request.render("pyxel_import_website.importation_view", values)

