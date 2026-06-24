# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request, Response
from odoo.exceptions import ValidationError
from .base_controller import BaseController
import werkzeug.exceptions
import base64
import logging
import json
from odoo.addons.web.controllers import report

_logger = logging.getLogger(__name__)


class ImportationsController(BaseController):
    @http.route(["/model/imports"], type="http", auth="public", website=True)
    def importations_list(self, **kw):
        values = self._prepare_page_values("Imports")
        return request.render("pyxel_import_website.importations_list", values)

    @http.route(
        ["/importations/view/<int:record_id>"], type="http", auth="user", website=True
    )
    def importation_view(self, record_id, **kw):
        record = request.env["importation.process"].sudo().browse(record_id)
        if not record.exists():
            return request.not_found()
        values = self._prepare_page_values("Import")
        values["record"] = record
        values["listing"] = {
            "name": "Importaciones",
            "href": "/model/imports",
        }

        current_stage = record.stage_id
        commercial_partner = request.env.user.commercial_partner_id
        contact_type = (
            commercial_partner.contact_type_id.type_of_contact
            if commercial_partner.contact_type_id.id
            else False
        )

        upload_file_link_label = (
            "Ver Información"
            if current_stage.cannot_upload or contact_type == "Client"
            else "Adicionar Información"
        )

        values["upload_file_link_label"] = upload_file_link_label

        # === Seguimiento: línea de tiempo unificada (acreditación + importación) ===
        # Incluye los eventos de la operación + la acreditación del cliente Y del
        # proveedor, porque el gate depende de que AMBAS partes estén acreditadas.
        customer = record.customer_id
        Event = request.env["en.tracking.event"].sudo()
        subdomains = [[("operation_id", "=", record.id)]]
        if customer:
            subdomains.append([("partner_id", "=", customer.id), ("phase", "=", "accreditation")])
        if record.provider_id:
            subdomains.append([("partner_id", "=", record.provider_id.id), ("phase", "=", "accreditation")])
        from odoo.osv import expression
        values["timeline"] = Event.search(expression.OR(subdomains), order="date asc")

        # Documentos de acreditación que entregó el cliente (en su partner).
        values["accred_docs"] = request.env["ir.attachment"].sudo().search([
            ("res_model", "=", "res.partner"),
            ("res_id", "=", customer.id if customer else False),
        ]) if customer else request.env["ir.attachment"]

        # Estado de acreditación de cada parte + acción requerida.
        cust_ok = bool(customer and customer.is_accredited)
        prov = record.provider_id
        prov_ok = bool(prov and prov.is_accredited)
        values["customer_accredited"] = cust_ok
        values["provider_accredited"] = prov_ok

        if not cust_ok:
            action = "Tu empresa está en proceso de acreditación. Te avisaremos en cuanto ENETRADEX valide tus documentos."
            action_kind = "warning"
        elif not prov_ok:
            action = "Tu empresa ya está acreditada. Falta acreditar a tu proveedor%s para poder iniciar la operación." % (
                " «%s»" % prov.name if prov else "")
            action_kind = "warning"
        elif current_stage.en_is_gate_stage:
            action = "Acreditación completa. Tu operación está lista para comenzar; un comercial la pondrá en marcha."
            action_kind = "success"
        else:
            action = "Tu operación está en curso. Etapa actual: %s." % (current_stage.name or "")
            action_kind = "info"
        values["action_required"] = action
        values["action_kind"] = action_kind

        return request.render("pyxel_import_website.importation_view", values)

    @http.route(
        ["/update_files/<int:record_id>"], type="http", auth="user", website=True
    )
    def update_files(self, record_id, **kwargs):
        # Recuperar el registro importation.process por su ID
        record = request.env["importation.process"].sudo().browse(record_id)
        if not record.exists():
            raise werkzeug.exceptions.NotFound()

        current_stage = record.stage_id
        commercial_partner = request.env.user.commercial_partner_id
        contact_type = (
            commercial_partner.contact_type_id.type_of_contact
            if commercial_partner.contact_type_id.id
            else False
        )
        _logger.info(f"Contact Type: {contact_type}")

        cannot_upload = (
            True if current_stage.cannot_upload or contact_type == "Client" else False
        )
        _logger.info("Can Not Upload %s", cannot_upload)

        if cannot_upload:
            if current_stage.cannot_upload:
                upload_disable_message = f"En la etapa '{current_stage.name}' de la importación no está permitida la carga de documentos."
            elif contact_type == "Client":
                upload_disable_message = (
                    "Tu tipo de usuario no tiene permitido subir documentos en esta sección."
                )
        else:
            upload_disable_message = ""

        # Renderizar la plantilla y pasar el registro
        return request.render(
            "pyxel_import_website.update_files",
            {
                "record": record,
                "cannot_upload": cannot_upload,
                "upload_disable_message": upload_disable_message,
            },
        )

    @http.route("/upload_pdf", type="http", auth="user", methods=["POST"], csrf=True)
    def upload_pdf(self, model, record_id, field_name, **kwargs):
        _logger.info(f"Esto entra en la ruta de upload pdf")
        file = request.httprequest.files.get("file")
        if not file or not file.filename.lower().endswith(".pdf"):
            return Response(
                json.dumps({"error": "Solo se permiten archivos PDF."}),
                content_type="application/json",
            )

        record = request.env[model].sudo().browse(int(record_id))
        filename_field = f"{field_name}_filename"
        filename = file.filename or getattr(file, "name", False)

        record.write(
            {field_name: base64.b64encode(file.read()), filename_field: filename}
        )

        return Response(json.dumps({"success": True}), content_type="application/json")
