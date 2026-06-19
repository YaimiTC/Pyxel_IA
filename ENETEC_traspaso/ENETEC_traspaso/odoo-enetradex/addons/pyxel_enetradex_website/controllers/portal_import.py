# -*- coding: utf-8 -*-
import base64
import json
import logging

from odoo import http, fields
from odoo.http import request, content_disposition
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


_IMPORT_DOC_RESET = {
    'attachment_id': False, 'upload_date': False,
    'source_type': 'file',
    'ai_state': 'pending', 'ai_reason': False,
    'ai_confidence': 0.0, 'ai_quality': 0.0,
    'ai_extracted_data': False,
    'commercial_state': 'blocked', 'commercial_reason': False,
}


class PortalImport(CustomerPortal):

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_provider_processes(self):
        """Procesos de importación en los que el usuario actúa como proveedor."""
        company = request.env.user.partner_id.commercial_partner_id
        return request.env['importation.process'].sudo().search(
            [('provider_id', '=', company.id),
             ('en_import_document_ids', '!=', False)],
            order='create_date desc')

    def _get_import_doc(self, doc_id):
        """Devuelve el documento si pertenece a un proceso del proveedor actual."""
        company = request.env.user.partner_id.commercial_partner_id
        doc = request.env['pyxel.import.document'].sudo().browse(int(doc_id))
        if doc.exists() and doc.importation_id.provider_id == company:
            return doc
        return False

    def _get_import_page(self, page_id):
        """Devuelve la página si el documento pertenece al proveedor actual."""
        company = request.env.user.partner_id.commercial_partner_id
        page = request.env['pyxel.import.document.page'].sudo().browse(int(page_id))
        if page.exists() and page.document_id.importation_id.provider_id == company:
            return page
        return False

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        procs = self._get_provider_processes()
        doc_count = sum(len(p.en_import_document_ids) for p in procs)
        values['import_doc_count'] = doc_count
        return values

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        procs = self._get_provider_processes()
        doc_count = sum(len(p.en_import_document_ids) for p in procs)
        values['import_doc_count'] = doc_count
        return values

    # ── Página principal del proveedor ────────────────────────────────────────

    @http.route('/my/despacho', type='http', auth='user', website=True)
    def my_despacho(self, process_id=None, **kw):
        procs = self._get_provider_processes()
        selected = None
        docs = request.env['pyxel.import.document'].sudo()
        if process_id:
            selected = procs.filtered(lambda p: p.id == int(process_id))
            selected = selected[0] if selected else None
        if not selected and procs:
            selected = procs[0]
        if selected:
            docs = selected.en_import_document_ids
        req = docs.filtered(lambda d: d.is_required)
        values = {
            'page_name': 'despacho',
            'processes': procs,
            'selected_process': selected,
            'docs': docs,
            'c_total':    len(req),
            'c_approved': len(req.filtered(lambda d: d.portal_state == 'approved')),
            'c_review':   len(req.filtered(lambda d: d.portal_state in ('in_review', 'validating'))),
            'c_pending':  len(req.filtered(lambda d: d.portal_state in ('pending', 'rejected'))),
        }
        return request.render('pyxel_enetradex_website.portal_my_despacho', values)

    # ── Descarga ──────────────────────────────────────────────────────────────

    @http.route('/my/despacho/download/<int:doc_id>', type='http', auth='user')
    def imp_download(self, doc_id, **kw):
        doc = self._get_import_doc(doc_id)
        if not doc or not doc.attachment_id:
            return request.redirect('/my/despacho')
        att = doc.attachment_id
        return request.make_response(
            base64.b64decode(att.datas or b''),
            headers=[
                ('Content-Type', att.mimetype or 'application/octet-stream'),
                ('Content-Disposition', content_disposition(att.name or 'documento')),
            ])

    # ── Subida de archivo PDF ─────────────────────────────────────────────────

    @http.route('/my/despacho/upload/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True, csrf=False)
    def imp_upload(self, doc_id, **kw):
        doc = self._get_import_doc(doc_id)
        f = kw.get('document')
        pid = doc.importation_id.id if doc else None
        if doc and doc.portal_state in ('pending', 'rejected', 'optional') \
                and f and getattr(f, 'filename', ''):
            if doc.attachment_id:
                doc.attachment_id.sudo().unlink()
            doc.page_ids.sudo().unlink()
            att = request.env['ir.attachment'].sudo().create({
                'name': f.filename,
                'datas': base64.b64encode(f.read()),
                'res_model': 'pyxel.import.document',
                'res_id': doc.id,
                'type': 'binary',
            })
            vals = dict(_IMPORT_DOC_RESET)
            vals.update({
                'attachment_id': att.id,
                'upload_date': fields.Datetime.now(),
                'source_type': 'file',
                'ai_state': 'validating',
            })
            doc.sudo().write(vals)
            # Llamar IA-DOCUMENTO (att.datas ya es base64, _call_docvalidator espera bytes)
            doc.sudo()._call_docvalidator(att.datas or b'')
        url = '/my/despacho?process_id=%s' % pid if pid else '/my/despacho'
        return request.redirect(url)

    # ── Eliminar documento ────────────────────────────────────────────────────

    @http.route('/my/despacho/delete/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def imp_delete(self, doc_id, **kw):
        doc = self._get_import_doc(doc_id)
        pid = doc.importation_id.id if doc else None
        if doc and doc.portal_state not in ('in_review', 'approved'):
            doc.sudo()._reset_document()
        url = '/my/despacho?process_id=%s' % pid if pid else '/my/despacho'
        return request.redirect(url)

    # ── Añadir página fotográfica (JSON) ─────────────────────────────────────

    @http.route('/my/despacho/page/add/<int:doc_id>', type='http', auth='user',
                methods=['POST'], csrf=False)
    def imp_page_add(self, doc_id, **kw):
        doc = self._get_import_doc(doc_id)
        if not doc or doc.portal_state not in ('pending', 'rejected', 'optional'):
            return request.make_response(
                json.dumps({'ok': False, 'reason': 'No permitido'}),
                headers=[('Content-Type', 'application/json')])

        img_file = kw.get('image') or request.httprequest.files.get('image')
        if not img_file:
            return request.make_response(
                json.dumps({'ok': False, 'reason': 'Sin imagen'}),
                headers=[('Content-Type', 'application/json')])

        img_data = base64.b64encode(img_file.read())
        existing = doc.page_ids.sorted('page_number')
        next_num = (existing[-1].page_number + 1) if existing else 1
        request.env['pyxel.import.document.page'].sudo().create({
            'document_id': doc.id,
            'page_number': next_num,
            'image': img_data,
            'image_filename': getattr(img_file, 'filename', 'page.jpg'),
        })
        # TODO [IA-CALIDAD]: validar calidad de la imagen y devolver error si baja
        total = len(doc.page_ids)
        return request.make_response(
            json.dumps({'ok': True, 'pages': total}),
            headers=[('Content-Type', 'application/json')])

    # ── Eliminar página ───────────────────────────────────────────────────────

    @http.route('/my/despacho/page/delete/<int:page_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def imp_page_delete(self, page_id, **kw):
        page = self._get_import_page(page_id)
        doc = page.document_id if page else None
        pid = doc.importation_id.id if doc else None
        if page and doc and doc.portal_state not in ('in_review', 'approved'):
            page.sudo().unlink()
        url = '/my/despacho?process_id=%s' % pid if pid else '/my/despacho'
        return request.redirect(url)

    # ── Finalizar — ensamblar páginas en PDF ──────────────────────────────────

    @http.route('/my/despacho/finalize/<int:doc_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def imp_finalize(self, doc_id, **kw):
        doc = self._get_import_doc(doc_id)
        pid = doc.importation_id.id if doc else None
        if doc and doc.page_ids and doc.portal_state not in ('in_review', 'approved'):
            try:
                doc.sudo().assemble_pdf_from_pages()
                # IA-DOCUMENTO se llama dentro de assemble_pdf_from_pages()
            except Exception as e:
                _logger.warning('Error al ensamblar PDF portal: %s', e)
        url = '/my/despacho?process_id=%s' % pid if pid else '/my/despacho'
        return request.redirect(url)
