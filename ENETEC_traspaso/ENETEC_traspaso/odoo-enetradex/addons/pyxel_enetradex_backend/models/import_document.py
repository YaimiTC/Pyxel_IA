# -*- coding: utf-8 -*-
import base64
import io
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Documentos propios del proceso de importación (uno por proceso).
IMPORT_DOC_CATALOG = [
    ('bl_awb',           'BL / AWB',                          True),
    ('cert_calidad',     'Certificado de calidad',             False),
    ('cert_exportacion', 'Certificado de exportación',         False),
    ('cert_origen',      'Certificado de origen',              False),
]

# Documentos por Orden de Compra (uno por OC vinculada al proceso).
OC_DOC_CATALOG = [
    ('oferta',               'Oferta firmada',                      True),
    ('factura_comercial',    'Factura comercial',                    True),
    ('lista_empaque',        'Lista de empaque',                     True),
    ('dm',                   'Declaración de Mercancía (DM)',        False),
    ('permisos_regulatorios','Permisos por entidades regulatorias',  False),
]

# doc_type que recibe DocValidator para cada clave de documento.
KEY_TO_DOCVAL = {
    'bl_awb':            'bill_of_lading',
    'cert_calidad':      'certificado_calidad',
    'cert_exportacion':  'certificado_exportacion',
    'cert_origen':       'certificado_origen',
    'oferta':            'oferta_firmada',
    'factura_comercial': 'factura_comercial',
    'lista_empaque':     'lista_empaque',
    'dm':                'declaracion_mercancia',
    'permisos_regulatorios': 'permisos_regulatorios',
}

VERDICT_MAP = {'apto': 'passed', 'revisar': 'doubt', 'no_apto': 'rejected'}


