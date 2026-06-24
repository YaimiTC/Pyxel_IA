# -*- coding: utf-8 -*-
import base64
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Etiqueta de documento -> expected_type del DocValidator (endpoint /import/verify).
# Sin mapeo o si el servicio no responde -> el doc queda en 'validating' (no bloquea).
LABEL_TO_DOCVAL = {
    'Oferta firmada': 'commercial_offer',
    'Factura comercial': 'commercial_invoice',
    'Lista de empaque': 'packing_list',
    'Certificado de origen': 'certificate_of_origin',
    'BL / AWB': 'bill_of_lading',
    'Declaración de Mercancía (DM)': 'declaracion_mercancia',
}
VERDICT_MAP = {'apto': 'passed', 'revisar': 'doubt', 'no_apto': 'rejected'}

# Checklist manual por document_key: se usa cuando la IA no está disponible.
IMPORT_DEFAULT_CHECKS = {
    'bl_awb': [
        ('Número de BL / AWB visible', 'critico'),
        ('Nombre del buque o vuelo identificado', 'alto'),
        ('Fecha de embarque legible', 'alto'),
        ('Puerto/aeropuerto de origen y destino', 'critico'),
        ('Descripción de la mercancía coincide', 'critico'),
    ],
    'cert_calidad': [
        ('Emitido por entidad certificadora reconocida', 'critico'),
        ('Mercancía descrita claramente', 'alto'),
        ('Fecha de emisión válida', 'alto'),
        ('Firma y sello del emisor', 'alto'),
    ],
    'cert_exportacion': [
        ('Emitido por autoridad del país de origen', 'critico'),
        ('Mercancía y cantidad coincide con la OC', 'critico'),
        ('Fecha de emisión válida', 'alto'),
        ('Firma y sello oficial', 'alto'),
    ],
    'cert_origen': [
        ('Emitido por organismo competente (cámara u otro)', 'critico'),
        ('País de origen declarado claramente', 'critico'),
        ('Mercancía y cantidad coincide con la OC', 'critico'),
        ('Firma y sello oficial', 'alto'),
    ],
    'oferta': [
        ('Nombre del proveedor identificado', 'critico'),
        ('Descripción del producto clara', 'critico'),
        ('Precio unitario y total presentes', 'alto'),
        ('Condiciones de pago y entrega', 'medio'),
        ('Documento firmado por el proveedor', 'alto'),
    ],
    'factura_comercial': [
        ('Número de factura visible', 'critico'),
        ('Nombre comprador y vendedor correctos', 'critico'),
        ('Descripción y cantidad de mercancía', 'critico'),
        ('Precio total y moneda especificados', 'critico'),
        ('Fecha de emisión presente', 'alto'),
    ],
    'lista_empaque': [
        ('Número de bultos o contenedor', 'critico'),
        ('Peso bruto y neto declarados', 'alto'),
        ('Descripción de la mercancía', 'critico'),
        ('Marca o código del embalaje', 'medio'),
    ],
    'permisos_regulatorios': [
        ('Entidad regulatoria identificada', 'critico'),
        ('Mercancía o actividad autorizada clara', 'critico'),
        ('Documento vigente (no vencido)', 'alto'),
        ('Firma y sello del organismo', 'alto'),
    ],
    'dm': [
        ('Número de DM visible', 'critico'),
        ('Clasificación arancelaria declarada', 'critico'),
        ('Valor CIF declarado', 'critico'),
        ('Firma del apoderado de aduana', 'alto'),
        ('Contenedor o referencia de carga', 'medio'),
    ],
}

# Catalogo de documentos DE LA IMPORTACION (nivel proceso, purchase_order_id=False).
# Taxonomia del manual ODIN 2.0: el conocimiento de embarque + certificados. El BL/AWB
# es el disparador de "listo para aduana" (en_ready_for_customs).
IMPORT_DOCS = [
    ('bl_awb', 'BL / AWB', True),
    ('cert_calidad', 'Certificado de calidad', False),
    ('cert_exportacion', 'Certificado de exportación', False),
    ('cert_origen', 'Certificado de origen', False),
]
# Campos nativos del proceso (los sube el cliente en el wizard de solicitud) ->
# slot del expediente que pre-enlazan. (binary_field, filename_field)
NATIVE_FIELD_MAP = {
    'bl_awb': ('documentation_file', 'documentation_file_filename'),
    'cert_calidad': ('quality_certificate', 'quality_certificate_filename'),
    'cert_exportacion': ('export_certificate', 'export_certificate_filename'),
    'cert_origen': ('origin_certificate', 'origin_certificate_filename'),
}

