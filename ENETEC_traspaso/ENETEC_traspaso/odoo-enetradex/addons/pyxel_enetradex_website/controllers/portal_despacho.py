# -*- coding: utf-8 -*-
"""Portal del PROVEEDOR — documentos de despacho por Orden de Compra.

El proveedor (vendor de la Orden de Compra) sube/reemplaza los documentos del
expediente de su OC (oferta, factura comercial, lista de empaque, DM, permisos).
Al subir se dispara la IA (pyxel.import.document.write -> _run_ai). Espejo del
portal de acreditación (/my/acreditacion) pero a nivel de Orden de Compra.
"""
import base64

from odoo import http, fields
from odoo.http import request, content_disposition
from odoo.addons.portal.controllers.portal import CustomerPortal

_IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif')

_RESET_VALS = {
    'attachment_id': False, 'upload_date': False,
    'ai_state': 'pending', 'ai_reason': False, 'ai_confidence': 0.0, 'ai_quality': 0.0,
    'ai_extracted_data': False,
    'commercial_state': 'blocked', 'commercial_reason': False,
}


class PortalDespacho(CustomerPortal):

    # ----- helpers -----
    def _despacho_orders(self):
        """Órdenes de compra del proveedor logueado que tienen expediente de docs."""
        company = request.env.user.partner_id.commercial_partner_id
        docs = request.env['pyxel.import.document'].sudo().search(
            [('purchase_order_id', '!=', False),
             ('purchase_order_id.partner_id.commercial_partner_id', '=', company.id)])
        return docs.mapped('purchase_order_id').sorted(key=lambda p: p.id, reverse=True)

    def _get_user_doc(self, doc_id):
        doc = request.env['pyxel.import.document'].sudo().browse(int(doc_id))
        company = request.env.user.partner_id.commercial_partner_id
        if doc.exists() and doc.purchase_order_id \
                and doc.purchase_order_id.partner_id.commercial_partner_id == company:
            return doc
        return False

    def _despacho_count(self):
        return len(self._despacho_orders())

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        values['despacho_count'] = self._despacho_count()
        return values

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        values['despacho_count'] = self._despacho_count()
        return values

    # ----- páginas -----
    @http.route('/my/despacho', type='http', auth='user', website=True)
    def my_despacho(self, **kw):
        orders = self._despacho_orders()
        ImportDoc = request.env['pyxel.import.document'].sudo()
        bloques = []
        for po in orders:
            # La DM la gestiona el apoderado de aduana, no el proveedor -> se oculta.
            docs = ImportDoc.search(
                [('purchase_order_id', '=', po.id), ('document_key', '!=', 'dm')],
                order='sequence, id')
            req = docs.filtered(lambda d: d.is_required)
            bloques.append({
                'po': po,
                'docs': docs,
                'c_total': len(req),
                'c_approved': len(req.filtered(lambda d: d.portal_state == 'approved')),
                'c_review': len(req.filtered(lambda d: d.portal_state in ('in_review', 'validating'))),
                'c_pending': len(req.filtered(lambda d: d.portal_state in ('pending', 'rejected'))),
            })
        return request.render('pyxel_enetradex_website.portal_my_despacho', {
            'page_name': 'despacho', 'bloques': bloques,
        })

    @http.route('/my/despacho/download/<int:doc_id>', type='http', auth='user')
    def despacho_download(self, doc_id, **kw):
        doc = self._get_user_doc(doc_id)
        if not doc or not doc.attachment_id:
            return request.redirect('/my/despacho')
        att = doc.attachment_id
        return request.make_response(base64.b64decode(att.datas or b''), headers=[
            ('Content-Type', att.mimetype or 'application/octet-stream'),
            ('Content-Disposition', content_disposition(att.name or 'documento')),
        ])

    @http.route('/my/despacho/delete/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def despacho_delete(self, doc_id, **kw):
        doc = self._get_user_doc(doc_id)
        if doc and doc.portal_state not in ('in_review', 'approved'):
            if doc.attachment_id:
                doc.attachment_id.sudo().unlink()
            doc.sudo().write(dict(_RESET_VALS))
        return request.redirect('/my/despacho')

    @http.route('/my/despacho/upload/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True, csrf=False)
    def despacho_upload(self, doc_id, **kw):
        doc = self._get_user_doc(doc_id)
        f = kw.get('document')
        if doc and doc.document_key == 'dm':
            return request.redirect('/my/despacho')  # la DM no la sube el proveedor
        if doc and doc.portal_state in ('pending', 'rejected', 'optional') and f and f.filename:
            name = f.filename.lower()
            data = f.read()
            if name.endswith('.pdf'):
                if doc.attachment_id:
                    doc.attachment_id.sudo().unlink()
                att = request.env['ir.attachment'].sudo().create({
                    'name': f.filename, 'datas': base64.b64encode(data),
                    'mimetype': 'application/pdf',
                    'res_model': 'pyxel.import.document', 'res_id': doc.id, 'type': 'binary',
                })
                vals = dict(_RESET_VALS)
                vals.update({'attachment_id': att.id, 'upload_date': fields.Datetime.now()})
                doc.sudo().write(vals)  # write() -> ai_state=validating + _run_ai()
            elif name.endswith(_IMG_EXT):
                # foto desde el móvil -> PDF + IA (reutiliza Fase 4)
                if doc.attachment_id:
                    doc.attachment_id.sudo().unlink()
                doc.sudo().write(dict(_RESET_VALS))
                doc.sudo().attach_images_as_pdf([base64.b64encode(data).decode()], f.filename)
        return request.redirect('/my/despacho')