class PyxelImportDocument(models.Model):
    _name = 'pyxel.import.document'
    _description = 'Documento del expediente de importación'
    _order = 'purchase_order_id asc nulls first, sequence, id'
    _rec_name = 'document_label'

    importation_id = fields.Many2one(
        'importation.process', string='Proceso de importación',
        ondelete='cascade', index=True, required=True)
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Orden de compra',
        ondelete='cascade', index=True)
    section_type = fields.Selection([
        ('import', 'Importación'),
        ('oc',     'Orden de compra'),
    ], compute='_compute_section_type', store=True, string='Sección')
    # 'line_section' → fila cabecera (nombre de la OC); False → documento normal.
    display_type = fields.Selection([
        ('line_section', 'Sección'),
    ], default=False, string='Tipo de fila')

    @api.depends('purchase_order_id')
    def _compute_section_type(self):
        for d in self:
            d.section_type = 'oc' if d.purchase_order_id else 'import'

    sequence = fields.Integer(default=10)
    document_key = fields.Char(string='Clave', required=True)
    document_label = fields.Char(string='Documento', required=True)
    is_required = fields.Boolean(string='Obligatorio', default=True)

    attachment_id = fields.Many2one('ir.attachment', string='Archivo')
    upload_date = fields.Datetime(string='Fecha de subida')
    document_file = fields.Binary(related='attachment_id.datas', readonly=True)
    document_filename = fields.Char(related='attachment_id.name', readonly=True)

    # Origen y páginas fotográficas
    source_type = fields.Selection([
        ('file',   'Archivo subido'),
        ('camera', 'Foto / cámara'),
    ], default='file', string='Origen')
    page_ids = fields.One2many('pyxel.import.document.page', 'document_id', string='Páginas')
    page_count = fields.Integer(compute='_compute_page_count', string='N.º páginas')

    # Campo de subida manual (backend/portal): al guardar crea/reemplaza el attachment
    # y resetea los estados para que la IA lo vuelva a validar.
    document_upload = fields.Binary(string='Subir archivo', store=False, attachment=False)
    document_upload_filename = fields.Char(string='Nombre de archivo', store=False)

    @api.depends('page_ids')
    def _compute_page_count(self):
        for d in self:
            d.page_count = len(d.page_ids)

    # ── PASO 1: IA ────────────────────────────────────────────────────────────
    ai_state = fields.Selection([
        ('pending',    'Pendiente'),
        ('validating', 'Validando'),
        ('passed',     'Apto'),
        ('doubt',      'Dudoso'),
        ('rejected',   'Rechazado'),
    ], default='pending', required=True, string='Dictamen IA')
    ai_confidence = fields.Float(string='Confianza IA (%)')
    ai_quality = fields.Float(string='Calidad de imagen (%)')
    ai_reason = fields.Text(string='Reporte de la IA')
    ai_extracted_data = fields.Text(string='Datos extraídos (OCR)')
    ai_findings = fields.Text(string='Hallazgos IA (JSON)')

    # ── Datos de la DM (solo cuando document_key == 'dm') ────────────────────
    dm_number = fields.Char(string='Número DM')
    dm_container_number = fields.Char(string='Contenedor (DM)')
    dm_cif_value = fields.Float(string='Valor CIF (USD)', digits=(16, 2))
    dm_arancel_total = fields.Float(string='Total aranceles (USD)', digits=(16, 2))
    dm_impuesto_circulacion = fields.Float(string='Impuesto circulación (USD)', digits=(16, 2))
    dm_arancel_notes = fields.Text(string='Notas arancelarias')
    dm_extraction_state = fields.Selection([
        ('pending',    'Sin DM'),
        ('extracted',  'Extraído por IA'),
        ('manual',     'Datos manuales'),
    ], default='pending', string='Estado extracción')
    dm_confirmed = fields.Boolean(string='Datos confirmados', default=False)

    def action_confirm_dm(self):
        """Apoderado confirma los datos de la DM (manual o revisados tras extracción IA)."""
        for d in self:
            d.dm_confirmed = True
            if d.dm_extraction_state == 'pending':
                d.dm_extraction_state = 'manual'

    # ── PASO 2: Comercial ─────────────────────────────────────────────────────
    commercial_state = fields.Selection([
        ('blocked',   'No aplica'),
        ('to_review', 'En revisión'),
        ('approved',  'Aprobado'),
        ('rejected',  'Rechazado'),
    ], default='blocked', required=True, string='Revisión comercial')
    commercial_reason = fields.Text(
        string='Motivo de rechazo (lo ve el proveedor)')

    # ── ESTADO COMBINADO (portal) ──────────────────────────────────────────────
    portal_state = fields.Selection([
        ('pending',    'Pendiente'),
        ('validating', 'Validando'),
        ('rejected',   'Rechazado'),
        ('in_review',  'En revisión'),
        ('approved',   'Aprobado'),
        ('optional',   'Opcional'),
    ], compute='_compute_portal_state', store=True, string='Estado (proveedor)')
    portal_reason = fields.Text(compute='_compute_portal_state', store=True)

    @api.depends('attachment_id', 'is_required',
                 'ai_state', 'ai_reason',
                 'commercial_state', 'commercial_reason')
    def _compute_portal_state(self):
        for d in self:
            reason = False
            if not d.attachment_id and d.commercial_state != 'approved':
                state = 'pending' if d.is_required else 'optional'
            elif d.ai_state == 'validating':
                state = 'validating'
            elif d.ai_state == 'rejected':
                state = 'rejected'
                reason = d.ai_reason
            elif d.ai_state in ('passed', 'doubt'):
                if d.commercial_state == 'approved':
                    state = 'approved'
                elif d.commercial_state == 'rejected':
                    state = 'rejected'
                    reason = d.commercial_reason
                else:
                    state = 'in_review'
            else:
                state = 'pending' if d.is_required else 'optional'
            d.portal_state = state
            d.portal_reason = reason

    # ── Llamada al DocValidator ───────────────────────────────────────────────
    def _call_docvalidator(self, file_b64):
        """Llama al DocValidator y aplica el resultado sobre self (ensure_one ya hecho)."""
        result = self._docvalidator_verify(
            file_b64.decode() if isinstance(file_b64, bytes) else file_b64,
            self.document_key)
        super(PyxelImportDocument, self).write(result)
        # Desbloquear comercial si la IA aprobó
        if result.get('ai_state') in ('passed', 'doubt') \
                and self.commercial_state == 'blocked':
            super(PyxelImportDocument, self).write({'commercial_state': 'to_review'})
        # Si es DM, extraer campos automáticamente del JSON de la IA
        if self.document_key == 'dm' and result.get('ai_extracted_data'):
            self._extract_dm_fields(result['ai_extracted_data'])

    def _extract_dm_fields(self, extracted_json):
        """Parsea el JSON de extracción de la IA y puebla los campos DM."""
        try:
            data = json.loads(extracted_json) if isinstance(extracted_json, str) else extracted_json
        except Exception:
            return
        vals = {}
        if data.get('numero_dm') or data.get('dm_number'):
            vals['dm_number'] = data.get('numero_dm') or data.get('dm_number')
        if data.get('contenedor') or data.get('container'):
            vals['dm_container_number'] = data.get('contenedor') or data.get('container')
        if data.get('valor_cif') or data.get('cif_value'):
            vals['dm_cif_value'] = float(data.get('valor_cif') or data.get('cif_value') or 0)
        if data.get('total_aranceles') or data.get('arancel_total'):
            vals['dm_arancel_total'] = float(data.get('total_aranceles') or data.get('arancel_total') or 0)
        if data.get('impuesto_circulacion'):
            vals['dm_impuesto_circulacion'] = float(data.get('impuesto_circulacion') or 0)
        if vals:
            vals['dm_extraction_state'] = 'extracted'
            super(PyxelImportDocument, self).write(vals)

    # ── Desbloqueo secuencial: IA apta → activa revisión comercial ────────────
    def write(self, vals):
        # Subida de archivo (widget binary): crea/reemplaza attachment y llama IA
        file_data = vals.pop('document_upload', None)
        file_name = vals.pop('document_upload_filename', None)
        if file_data:
            for d in self:
                fname = file_name or (d.document_label + '.pdf')
                if d.attachment_id:
                    d.attachment_id.sudo().write({'datas': file_data, 'name': fname})
                    att = d.attachment_id
                else:
                    att = self.env['ir.attachment'].sudo().create({
                        'name': fname, 'datas': file_data,
                        'res_model': 'pyxel.import.document',
                        'res_id': d.id, 'type': 'binary',
                    })
                super(PyxelImportDocument, d).write({
                    'attachment_id': att.id,
                    'upload_date': fields.Datetime.now(),
                    'ai_state': 'validating',
                    'ai_confidence': 0.0, 'ai_quality': 0.0,
                    'ai_reason': False, 'ai_extracted_data': False,
                    'commercial_state': 'blocked',
                })
                d._call_docvalidator(file_data)
        res = super().write(vals)
        if vals.get('ai_state') in ('passed', 'doubt'):
            for d in self:
                if d.commercial_state == 'blocked':
                    super(PyxelImportDocument, d).write(
                        {'commercial_state': 'to_review'})
        return res

    # ── Acciones COMERCIAL ────────────────────────────────────────────────────
    def action_commercial_approve(self):
        for d in self:
            if d.ai_state not in ('passed', 'doubt'):
                raise UserError(
                    _('La IA aún no entregó un dictamen revisable para este documento.'))
            d.write({'commercial_state': 'approved', 'commercial_reason': False})
            d.importation_id._check_import_expediente_complete()

    def action_commercial_reject(self):
        for d in self:
            if d.ai_state not in ('passed', 'doubt'):
                raise UserError(
                    _('La IA aún no entregó un dictamen revisable para este documento.'))
            if not (d.commercial_reason or '').strip():
                raise UserError(
                    _('Indique el motivo de rechazo: el proveedor verá ese motivo.'))
            d.write({'commercial_state': 'rejected'})

    def action_commercial_reopen(self):
        for d in self:
            if d.ai_state in ('passed', 'doubt'):
                d.write({'commercial_state': 'to_review'})

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

    # ── Ver documento ─────────────────────────────────────────────────────────
    def action_view_document(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_('Este documento no tiene archivo subido.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=false' % self.attachment_id.id,
            'target': 'new',
        }

    # ── Ensamblar PDF desde páginas fotográficas ───────────────────────────────
    def assemble_pdf_from_pages(self):
        """Combina las page_ids (imágenes) en un único PDF y lo asigna como attachment."""
        self.ensure_one()
        pages = self.page_ids.sorted('page_number')
        if not pages:
            raise UserError(_('No hay páginas fotográficas para ensamblar.'))
        try:
            from PIL import Image
        except ImportError:
            raise UserError(_('Pillow no está disponible en el servidor.'))

        images = []
        for page in pages:
            if not page.image:
                continue
            img = Image.open(io.BytesIO(base64.b64decode(page.image)))
            images.append(img.convert('RGB'))

        if not images:
            raise UserError(_('Las páginas no contienen imágenes válidas.'))

        buf = io.BytesIO()
        images[0].save(buf, format='PDF', save_all=True,
                       append_images=images[1:], resolution=150)
        pdf_b64 = base64.b64encode(buf.getvalue())
        fname = (self.document_label or 'documento') + '.pdf'

        if self.attachment_id:
            self.attachment_id.sudo().unlink()

        att = self.env['ir.attachment'].sudo().create({
            'name': fname,
            'datas': pdf_b64,
            'res_model': 'pyxel.import.document',
            'res_id': self.id,
            'type': 'binary',
        })
        reset = {
            'attachment_id': att.id,
            'upload_date': fields.Datetime.now(),
            'source_type': 'camera',
            'ai_state': 'validating',
            'ai_confidence': 0.0, 'ai_quality': 0.0,
            'ai_reason': False, 'ai_extracted_data': False,
            'commercial_state': 'blocked',
        }
        super(PyxelImportDocument, self).write(reset)
        self._call_docvalidator(pdf_b64)

    # ── Validación IA ─────────────────────────────────────────────────────────
    @api.model
    def _docvalidator_verify(self, file_b64, document_key):
        doc_type = KEY_TO_DOCVAL.get(document_key or '')
        if not doc_type or not file_b64:
            return {'ai_state': 'validating'}
        base = self.env['ir.config_parameter'].sudo().get_param(
            'docvalidator.url', 'http://host.docker.internal:8000')
        try:
            import requests
            r = requests.post(
                base.rstrip('/') + '/verify',
                json={'file_b64': file_b64, 'expected_type': doc_type},
                timeout=60)
            r.raise_for_status()
            d = r.json()
            verdict = d.get('verdict') or d.get('result') or 'revisar'
            reason = d.get('reason') or d.get('ai_reason') or False
            return {
                'ai_state':          VERDICT_MAP.get(verdict, 'doubt'),
                'ai_confidence':     float(d.get('confidence') or d.get('score') or 0),
                'ai_quality':        float(d.get('quality') or d.get('score') or 0),
                'ai_reason':         reason,
                'ai_extracted_data': json.dumps(
                    d.get('extracted_fields') or d.get('fields') or {},
                    ensure_ascii=False),
            }
        except Exception as e:
            _logger.warning('DocValidator no disponible para import doc: %s', e)
            return {'ai_state': 'validating'}

    def trigger_ai_validation(self):
        """Llama al DocValidator para este documento. Se invoca al subir el archivo."""
        self.ensure_one()
        if not self.attachment_id:
            return
        file_b64 = self.attachment_id.datas
        if not file_b64:
            return
        self.write({'ai_state': 'validating'})
        result = self._docvalidator_verify(
            file_b64.decode() if isinstance(file_b64, bytes) else file_b64,
            self.document_key)
        self.write(result)

    def action_assemble_from_images(self, images_b64):
        """RPC: recibe lista de archivos en base64 (imágenes o PDFs) y los combina
        en un único PDF. PDFs se fusionan con pypdf; imágenes se convierten con Pillow."""
        self.ensure_one()
        if not images_b64:
            raise UserError(_('No se recibieron archivos.'))

        from PIL import Image as PILImage
        from PyPDF2 import PdfFileMerger, PdfFileReader

        merger = PdfFileMerger()
        any_page = False
        pdf_bufs = []  # mantener referencias vivas

        for i, b64 in enumerate(images_b64):
            try:
                raw = base64.b64decode(b64 if isinstance(b64, str) else b64.decode())
            except Exception as e:
                _logger.warning('No se pudo decodificar base64 item %d: %s', i + 1, e)
                continue

            if raw[:4] == b'%PDF':
                buf = io.BytesIO(raw)
                pdf_bufs.append(buf)
                merger.append(PdfFileReader(buf))
                any_page = True
            else:
                try:
                    img = PILImage.open(io.BytesIO(raw)).convert('RGB')
                    img_buf = io.BytesIO()
                    img.save(img_buf, format='PDF', resolution=150)
                    img_buf.seek(0)
                    pdf_bufs.append(img_buf)
                    merger.append(PdfFileReader(img_buf))
                    any_page = True
                except Exception as e:
                    _logger.warning('Imagen %d no pudo procesarse: %s', i + 1, e)

        if not any_page:
            raise UserError(_('Ningún archivo pudo procesarse. Asegúrate de subir PDF, JPG o PNG.'))

        out = io.BytesIO()
        merger.write(out)
        pdf_b64 = base64.b64encode(out.getvalue())
        fname = (self.document_label or 'documento') + '.pdf'
        is_camera = not any(
            base64.b64decode(b)[:4] == b'%PDF' for b in images_b64 if b
        )

        if self.attachment_id:
            self.attachment_id.sudo().unlink()
        self.page_ids.sudo().unlink()

        att = self.env['ir.attachment'].sudo().create({
            'name': fname, 'datas': pdf_b64,
            'res_model': 'pyxel.import.document',
            'res_id': self.id, 'type': 'binary',
        })
        super(PyxelImportDocument, self).write({
            'attachment_id': att.id,
            'upload_date': fields.Datetime.now(),
            'source_type': 'camera' if is_camera else 'file',
            'ai_state': 'validating',
            'ai_confidence': 0.0, 'ai_quality': 0.0,
            'ai_reason': False, 'ai_extracted_data': False,
            'commercial_state': 'blocked',
        })
        self._call_docvalidator(pdf_b64)
        return True

    def _reset_document(self):
        """Borra archivo, páginas y resetea todos los estados."""
        if self.attachment_id:
            self.attachment_id.sudo().unlink()
        self.page_ids.sudo().unlink()
        super(PyxelImportDocument, self).write({
            'attachment_id': False, 'upload_date': False,
            'source_type': 'file', 'ai_state': 'pending',
            'ai_confidence': 0.0, 'ai_quality': 0.0,
            'ai_reason': False, 'ai_extracted_data': False,
            'commercial_state': 'blocked', 'commercial_reason': False,
        })

    # ── Construcción del expediente ───────────────────────────────────────────
    @api.model
    def build_expediente(self, importation):
        """Crea los slots de documentos del PROCESO DE IMPORTACIÓN (BL, certificados).
        Un set por proceso; no incluye documentos de OC.
        """
        docs = self.browse()
        for proc in importation:
            existing_keys = proc.en_import_document_ids.filtered(
                lambda d: not d.purchase_order_id).mapped('document_key')
            for seq, (key, label, required) in enumerate(IMPORT_DOC_CATALOG, start=1):
                if key in existing_keys:
                    continue
                docs |= self.create({
                    'importation_id': proc.id,
                    'sequence':       seq * 10,
                    'document_key':   key,
                    'document_label': label,
                    'is_required':    required,
                })
        return docs

    @api.model
    def build_oc_expediente(self, purchase_orders):
        """Crea los slots de documentos por cada Orden de Compra vinculada al proceso.
        Inserta una fila separadora (display_type=line_section) con el nombre de la OC
        antes de sus documentos. No duplica si la OC ya tiene slots.
        """
        docs = self.browse()
        for po in purchase_orders:
            if not po.importation_id:
                continue
            existing = self.search([
                ('importation_id', '=', po.importation_id.id),
                ('purchase_order_id', '=', po.id),
            ])
            if existing:
                continue
            # Fila cabecera con el nombre de la OC
            docs |= self.create({
                'importation_id':    po.importation_id.id,
                'purchase_order_id': po.id,
                'sequence':          0,
                'document_key':      '_section',
                'document_label':    po.name or 'Orden de compra',
                'is_required':       False,
                'display_type':      'line_section',
            })
            for seq, (key, label, required) in enumerate(OC_DOC_CATALOG, start=1):
                docs |= self.create({
                    'importation_id':    po.importation_id.id,
                    'purchase_order_id': po.id,
                    'sequence':          seq * 10,
                    'document_key':      key,
                    'document_label':    label,
                    'is_required':       required,
                })
        return docs


class PyxelImportDocumentPage(models.Model):
    _name = 'pyxel.import.document.page'
    _description = 'Página fotográfica de documento de importación'
    _order = 'page_number'

    document_id = fields.Many2one(
        'pyxel.import.document', ondelete='cascade', required=True, index=True)
    page_number = fields.Integer(default=1)
    image = fields.Binary(attachment=True, string='Imagen')
    image_filename = fields.Char()
    quality_score = fields.Float(string='Calidad (%)')
    # TODO [IA-CALIDAD]: al crear una página, llamar al validador de calidad de imagen
    # y fijar quality_score. Si calidad < umbral, devolver error JSON al cliente.