# Catalogo de documentos por ORDEN DE COMPRA. Cada OC ligada al proceso genera su
# bloque. Oferta/factura/lista/permisos los sube el proveedor; la DM, el apoderado de aduana.
OC_DOCS = [
    ('oferta', 'Oferta firmada', True),
    ('factura_comercial', 'Factura comercial', True),
    ('lista_empaque', 'Lista de empaque', True),
    ('permisos_regulatorios', 'Permisos por entidades regulatorias', False),
    ('dm', 'Declaración de Mercancía (DM)', False),
]


class PyxelImportDocumentCheck(models.Model):
    _name = 'pyxel.import.document.check'
    _description = 'Punto de chequeo manual de documento de importación'
    _order = 'sequence, id'

    document_id = fields.Many2one('pyxel.import.document', ondelete='cascade', required=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Punto a validar", required=True)
    severity = fields.Selection([
        ('critico', 'Crítico'), ('alto', 'Alto'), ('medio', 'Medio'), ('bajo', 'Bajo'),
    ], string="Severidad")
    commercial_ok = fields.Boolean(string="Conforme")
    commercial_comment = fields.Char(string="Comentario")


class PyxelImportDocument(models.Model):
    _name = 'pyxel.import.document'
    _description = 'Documento del expediente de importación'
    _order = 'purchase_order_id, sequence, id'

    importation_id = fields.Many2one(
        'importation.process', required=True, ondelete='cascade', index=True)
    # Reservado para Fase 2 (documentos por Orden de Compra): por ahora siempre False.
    purchase_order_id = fields.Many2one('purchase.order', ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    document_key = fields.Char()
    document_label = fields.Char(required=True)
    is_required = fields.Boolean(default=True)
    attachment_id = fields.Many2one('ir.attachment')
    upload_date = fields.Datetime()
    page_ids = fields.One2many('pyxel.import.document.page', 'document_id', string="Páginas")
    document_file = fields.Binary(related='attachment_id.datas', readonly=True)
    document_filename = fields.Char(related='attachment_id.name', readonly=True)

    # PASO 1 — IA (automatico al subir/asignar el archivo)
    ai_state = fields.Selection([
        ('pending', 'Pendiente'), ('validating', 'Validando'),
        ('passed', 'Apto'), ('doubt', 'Dudoso'), ('rejected', 'Rechazado'),
        ('unavailable', 'IA no disponible'),
    ], default='pending', required=True, string="Dictamen IA")
    ai_confidence = fields.Float(string="Confianza IA (%)")
    ai_quality = fields.Float(string="Calidad de imagen (%)")
    ai_reason = fields.Text(string="Reporte de la IA")
    ai_extracted_data = fields.Text(string="Datos extraídos (OCR)")

    # PASO 2 — Comercial (manual)
    commercial_state = fields.Selection([
        ('blocked', 'No aplica'), ('to_review', 'En revisión'),
        ('approved', 'Aprobado'), ('rejected', 'Rechazado'),
    ], default='blocked', required=True, string="Revisión comercial")
    commercial_reason = fields.Text(string="Motivo de rechazo (lo ve el proveedor)")

    # Checklist manual (cuando la IA no está disponible)
    dm_confirmed = fields.Boolean(string="DM Confirmada", default=False)

    check_ids = fields.One2many('pyxel.import.document.check', 'document_id', string="Lista de validación")
    check_total = fields.Integer(compute='_compute_check_counts')
    check_ok_count = fields.Integer(compute='_compute_check_counts', string="Puntos conformes")

    @api.depends('check_ids.commercial_ok')
    def _compute_check_counts(self):
        for d in self:
            d.check_total = len(d.check_ids)
            d.check_ok_count = len(d.check_ids.filtered('commercial_ok'))

    # ESTADO COMBINADO (para listados y portal)
    portal_state = fields.Selection([
        ('pending', 'Pendiente'), ('validating', 'Validando'),
        ('rejected', 'Rechazado'), ('in_review', 'En revisión'),
        ('approved', 'Aprobado'), ('optional', 'Opcional'),
    ], compute='_compute_portal_state', store=True, string="Estado")
    portal_reason = fields.Text(compute='_compute_portal_state', store=True)

    @api.depends('attachment_id', 'is_required', 'ai_state', 'ai_reason',
                 'commercial_state', 'commercial_reason')
    def _compute_portal_state(self):
        for d in self:
            reason = False
            if not d.attachment_id and d.commercial_state != 'approved':
                state = 'pending' if d.is_required else 'optional'
            elif d.commercial_state == 'approved':
                state = 'approved'
            elif d.commercial_state == 'rejected':
                state = 'rejected'
                reason = d.commercial_reason
            elif d.ai_state == 'rejected':
                state = 'rejected'
                reason = d.ai_reason
            elif d.ai_state == 'validating':
                state = 'validating'
            else:
                # 'passed', 'doubt', 'unavailable' -> revisión manual activa
                state = 'in_review'
            d.portal_state = state
            d.portal_reason = reason

    # Al ASIGNAR/cambiar el archivo -> lanzar la IA. Al quedar Apto -> activar al comercial.
    def write(self, vals):
        run_ai_for = self.browse()
        if 'attachment_id' in vals and vals.get('attachment_id'):
            run_ai_for = self
            vals.setdefault('upload_date', fields.Datetime.now())
            vals.setdefault('ai_state', 'validating')
        res = super().write(vals)
        # Al subir archivo se habilita la revisión comercial (la IA es best-effort:
        # si DocValidator no dictamina, el comercial revisa manualmente igual).
        if 'attachment_id' in vals and vals.get('attachment_id'):
            for d in self:
                if d.commercial_state == 'blocked':
                    d.commercial_state = 'to_review'
            for d in run_ai_for:
                d._run_ai()
        if 'ai_state' in vals and vals['ai_state'] in ('passed', 'doubt', 'unavailable'):
            for d in self:
                if d.commercial_state == 'blocked':
                    d.commercial_state = 'to_review'
        return res

    def _run_ai(self):
        """Llama al DocValidator con el archivo actual y actualiza el dictamen IA."""
        self.ensure_one()
        if not self.attachment_id or not self.attachment_id.datas:
            return
        verdict = self._docvalidator_verify(
            self.attachment_id.datas.decode() if isinstance(self.attachment_id.datas, bytes)
            else self.attachment_id.datas, self.document_label)
        self.with_context(skip_ai=True).write(verdict)

    @api.model
    def _docvalidator_verify(self, file_b64, label):
        doc_type = LABEL_TO_DOCVAL.get(label or '')
        if not doc_type or not file_b64:
            return {'ai_state': 'unavailable'}
        icp = self.env['ir.config_parameter'].sudo()
        base = icp.get_param('docvalidator.url', 'http://host.docker.internal:8000')
        api_key = icp.get_param('docvalidator.api_key')
        headers = {'X-API-Key': api_key} if api_key else {}
        try:
            import requests
            r = requests.post(base.rstrip('/') + '/import/verify',
                              json={'doc_type': doc_type, 'file_b64': file_b64},
                              headers=headers, timeout=60)
            r.raise_for_status()
            d = r.json()
            inc = d.get('incumplimientos') or []
            reason = '; '.join(filter(None, (x.get('detail') or x.get('label') for x in inc)))
            return {
                'ai_state': VERDICT_MAP.get(d.get('verdict'), 'doubt'),
                'ai_confidence': float(d.get('score') or 0),
                'ai_quality': float(d.get('score') or 0),
                'ai_reason': reason or False,
                'ai_extracted_data': json.dumps(d.get('fields') or {}, ensure_ascii=False),
            }
        except Exception as e:  # noqa: BLE001
            _logger.warning("DocValidator no disponible: %s", e)
            return {'ai_state': 'unavailable'}

    def action_start_manual_review(self):
        """Pasa el doc a revisión manual: crea checklist por defecto y habilita al comercial."""
        for d in self:
            if not d.attachment_id:
                raise UserError(_("Sube el documento antes de iniciar la revisión."))
            d.with_context(skip_ai=True).write({'ai_state': 'unavailable'})
            if not d.check_ids:
                d._create_default_checks()
            if d.commercial_state == 'blocked':
                d.commercial_state = 'to_review'

    def _create_default_checks(self):
        self.ensure_one()
        Check = self.env['pyxel.import.document.check'].sudo()
        items = IMPORT_DEFAULT_CHECKS.get(self.document_key or '', [])
        if not items:
            items = [('Documento legible y completo', 'alto'),
                     ('Datos de la operación coinciden', 'critico'),
                     ('Firma o sello de autoridad presente', 'alto')]
        for i, (name, severity) in enumerate(items):
            Check.create({'document_id': self.id, 'sequence': (i + 1) * 10,
                          'name': name, 'severity': severity})

    def upload_pdf_b64(self, b64_data, filename=None):
        """Recibe un PDF en base64 desde el widget JS, valida y lo adjunta."""
        self.ensure_one()
        fname = filename or (self.document_label + '.pdf')
        if fname and not fname.lower().endswith('.pdf'):
            raise ValidationError(_("Solo se permiten archivos PDF."))
        raw = base64.b64decode(b64_data)
        if len(raw) > 6 * 1024 * 1024:
            raise ValidationError(
                _("El PDF no puede superar 6 MB (pesa %.1f MB).") % (len(raw) / 1024 / 1024))
        att = self.env['ir.attachment'].sudo().create({
            'name': fname,
            'datas': b64_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        self.write({'attachment_id': att.id})
        return att.id

    def attach_images_as_pdf(self, images_b64, filename=None):
        """Une imágenes (base64) en un PDF y lo adjunta; dispara la IA."""
        self.ensure_one()
        import io
        try:
            from PIL import Image
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas as rlcanvas
        except ImportError:
            raise UserError(_("Dependencias de imagen no disponibles en el servidor."))
        buf = io.BytesIO()
        c = rlcanvas.Canvas(buf, pagesize=A4)
        w, h = A4
        for b64img in images_b64:
            raw = base64.b64decode(b64img)
            img = Image.open(io.BytesIO(raw))
            iw, ih = img.size
            scale = min(w / iw, h / ih)
            nw, nh = iw * scale, ih * scale
            x, y = (w - nw) / 2, (h - nh) / 2
            img_buf = io.BytesIO()
            img.save(img_buf, format='PNG')
            img_buf.seek(0)
            from reportlab.lib.utils import ImageReader
            c.drawImage(ImageReader(img_buf), x, y, nw, nh)
            c.showPage()
        c.save()
        pdf_b64 = base64.b64encode(buf.getvalue()).decode()
        return self.upload_pdf_b64(pdf_b64, filename or (self.document_label + '.pdf'))

    # ----- Acciones COMERCIAL -----
    def action_commercial_approve(self):
        for d in self:
            if not d.attachment_id:
                raise UserError(_("Sube el documento antes de aprobarlo."))
            if d.ai_state == 'rejected':
                raise UserError(_("La IA rechazó el documento; corrígelo o reemplázalo antes de aprobar."))
            d.write({'commercial_state': 'approved', 'commercial_reason': False})
            if callable(getattr(d.importation_id, '_notify_expediente_complete', None)):
                d.importation_id._notify_expediente_complete()

    def action_commercial_reject(self):
        for d in self:
            if not (d.commercial_reason or '').strip():
                raise UserError(_("Indique el motivo de rechazo: el proveedor verá ese motivo."))
            d.write({'commercial_state': 'rejected'})

    def action_commercial_reopen(self):
        for d in self:
            if d.attachment_id:
                d.write({'commercial_state': 'to_review', 'commercial_reason': False})

    def action_rerun_ai(self):
        for d in self:
            d._run_ai()

    # ----- Captura por camara (foto -> PDF) -----
    def attach_images_as_pdf(self, images_b64, filename=None):
        """Une una o varias imagenes (base64) en un unico PDF y lo adjunta a este
        documento; al asignar el adjunto se dispara la IA (write -> _run_ai).
        Lo usa el widget de camara: el usuario fotografia el documento fisico."""
        self.ensure_one()
        import base64 as _b64
        import io
        from PIL import Image

        imgs = []
        for b in images_b64 or []:
            if not b:
                continue
            if isinstance(b, str) and b.startswith('data:') and ',' in b:
                b = b.split(',', 1)[1]
            try:
                im = Image.open(io.BytesIO(_b64.b64decode(b)))
                imgs.append(im.convert('RGB'))
            except Exception:  # noqa: BLE001
                raise UserError(_("No se pudo leer una de las imágenes (formato no soportado)."))
        if not imgs:
            raise UserError(_("No se recibió ninguna imagen."))

        buf = io.BytesIO()
        imgs[0].save(buf, format='PDF', save_all=True, append_images=imgs[1:])
        name = filename or ('%s.pdf' % (self.document_label or 'documento'))
        if not name.lower().endswith('.pdf'):
            name = name.rsplit('.', 1)[0] + '.pdf'
        att = self.env['ir.attachment'].create({
            'name': name,
            'datas': _b64.b64encode(buf.getvalue()),
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        })
        self.write({'attachment_id': att.id})  # -> dispara la IA
        return att.id

    # ----- Utilidades -----
    def action_view_document(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("Este documento no tiene archivo subido."))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=false' % self.attachment_id.id,
            'target': 'new',
        }

    def action_open_review(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pyxel.import.document',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('pyxel_enetradex_backend.view_pyxel_import_document_form').id, 'form')],
            'target': 'current',
        }

    # ----- Construccion del expediente -----
    @api.model
    def build_expediente(self, processes):
        """Crea los slots de documentos DE LA IMPORTACION (nivel proceso) si no existen.
        No duplica. Pre-enlaza adjuntos del wizard cuyo nombre coincida con la etiqueta."""
        for proc in processes:
            existing = self.search([
                ('importation_id', '=', proc.id), ('purchase_order_id', '=', False)])
            have = set(existing.mapped('document_key'))
            # adjuntos del wizard para intentar pre-enlazar
            shipment = proc.en_shipment_doc_ids if 'en_shipment_doc_ids' in proc._fields else self.env['ir.attachment']
            seq = 10
            for key, label, required in IMPORT_DOCS:
                if key in have:
                    seq += 10
                    continue
                vals = {
                    'importation_id': proc.id, 'sequence': seq,
                    'document_key': key, 'document_label': label, 'is_required': required,
                }
                # pre-enlace best-effort por coincidencia de nombre
                match = shipment.filtered(lambda a, l=label: l.lower().split()[0] in (a.name or '').lower())[:1]
                if match:
                    vals.update({'attachment_id': match.id, 'upload_date': fields.Datetime.now(),
                                 'ai_state': 'validating'})
                doc = self.create(vals)
                # pre-enlace desde los campos nativos del wizard (BL/AWB + certificados)
                nat = NATIVE_FIELD_MAP.get(key)
                if not doc.attachment_id and nat and nat[0] in proc._fields and proc[nat[0]]:
                    att = self.env['ir.attachment'].create({
                        'name': proc[nat[1]] or ('%s.pdf' % label),
                        'datas': proc[nat[0]], 'res_model': self._name,
                        'res_id': doc.id, 'type': 'binary',
                    })
                    doc.write({'attachment_id': att.id})  # dispara la IA
                elif doc.attachment_id:
                    doc._run_ai()
                seq += 10
        return True

    @api.model
    def build_oc_expediente(self, purchase_orders):
        """Crea el bloque de documentos de cada Orden de Compra ligada a un proceso.
        No duplica si la OC ya tiene su bloque."""
        for po in purchase_orders:
            if not po.importation_id:
                continue
            if self.search_count([('purchase_order_id', '=', po.id)]):
                continue
            seq = 10
            for key, label, required in OC_DOCS:
                self.create({
                    'importation_id': po.importation_id.id, 'purchase_order_id': po.id,
                    'document_key': key, 'document_label': label,
                    'is_required': required, 'sequence': seq,
                })
                seq += 10
        return True
