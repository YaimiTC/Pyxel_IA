# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Catálogo de documentos requeridos por tipo de cliente.
# Cada entrada: (clave_técnica, etiqueta, es_requerido)
# Las claves coinciden con los inputs doc_* del formulario de acreditación.
DOC_CATALOG = {
    'Mipyme': [
        ('doc_mipyme_escritura_notarial', 'Escritura notarial', True),
        ('doc_mipyme_registro_mercantil', 'Registro mercantil', True),
        ('doc_mipyme_carnet_nit', 'Carnet con el NIT', True),
        ('doc_mipyme_contrato_banco', 'Contrato de banco CUP, MLC o USD o certifico bancario', True),
        ('doc_mipyme_certifico_adeudo', 'Certifico de no adeudo o comprobante del último pago', True),
    ],
    'Sucursal Extranjera': [
        ('doc_sucursal_escrituras_constitucion', 'Escrituras de constituciones y modificaciones efectuadas', True),
        ('doc_sucursal_registro_mercantil', 'Inscripción en el registro mercantil', True),
        ('doc_sucursal_licencia_camara', 'Licencia de Cámara de Comercio', True),
        ('doc_sucursal_planilla_contribuyente', 'Planilla de inscripción o actualización en el registro de contribuyente', True),
        ('doc_sucursal_contrato_banco', 'Contrato de banco CUP, MLC o USD o certifico bancario', True),
        ('doc_sucursal_resolucion_mincex', 'Resolución del Ministerio del Comercio Exterior y la Inversión Extranjera', True),
    ],
    'Estatal': [
        ('doc_estatal_resoluciones', 'Resoluciones constitutivas', True),
        ('doc_estatal_reup', 'Documento acreditativo del Código REUP', True),
        ('doc_estatal_nit', 'Documento acreditativo del NIT', True),
        ('doc_estatal_contrato_banco', 'Contrato de banco CUP, MLC o USD o certifico bancario', True),
    ],
    'CNA': [
        ('doc_cna_onat', 'Documento acreditativo ONAT', True),
        ('doc_cna_reane', 'Documento acreditativo Código REANE', True),
        ('doc_cna_escritura_notarial', 'Escritura notarial', True),
        ('doc_cna_registro_mercantil', 'Registro mercantil', True),
        ('doc_cna_carnet_nit', 'Carnet con el NIT', True),
        ('doc_cna_contrato_banco', 'Contrato de banco CUP, MLC o USD o certifico bancario', True),
        ('doc_cna_certifico_adeudo', 'Certifico de no adeudo o comprobante del último pago', True),
    ],
    'Proveedor Extranjero': [
        ('doc_prov_escritura', 'Escritura de constitución y modificaciones efectuadas', True),
        ('doc_prov_registro_mercantil', 'Inscripción en el registro mercantil', True),
        ('doc_prov_poder_acreditativo', 'Poder acreditativo de legitimación de representantes', True),
        ('doc_prov_certifico_bancario', 'Certifico de cuenta bancaria con el que va a operar el contrato', True),
        ('doc_prov_codigo_mincex', 'Código MIncex', True),
    ],
}

# Prefijo de la clave doc_* -> tipo de cliente del catálogo
DOC_PREFIX_TO_TYPE = {
    'doc_mipyme_': 'Mipyme',
    'doc_sucursal_': 'Sucursal Extranjera',
    'doc_estatal_': 'Estatal',
    'doc_cna_': 'CNA',
    'doc_prov_': 'Proveedor Extranjero',
}


