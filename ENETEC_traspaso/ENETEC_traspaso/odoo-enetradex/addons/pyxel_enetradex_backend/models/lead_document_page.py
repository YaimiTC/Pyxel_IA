# -*- coding: utf-8 -*-
import base64
import io
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_MIN_WIDTH = 400    # px mínimo para calidad aceptable
_MIN_HEIGHT = 300
_MAX_SIZE_MB = 10
_MIN_SCORE = 20.0   # % mínimo (1920x1080=100%, 1280x720=44%, 640x480=15%)


class LeadDocumentPage(models.Model):
    _name = 'pyxel.lead.document.page'
    _description = 'Página fotográfica del expediente de acreditación'
    _order = 'page_number'

    document_id = fields.Many2one('pyxel.lead.document', required=True, ondelete='cascade')
    page_number = fields.Integer(default=1)
    image = fields.Binary(string="Foto", required=True)
    image_filename = fields.Char()
    quality_score = fields.Float(string="Calidad (%)", default=0.0)
    quality_ok = fields.Boolean(string="Calidad aceptable", default=False)
    quality_reason = fields.Char(string="Observación")

    @api.model
    def create_from_b64(self, document_id, images_b64):
        """Crea páginas desde lista de base64, valida calidad de cada imagen.
        Devuelve {'pages': [...], 'rejected': [...]} con info de calidad."""
        doc = self.env['pyxel.lead.document'].browse(document_id)
        next_num = max((doc.page_ids.mapped('page_number') or [0])) + 1
        results = []
        rejected = []
        for b64 in images_b64:
            score, reason = self._check_quality(b64)
            ok = score >= _MIN_SCORE
            page = self.create({
                'document_id': document_id,
                'page_number': next_num,
                'image': b64,
                'quality_score': score,
                'quality_ok': ok,
                'quality_reason': reason,
            })
            entry = {'page_id': page.id, 'page_number': next_num,
                     'quality_score': score, 'quality_ok': ok, 'quality_reason': reason}
            if ok:
                results.append(entry)
            else:
                rejected.append(entry)
            next_num += 1
        return {'pages': results, 'rejected': rejected}

    def _check_quality(self, b64):
        """Valida dimensiones y tamaño de la imagen. Devuelve (score 0-100, razón)."""
        try:
            from PIL import Image as PILImage
            raw = base64.b64decode(b64)
            img = PILImage.open(io.BytesIO(raw))
            w, h = img.size
            size_mb = len(raw) / 1024 / 1024
            if size_mb > _MAX_SIZE_MB:
                return 0.0, _("Imagen demasiado grande (%.1f MB)") % size_mb
            if w < _MIN_WIDTH or h < _MIN_HEIGHT:
                return 30.0, _("Resolución baja (%dx%d px). Acércate más al documento.") % (w, h)
            # Score proporcional a resolución (normalizado a 1080p como 100%)
            score = min(100.0, (w * h) / (1920 * 1080) * 100)
            reason = _("Calidad correcta (%.0f%%)") % score if score >= _MIN_SCORE \
                else _("Resolución insuficiente (%dx%d px, min %dx%d)") % (w, h, _MIN_WIDTH, _MIN_HEIGHT)
            return round(score, 1), reason
        except Exception as e:
            _logger.warning("Error validando calidad de imagen: %s", e)
            return 50.0, _("No se pudo verificar la calidad")

    @api.model
    def assemble_pdf(self, document_id, force=False):
        """Une todas las páginas del documento en un PDF y lo sube como attachment_id.
        Si force=True incluye páginas rechazadas por calidad."""
        doc = self.env['pyxel.lead.document'].browse(document_id)
        pages = doc.page_ids.sorted('page_number')
        if not pages:
            raise ValidationError(_("No hay páginas para ensamblar."))
        if not force:
            bad = pages.filtered(lambda p: not p.quality_ok)
            if bad:
                nums = ', '.join(str(p.page_number) for p in bad)
                raise ValidationError(
                    _("Las páginas %s tienen calidad insuficiente. Retómalas o usa 'Generar PDF igualmente'.") % nums)
        try:
            from PIL import Image as PILImage
            imgs = []
            for page in pages:
                raw = base64.b64decode(page.image)
                imgs.append(PILImage.open(io.BytesIO(raw)).convert('RGB'))
            buf = io.BytesIO()
            imgs[0].save(buf, format='PDF', save_all=True, append_images=imgs[1:])
            pdf_b64 = base64.b64encode(buf.getvalue())
        except Exception as e:
            raise ValidationError(_("Error al generar el PDF: %s") % str(e))

        fname = doc.document_label + '.pdf'
        att = self.env['ir.attachment'].create({
            'name': fname,
            'datas': pdf_b64,
            'mimetype': 'application/pdf',
            'res_model': 'pyxel.lead.document',
            'res_id': doc.id,
        })
        doc.write({'attachment_id': att.id})
        # Eliminar páginas tras ensamblar
        pages.unlink()
        return att.id
