# -*- coding: utf-8 -*-
"""Portal del CLIENTE — documentos DE LA IMPORTACIÓN (nivel proceso).

El cliente sube/reemplaza los documentos de la importación de sus operaciones:
BL/AWB (obligatorio) + certificados (calidad, exportación, origen). El BL/AWB
suele emitirse tras el embarque, por eso necesita subirlo aquí cuando ya lo tenga.
Cada subida dispara la IA y pasa a revisión comercial; cuando BL/AWB + factura +
lista de cada OC están aprobados, la operación queda lista para el apoderado de aduana.
Espejo de /my/despacho (proveedor) pero a nivel proceso.
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


class PortalImportacion(CustomerPortal):

    # ----- helpers -----
    def _import_processes(self):
        company = request.env.user.partner_id.commercial_partner_id
        docs = request.env['pyxel.import.document'].sudo().search(
            [('purchase_order_id', '=', False),
             ('importation_id.customer_id.commercial_partner_id', '=', company.id)])
        return docs.mapped('importation_id').sorted(key=lambda p: p.id, reverse=True)

    def _get_user_doc(self, doc_id):
        doc = request.env['pyxel.import.document'].sudo().browse(int(doc_id))
        company = request.env.user.partner_id.commercial_partner_id
        if doc.exists() and not doc.purchase_order_id and doc.importation_id \
                and doc.importation_id.customer_id.commercial_partner_id == company:
            return doc
        return False

    def _importacion_count(self):
        return len(self._import_processes())

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        values['importacion_count'] = self._importacion_count()
        return values

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        values['importacion_count'] = self._importacion_count()
        return values

    # ----- páginas -----
    @http.route('/my/importacion', type='http', auth='user', website=True)
    def my_importacion(self, **kw):
        procs = self._import_processes()
        ImportDoc = request.env['pyxel.import.document'].sudo()
        bloques = []
        for proc in procs:
            docs = ImportDoc.search(
                [('importation_id', '=', proc.id), ('purchase_order_id', '=', False)],
                order='sequence, id')
            req = docs.filtered(lambda d: d.is_required)
            bloques.append({
                'proc': proc,
                'docs': docs,
                'c_total': len(req),
                'c_approved': len(req.filtered(lambda d: d.portal_state == 'approved')),
                'ready': proc.en_ready_for_customs if 'en_ready_for_customs' in proc._fields else False,
            })
        return request.render('pyxel_enetradex_website.portal_my_importacion', {
            'page_name': 'importacion', 'bloques': bloques,
        })

    @http.route('/my/importacion/download/<int:doc_id>', type='http', auth='user')
    def importacion_download(self, doc_id, **kw):
        doc = self._get_user_doc(doc_id)
        if not doc or not doc.attachment_id:
            return request.redirect('/my/importacion')
        att = doc.attachment_id
        return request.make_response(base64.b64decode(att.datas or b''), headers=[
            ('Content-Type', att.mimetype or 'application/octet-stream'),
            ('Content-Disposition', content_disposition(att.name or 'documento')),
        ])

    @http.route('/my/importacion/delete/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def importacion_delete(self, doc_id, **kw):
        doc = self._get_user_doc(doc_id)
        if doc and doc.portal_state not in ('in_review', 'approved'):
            if doc.attachment_id:
                doc.attachment_id.sudo().unlink()
            doc.sudo().write(dict(_RESET_VALS))
        return request.redirect('/my/importacion')

    @http.route('/my/importacion/upload/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True, csrf=False)
    def importacion_upload(self, doc_id, **kw):
        doc = self._get_user_doc(doc_id)
        f = kw.get('document')
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
                if doc.attachment_id:
                    doc.attachment_id.sudo().unlink()
                doc.sudo().write(dict(_RESET_VALS))
                doc.sudo().attach_images_as_pdf([base64.b64encode(data).decode()], f.filename)
        return request.redirect('/my/importacion')