class PyxelLeadDocument(models.Model):
    _name = 'pyxel.lead.document'
    _description = 'Documento del expediente de acreditación'
    _order = 'sequence, id'

    lead_id = fields.Many2one(
        'crm.lead', string='Solicitud', ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)

    document_key = fields.Char(string='Clave técnica')
    document_label = fields.Char(string='Concepto', required=True)
    client_type = fields.Char(string='Tipo de cliente')
    is_required = fields.Boolean(string='Requerido', default=True)

    attachment_id = fields.Many2one('ir.attachment', string='Archivo')
    upload_date = fields.Datetime(string='Fecha de subida')

    # --- Estado IA (automático, primer filtro) ---
    ai_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('validating', 'Validando'),
        ('passed', 'Apto'),
        ('doubt', 'Dudoso'),
        ('rejected', 'Rechazado'),
    ], string='Veredicto IA', default='pending', required=True)
    ai_confidence = fields.Float(string='Confianza IA (%)')
    ai_quality = fields.Float(string='Calidad de imagen (%)')
    ai_reason = fields.Text(string='Motivo IA')

    # --- Paso 2: Revisión de la abogada (manual) ---
    lawyer_state = fields.Selection([
        ('blocked', 'No aplica'),
        ('to_review', 'En revisión'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Revisión legal', default='blocked', required=True)
    lawyer_reason = fields.Text(
        string='Motivo de rechazo (abogada)',
        help='Motivo que verá el cliente si la abogada rechaza.')

    # --- Paso 3: Revisión comercial (manual) ---
    commercial_state = fields.Selection([
        ('blocked', 'No aplica'),
        ('to_review', 'En revisión'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Revisión comercial', default='blocked', required=True)
    commercial_reason = fields.Text(string='Motivo del comercial')

    # --- Estado combinado para el portal del cliente ---
    portal_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('validating', 'Validando'),
        ('rejected', 'Rechazado'),
        ('in_review', 'En revisión'),
        ('approved', 'Aprobado'),
        ('optional', 'Opcional'),
    ], string='Estado', compute='_compute_portal_state', store=True)

    portal_reason = fields.Text(
        string='Motivo visible al cliente', compute='_compute_portal_state', store=True)

    # --- Revisión: previsualización y notas ---
    document_file = fields.Binary(
        related='attachment_id.datas', string='Documento', readonly=True)
    document_filename = fields.Char(
        related='attachment_id.name', string='Nombre del archivo', readonly=True)
    ai_extracted_data = fields.Text(
        string='Datos extraídos por la IA',
        help='Datos OCR devueltos por el validador (NIT, nombre, vencimiento, etc.).')
    lawyer_notes = fields.Text(
        string='Notas de la abogada',
        help='Notas internas de la abogada. NO se muestran al cliente.')

    @api.depends('attachment_id', 'is_required', 'ai_state', 'ai_reason',
                 'lawyer_state', 'lawyer_reason',
                 'commercial_state', 'commercial_reason')
    def _compute_portal_state(self):
        for doc in self:
            reason = False
            if not doc.attachment_id and doc.commercial_state != 'approved':
                state = 'pending' if doc.is_required else 'optional'
            elif doc.ai_state == 'validating':
                state = 'validating'
            elif doc.ai_state in ('doubt', 'rejected'):
                state = 'rejected'
                reason = doc.ai_reason or _('La validación automática no superó el documento. Suba una versión más nítida o el documento correcto.')
            elif doc.ai_state == 'passed':
                # Paso 2: abogada
                if doc.lawyer_state == 'rejected':
                    state = 'rejected'
                    reason = doc.lawyer_reason
                elif doc.lawyer_state != 'approved':
                    state = 'in_review'
                # Paso 3: comercial (solo si la abogada aprobó)
                elif doc.commercial_state == 'approved':
                    state = 'approved'
                elif doc.commercial_state == 'rejected':
                    state = 'rejected'
                    reason = doc.commercial_reason
                else:
                    state = 'in_review'
            else:
                state = 'pending' if doc.is_required else 'optional'
            doc.portal_state = state
            doc.portal_reason = reason

    def write(self, vals):
        """Desbloqueo automático IA -> abogada cuando el validador marca 'Apto'."""
        res = super().write(vals)
        if 'ai_state' in vals:
            for doc in self:
                if doc.ai_state == 'passed' and doc.lawyer_state == 'blocked':
                    doc.lawyer_state = 'to_review'
        return res

    # --- Paso 2: Acciones de la abogada ---
    def action_lawyer_approve(self):
        for doc in self:
            if doc.ai_state != 'passed':
                raise UserError(_(
                    "No se puede aprobar '%s': el documento aún no superó la "
                    "validación automática (IA).") % doc.document_label)
            doc.lawyer_state = 'approved'
            doc.lawyer_reason = False
            # Desbloquea la revisión comercial
            doc.commercial_state = 'to_review'

    def action_lawyer_reject(self):
        for doc in self:
            if doc.ai_state != 'passed':
                raise UserError(_(
                    "No se puede rechazar '%s': el documento aún no superó la "
                    "validación automática (IA).") % doc.document_label)
            if not (doc.lawyer_reason and doc.lawyer_reason.strip()):
                raise UserError(_(
                    "Indique el motivo del rechazo de '%s' en el campo "
                    "'Motivo de rechazo (abogada)'. El cliente verá ese motivo "
                    "en su portal.") % doc.document_label)
            doc.lawyer_state = 'rejected'
            doc.commercial_state = 'blocked'

    def action_lawyer_reopen(self):
        for doc in self:
            if doc.ai_state == 'passed':
                doc.lawyer_state = 'to_review'
                doc.commercial_state = 'blocked'

    # --- Paso 3: Acciones del comercial ---
    def action_commercial_approve(self):
        for doc in self:
            if doc.lawyer_state != 'approved':
                raise UserError(_(
                    "No se puede aprobar '%s': la abogada aún no aprobó la "
                    "revisión legal.") % doc.document_label)
            doc.commercial_state = 'approved'
            doc.commercial_reason = False

    def action_commercial_reject(self):
        for doc in self:
            if doc.lawyer_state != 'approved':
                raise UserError(_(
                    "No se puede rechazar '%s': la abogada aún no aprobó la "
                    "revisión legal.") % doc.document_label)
            if not (doc.commercial_reason and doc.commercial_reason.strip()):
                raise UserError(_(
                    "Indique el motivo del rechazo de '%s' en el campo "
                    "'Motivo del comercial' antes de rechazar. El cliente verá "
                    "ese motivo en su portal.") % doc.document_label)
            doc.commercial_state = 'rejected'

    def action_commercial_reopen(self):
        for doc in self:
            if doc.lawyer_state == 'approved':
                doc.commercial_state = 'to_review'

    def action_view_document(self):
        """Abre el PDF subido en una pestaña nueva del navegador."""
        self.ensure_one()
        if not self.attachment_id:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=false' % self.attachment_id.id,
            'target': 'new',
        }

    def action_open_review(self):
        """Abre la ficha de revisión del documento (previsualizador + notas)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.document_label or _('Revisión de documento'),
            'res_model': 'pyxel.lead.document',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'pyxel_import_backend.view_pyxel_lead_document_form').id,
            'target': 'current',
        }

    def _get_notes_recipients(self):
        """Destinatarios: empresa de la oportunidad + contacto(s) individual(es)."""
        self.ensure_one()
        partners = self.env['res.partner']
        lead = self.lead_id
        if lead.partner_id:
            if lead.partner_id.email:
                partners |= lead.partner_id
            partners |= lead.partner_id.child_ids.filtered('email')
        return partners

    def _build_notes_email_body(self):
        self.ensure_one()
        ai_label = dict(self._fields['ai_state'].selection).get(self.ai_state, '')
        parts = [
            '<p>Estimado cliente,</p>',
            '<p>Le compartimos la revisión del documento '
            '<strong>%s</strong> de su expediente de acreditación.</p>'
            % (self.document_label or ''),
        ]
        dictamen = '<p><strong>Dictamen automático (IA):</strong> %s' % ai_label
        if self.ai_confidence:
            dictamen += ' &#8212; confianza %d%%' % int(self.ai_confidence)
        dictamen += '</p>'
        parts.append(dictamen)
        if self.ai_reason:
            parts.append('<p><strong>Observación de la IA:</strong> %s</p>'
                         % self.ai_reason)
        if self.lawyer_state == 'rejected' and self.lawyer_reason:
            parts.append('<p><strong>Motivo de la revisión legal:</strong><br/>%s</p>'
                         % self.lawyer_reason.replace('\n', '<br/>'))
        if self.commercial_state == 'rejected' and self.commercial_reason:
            parts.append('<p><strong>Motivo de la revisión comercial:</strong><br/>%s</p>'
                         % self.commercial_reason.replace('\n', '<br/>'))
        return ''.join(parts)

    def action_send_notes_email(self):
        """Abre el compositor de Odoo con las notas precargadas.

        El correo se registra en el chatter de la oportunidad (crm.lead),
        se envía por el servidor de correo saliente institucional y el autor
        es el usuario logueado. Destinatarios: empresa + contacto individual.
        """
        self.ensure_one()
        lead = self.lead_id
        partners = self._get_notes_recipients()
        if not partners:
            raise UserError(_(
                "No hay correos de destino. La oportunidad no tiene una empresa "
                "ni un contacto con email configurado."))
        subject = _('Revisión de su documento: %s') % (self.document_label or '')
        ctx = {
            'default_model': 'crm.lead',
            'default_res_id': lead.id,
            'default_composition_mode': 'comment',
            'default_partner_ids': partners.ids,
            'default_subject': subject,
            'default_body': self._build_notes_email_body(),
            'mail_post_autofollow': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enviar notas al cliente'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': ctx,
        }

    @api.model
    def get_client_type_for_keys(self, doc_keys):
        """Infiere el tipo de cliente a partir de las claves doc_* subidas."""
        for prefix, ctype in DOC_PREFIX_TO_TYPE.items():
            if any(k.startswith(prefix) for k in doc_keys):
                return ctype
        return False

    @api.model
    def build_expediente(self, lead, client_type, uploaded=None):
        """Crea las líneas del expediente para un lead según su tipo de cliente.

        uploaded: dict {document_key: ir.attachment recordset} con lo subido.
        Las líneas con archivo arrancan en ai_state 'validating' (a la espera
        del validador IA); el resto quedan 'pending'.
        """
        uploaded = uploaded or {}
        catalog = DOC_CATALOG.get(client_type, [])
        seq = 10
        for key, label, required in catalog:
            attachment = uploaded.get(key)
            vals = {
                'lead_id': lead.id,
                'sequence': seq,
                'document_key': key,
                'document_label': label,
                'client_type': client_type,
                'is_required': required,
            }
            if attachment:
                vals.update({
                    'attachment_id': attachment.id,
                    'upload_date': fields.Datetime.now(),
                    'ai_state': 'validating',
                })
            self.create(vals)
            seq += 10
        return True
