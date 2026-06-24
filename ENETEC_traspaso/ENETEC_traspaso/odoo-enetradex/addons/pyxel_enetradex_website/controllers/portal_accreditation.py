# -*- coding: utf-8 -*-
import base64
import json

from odoo import http, fields
from odoo.http import request, content_disposition
from odoo.addons.portal.controllers.portal import CustomerPortal

_RESET_VALS = {
    'attachment_id': False, 'upload_date': False,
    'ai_state': 'pending', 'ai_reason': False, 'ai_confidence': 0.0, 'ai_quality': 0.0,
    'ai_extracted_data': False,
    'lawyer_state': 'blocked', 'lawyer_reason': False, 'lawyer_notes': False,
    'commercial_state': 'blocked', 'commercial_reason': False,
}


class PortalAccreditation(CustomerPortal):

    def _get_accreditation_lead(self):
        company = request.env.user.partner_id.commercial_partner_id
        return request.env['crm.lead'].sudo().search(
            [('partner_id', '=', company.id), ('accreditation_document_ids', '!=', False)],
            order='create_date desc', limit=1)

    def _get_user_acc_doc(self, doc_id):
        doc = request.env['pyxel.lead.document'].sudo().browse(int(doc_id))
        company = request.env.user.partner_id.commercial_partner_id
        if doc.exists() and doc.lead_id.partner_id == company:
            return doc
        return False

    def _accreditation_count(self):
        company = request.env.user.partner_id.commercial_partner_id
        if company.contact_type_id.type_of_contact in ('Client', 'Supplier'):
            lead = self._get_accreditation_lead()
            return len(lead.accreditation_document_ids) if lead else 0
        return 0

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        values['accreditation_count'] = self._accreditation_count()
        return values

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        values['accreditation_count'] = self._accreditation_count()
        return values

    @http.route('/my/acreditacion', type='http', auth='user', website=True)
    def my_accreditation(self, **kw):
        lead = self._get_accreditation_lead()
        docs = lead.accreditation_document_ids if lead else request.env['pyxel.lead.document']
        req = docs.filtered(lambda d: d.is_required)
        values = {
            'page_name': 'accreditation', 'lead': lead, 'docs': docs,
            'c_total': len(req),
            'c_approved': len(req.filtered(lambda d: d.portal_state == 'approved')),
            'c_review': len(req.filtered(lambda d: d.portal_state in ('in_review', 'validating'))),
            'c_pending': len(req.filtered(lambda d: d.portal_state in ('pending', 'rejected'))),
        }
        return request.render('pyxel_enetradex_website.portal_my_accreditation', values)

    @http.route('/my/acreditacion/download/<int:doc_id>', type='http', auth='user')
    def acc_download(self, doc_id, **kw):
        doc = self._get_user_acc_doc(doc_id)
        if not doc or not doc.attachment_id:
            return request.redirect('/my/acreditacion')
        att = doc.attachment_id
        return request.make_response(base64.b64decode(att.datas or b''), headers=[
            ('Content-Type', att.mimetype or 'application/octet-stream'),
            ('Content-Disposition', content_disposition(att.name or 'documento')),
        ])

    @http.route('/my/acreditacion/delete/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def acc_delete(self, doc_id, **kw):
        doc = self._get_user_acc_doc(doc_id)
        if doc and doc.portal_state not in ('in_review', 'approved'):
            if doc.attachment_id:
                doc.attachment_id.sudo().unlink()
            doc.sudo().write(dict(_RESET_VALS))
        return request.redirect('/my/acreditacion')

    @http.route('/my/acreditacion/upload/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True, csrf=False)
    def acc_upload(self, doc_id, **kw):
        doc = self._get_user_acc_doc(doc_id)
        f = kw.get('document')
        if doc and doc.portal_state in ('pending', 'rejected', 'optional') \
                and f and (f.filename or '').lower().endswith('.pdf'):
            file_bytes = f.read()
            if doc.attachment_id:
                doc.attachment_id.sudo().unlink()
            att = request.env['ir.attachment'].sudo().create({
                'name': f.filename, 'datas': base64.b64encode(file_bytes),
                'res_model': 'res.partner', 'res_id': doc.lead_id.partner_id.id, 'type': 'binary',
            })
            vals = dict(_RESET_VALS)
            vals.update({'attachment_id': att.id, 'upload_date': fields.Datetime.now(),
                         'ai_state': 'validating'})
            doc.sudo().write(vals)
            doc.sudo()._run_ai()
        return request.redirect('/my/acreditacion')

    @http.route('/my/acreditacion/photo/<int:doc_id>', type='http', auth='user',
                methods=['POST'], csrf=False)
    def acc_photo(self, doc_id, **kw):
        """Recibe lista de imágenes base64, crea páginas y devuelve JSON."""
        doc = self._get_user_acc_doc(doc_id)
        if not doc or doc.portal_state not in ('pending', 'rejected', 'optional'):
            return request.make_response(
                json.dumps({'error': 'No autorizado'}),
                headers=[('Content-Type', 'application/json')])
        try:
            body = json.loads(request.httprequest.data)
            images_b64 = body.get('images', [])
            result = request.env['pyxel.lead.document.page'].sudo().create_from_b64(
                doc.id, images_b64)
        except Exception as e:
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')])
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')])

    @http.route('/my/acreditacion/assemble/<int:doc_id>', type='http', auth='user',
                methods=['POST'], csrf=False)
    def acc_assemble(self, doc_id, **kw):
        """Ensambla las páginas en PDF y lo asigna como attachment_id."""
        doc = self._get_user_acc_doc(doc_id)
        if not doc or doc.portal_state not in ('pending', 'rejected', 'optional'):
            return request.make_response(
                json.dumps({'error': 'No autorizado'}),
                headers=[('Content-Type', 'application/json')])
        try:
            body = json.loads(request.httprequest.data or b'{}')
            force = body.get('force', False)
            if doc.attachment_id:
                doc.attachment_id.sudo().unlink()
            att_id = request.env['pyxel.lead.document.page'].sudo().assemble_pdf(
                doc.id, force)
            doc.sudo().write({
                'upload_date': fields.Datetime.now(),
                'ai_state': 'validating',
                'lawyer_state': 'blocked',
                'commercial_state': 'blocked',
            })
        except Exception as e:
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')])
        return request.make_response(
            json.dumps({'ok': True, 'att_id': att_id}),
            headers=[('Content-Type', 'application/json')])
