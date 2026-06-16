import binascii
import logging
import base64

from datetime import datetime

from odoo import fields
from odoo import http, _
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.exceptions import AccessError, UserError, MissingError
from odoo.http import request, content_disposition

_logger = logging.getLogger(__name__)


class Portal(CustomerPortal):
    def _prepare_portal_layout_values(self):
        values = super(Portal, self)._prepare_portal_layout_values()
        user = request.env.user
        business_partner_id = user.commercial_partner_id.id
        contact_type = user.commercial_partner_id.contact_type_id
        is_internal_user = user.has_group('base.group_user')

        first_stage = request.env['importation.stage'].sudo().search([], order='sequence asc', limit=1)
        _logger.info(f"La primera etapa de CRM es: {first_stage.name} (ID: {first_stage.id})")

        # Inicializa contadores
        new_quotations_count = 0  # representa a los purchase.order
        new_orders_count = 0  # representa a los sale.order
        new_invoices_count = 0  # representa a los invoices
        new_importaciones_count = 0  # representa a las importaciones

        if is_internal_user:
            _logger.info("Usuario interno: se cuentan todos los documentos.")
            new_quotations_count = request.env['purchase.order'].sudo().search_count([('state', '=', 'draft')])
            new_orders_count = request.env['sale.order'].sudo().search_count([('state', '=', 'draft')])
            new_invoices_count = request.env['account.move'].sudo().search_count([
                ('state', '=', 'draft'),
                ('move_type', '=', 'out_invoice')
            ])
            new_importaciones_count = request.env['importation.process'].sudo().search_count([
                ('stage_id', '=', first_stage.id)
            ])

        elif contact_type.type_of_contact == 'Client':
            _logger.info("Usuario cliente: se cuentan solo ventas e importaciones como cliente.")
            new_orders_count = request.env['sale.order'].sudo().search_count([
                ('state', '=', 'draft'),
                ('partner_id', '=', business_partner_id)
            ])

            new_invoices_count = request.env['account.move'].sudo().search_count([
                ('state', '=', 'draft'),
                ('move_type', '=', 'out_invoice'),
                ('partner_id', '=', business_partner_id)
            ])
            new_importaciones_count = request.env['importation.process'].sudo().search_count([
                ('stage_id', '=', first_stage.id),
                ('customer_id', '=', business_partner_id)
            ])

        elif contact_type.type_of_contact == 'Supplier':
            _logger.info("Usuario proveedor: se cuentan solo compras e importaciones como proveedor.")
            new_quotations_count = request.env['purchase.order'].sudo().search_count([
                ('state', '=', 'draft'),
                ('partner_id', '=', business_partner_id)
            ])
            new_invoices_count = request.env['account.move'].sudo().search_count([
                ('state', '=', 'draft'),
                ('move_type', '=', 'out_invoice'),
                ('partner_id', '=', business_partner_id)
            ])
            new_importaciones_count = request.env['importation.process'].sudo().search_count([
                ('stage_id', '=', first_stage.id),
                ('provider_id', '=', business_partner_id)
            ])
            # Las órdenes de venta quedan en cero

        _logger.info(
            f"Contadores calculados: Quotations: {new_quotations_count}, Orders: {new_orders_count}, "
            f"Invoices: {new_invoices_count}, Imports: {new_importaciones_count}"
        )

        # === Estado del contrato ===
        contract_status = False
        days_in_process = 'False'

        if contact_type.type_of_contact in ['Client', 'Supplier']:
            lead = request.env['crm.lead'].sudo().search(
                [('partner_id', '=', business_partner_id)],
                order='create_date desc',
                limit=1
            )

            if lead:
                contract_status = lead.stage_id.name
                # if contact_type.type_of_contact == 'Client':
                #     is_accredited = request.env["res.partner.contract.import"].sudo().search([
                #         ("partner_id", "=", business_partner_id),
                #         ("active_contract", "=", True)
                #     ], limit=1)
                # elif contact_type.type_of_contact == 'Supplier':
                is_accredited = lead.partner_id.is_accredited

                if not is_accredited:
                    days_in_process = (datetime.now() - lead.create_date).days

        _logger.info(f"Estado del contrato: {contract_status}, Días en proceso: {days_in_process}")

        # Expediente de acreditación del cliente
        accreditation_count = 0
        if contact_type.type_of_contact in ['Client', 'Supplier']:
            lead_acc = request.env['crm.lead'].sudo().search(
                [('partner_id', '=', business_partner_id)],
                order='create_date desc', limit=1)
            if lead_acc:
                accreditation_count = lead_acc.accreditation_doc_count

        # Actualiza valores del portal
        values.update({
            'new_quotations_count': new_quotations_count,
            'new_orders_count': new_orders_count,
            'new_invoices_count': new_invoices_count,
            'new_importaciones_count': new_importaciones_count,
            'contract_status': contract_status,
            'days_in_process': days_in_process,
            'accreditation_count': accreditation_count,
        })

        return values

    # ------------------------------------------------------------------
    # Expediente de acreditación (portal del cliente)
    # ------------------------------------------------------------------
    def _get_accreditation_lead(self):
        partner = request.env.user.commercial_partner_id
        return request.env['crm.lead'].sudo().search(
            [('partner_id', '=', partner.id)],
            order='create_date desc', limit=1)

    def _get_user_doc(self, doc_id):
        """Devuelve el documento si pertenece al partner del usuario actual."""
        partner = request.env.user.commercial_partner_id
        doc = request.env['pyxel.lead.document'].sudo().browse(int(doc_id))
        if doc.exists() and doc.lead_id.partner_id.id == partner.id:
            return doc
        return False

    @http.route(['/my/acreditacion'], type='http', auth='user', website=True)
    def portal_my_accreditation(self, **kw):
        lead = self._get_accreditation_lead()
        documents = lead.accreditation_document_ids if lead else \
            request.env['pyxel.lead.document']
        values = {
            'lead': lead,
            'documents': documents.sudo(),
            'page_name': 'accreditation',
        }
        return request.render(
            'pyxel_import_website.portal_my_accreditation', values)

    @http.route(['/my/acreditacion/download/<int:doc_id>'],
                type='http', auth='user')
    def portal_accreditation_download(self, doc_id, **kw):
        doc = self._get_user_doc(doc_id)
        if not doc or not doc.attachment_id:
            return request.not_found()
        att = doc.attachment_id.sudo()
        content = base64.b64decode(att.datas or b'')
        return request.make_response(content, headers=[
            ('Content-Type', att.mimetype or 'application/octet-stream'),
            ('Content-Disposition', content_disposition(att.name or 'documento.pdf')),
            ('Content-Length', len(content)),
        ])

    @http.route(['/my/acreditacion/delete/<int:doc_id>'],
                type='http', auth='user', methods=['POST'], website=True)
    def portal_accreditation_delete(self, doc_id, **kw):
        doc = self._get_user_doc(doc_id)
        # Documento aprobado o en revisión = solo ver, no se puede tocar
        if doc and doc.portal_state not in ('in_review', 'approved'):
            if doc.attachment_id:
                doc.attachment_id.sudo().unlink()
            doc.sudo().write({
                'attachment_id': False,
                'upload_date': False,
                'ai_state': 'pending',
                'ai_reason': False,
                'ai_confidence': 0,
                'ai_quality': 0,
                'commercial_state': 'blocked',
                'commercial_reason': False,
            })
        return request.redirect('/my/acreditacion')

    @http.route(['/my/acreditacion/upload/<int:doc_id>'],
                type='http', auth='user', methods=['POST'],
                website=True, csrf=False)
    def portal_accreditation_upload(self, doc_id, **post):
        doc = self._get_user_doc(doc_id)
        ufile = post.get('document')
        # Solo se puede subir/resubir en estados editables por el cliente
        if doc and doc.portal_state in ('pending', 'rejected', 'optional') \
                and ufile and hasattr(ufile, 'read'):
            data = ufile.read()
            mimetype = ufile.mimetype or ''
            filename = ufile.filename or 'documento.pdf'
            # Solo se aceptan PDF
            if mimetype == 'application/pdf' or filename.lower().endswith('.pdf'):
                # Eliminar archivo anterior si lo hubiera
                if doc.attachment_id:
                    doc.attachment_id.sudo().unlink()
                att = request.env['ir.attachment'].sudo().create({
                    'name': doc.document_label or filename,
                    'datas': base64.b64encode(data),
                    'res_model': 'res.partner',
                    'res_id': doc.lead_id.partner_id.id,
                    'type': 'binary',
                    'mimetype': mimetype or 'application/pdf',
                })
                doc.sudo().write({
                    'attachment_id': att.id,
                    'upload_date': fields.Datetime.now(),
                    'ai_state': 'validating',
                    'ai_reason': False,
                    'commercial_state': 'blocked',
                    'commercial_reason': False,
                })
                # TODO: aquí se invocará al validador IA para fijar ai_state
                # (passed/doubt/rejected), ai_confidence y ai_quality.
        return request.redirect('/my/acreditacion')
