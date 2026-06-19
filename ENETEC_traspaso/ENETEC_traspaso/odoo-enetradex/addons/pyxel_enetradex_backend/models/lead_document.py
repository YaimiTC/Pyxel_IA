# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Mapeo etiqueta de documento -> doc_type del DocValidator (modelo PYME).
LABEL_TO_DOCVAL = {
    'Escritura notarial': 'escritura_notarial',
    'Registro mercantil': 'registro_mercantil',
    'Carnet con el NIT': 'identificacion_fiscal',
    'Contrato de banco': 'contrato_cuentas',
    'Certifico de no adeudo': 'no_adeudo',
}
# Veredicto DocValidator -> ai_state del expediente.
VERDICT_MAP = {'apto': 'passed', 'revisar': 'doubt', 'no_apto': 'rejected'}

# Catálogo de documentos por tipo de entidad. Las ETIQUETAS deben coincidir con
# las del wizard (en_wizard.xml, var DOCS) para poder mapear los adjuntos subidos.
DOC_CATALOG = {
    'Pymes': [
        ('escritura_notarial', 'Escritura notarial', True),
        ('registro_mercantil', 'Registro mercantil', True),
        ('carnet_nit', 'Carnet con el NIT', True),
        ('contrato_banco', 'Contrato de banco', True),
        ('certifico_no_adeudo', 'Certifico de no adeudo', True),
    ],
    'Estatal': [
        ('resoluciones', 'Resoluciones constitutivas', True),
        ('reup', 'Código REUP', True),
        ('nit', 'NIT', True),
        ('contrato_banco', 'Contrato de banco', True),
    ],
    'CNA': [
        ('onat', 'ONAT', True),
        ('reane', 'Código REANE', True),
        ('escritura_notarial', 'Escritura notarial', True),
        ('registro_mercantil', 'Registro mercantil', True),
        ('carnet_nit', 'Carnet con el NIT', True),
        ('contrato_banco', 'Contrato de banco', True),
        ('certifico_no_adeudo', 'Certifico de no adeudo', True),
    ],
    'Sucursal Extranjera': [
        ('escrituras_constitucion', 'Escrituras de constitución', True),
        ('inscripcion_rm', 'Inscripción registro mercantil', True),
        ('licencia_camara', 'Licencia de la cámara comercial', True),
        ('carnet_acore', 'Carnet de ACORE o PALCO', False),
        ('planilla_contribuyente', 'Planilla de contribuyente', True),
        ('contrato_banco', 'Contrato de banco', True),
        ('resolucion_mincex', 'Resolución del MINCEX', True),
    ],
    'Proveedor': [
        ('escritura_constitucion', 'Escritura de constitución', True),
        ('inscripcion_rm', 'Inscripción registro mercantil', True),
        ('poder_acreditativo', 'Poder acreditativo', True),
        ('certifico_cuenta', 'Certifico de cuenta bancaria', True),
        ('codigo_mincex', 'Código MINCEX', True),
    ],
}


class PyxelLeadDocument(models.Model):
    _name = 'pyxel.lead.document'
    _description = 'Documento del expediente de acreditación'
    _order = 'sequence, id'

    lead_id = fields.Many2one('crm.lead', ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    document_key = fields.Char()
    document_label = fields.Char(required=True)
    client_type = fields.Char()
    is_required = fields.Boolean(default=True)
    attachment_id = fields.Many2one('ir.attachment')
    upload_date = fields.Datetime()
    document_file = fields.Binary(related='attachment_id.datas', readonly=True)
    document_filename = fields.Char(related='attachment_id.name', readonly=True)

    # PASO 1 — IA (automático)
    ai_state = fields.Selection([
        ('pending', 'Pendiente'), ('validating', 'Validando'),
        ('passed', 'Apto'), ('doubt', 'Dudoso'), ('rejected', 'Rechazado'),
    ], default='pending', required=True, string="Dictamen IA")
    ai_confidence = fields.Float(string="Confianza IA (%)")
    ai_quality = fields.Float(string="Calidad de imagen (%)")
    ai_reason = fields.Text(string="Reporte de la IA")
    ai_extracted_data = fields.Text(string="Datos extraídos (OCR)")
    ai_findings = fields.Text(string="Hallazgos IA (JSON)")

    # Lista de validación (misma para la IA y la abogada: ella confirma visualmente).
    check_ids = fields.One2many('pyxel.lead.document.check', 'document_id', string="Lista de validación")
    check_total = fields.Integer(compute='_compute_check_counts')
    check_ok_count = fields.Integer(compute='_compute_check_counts', string="Puntos conformes")

    @api.depends('check_ids.lawyer_ok')
    def _compute_check_counts(self):
        for d in self:
            d.check_total = len(d.check_ids)
            d.check_ok_count = len(d.check_ids.filtered('lawyer_ok'))

    # PASO 2 — Abogada (manual)
    lawyer_state = fields.Selection([
        ('blocked', 'No aplica'), ('to_review', 'En revisión'),
        ('approved', 'Aprobado'), ('rejected', 'Rechazado'),
    ], default='blocked', required=True, string="Revisión abogada")
    lawyer_notes = fields.Text(string="Notas internas (el cliente NO las ve)")
    lawyer_reason = fields.Text(string="Motivo de rechazo abogada (lo ve el cliente)")

    # PASO 3 — Comercial (manual)
    commercial_state = fields.Selection([
        ('blocked', 'No aplica'), ('to_review', 'En revisión'),
        ('approved', 'Aprobado'), ('rejected', 'Rechazado'),
    ], default='blocked', required=True, string="Revisión comercial")
    commercial_reason = fields.Text(string="Motivo de rechazo comercial (lo ve el cliente)")

    # ESTADO COMBINADO para el portal
    portal_state = fields.Selection([
        ('pending', 'Pendiente'), ('validating', 'Validando'),
        ('rejected', 'Rechazado'), ('in_review', 'En revisión'),
        ('approved', 'Aprobado'), ('optional', 'Opcional'),
    ], compute='_compute_portal_state', store=True, string="Estado (cliente)")
    portal_reason = fields.Text(compute='_compute_portal_state', store=True)

    @api.depends('attachment_id', 'is_required', 'ai_state', 'ai_reason',
                 'lawyer_state', 'lawyer_reason', 'commercial_state', 'commercial_reason')
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
                if d.lawyer_state == 'rejected':
                    state = 'rejected'
                    reason = d.lawyer_reason
                elif d.lawyer_state != 'approved':
                    state = 'in_review'
                elif d.commercial_state == 'approved':
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

    # Desbloqueo secuencial: al quedar Apto la IA, activa a la abogada.
    def write(self, vals):
        res = super().write(vals)
        if 'ai_state' in vals and vals['ai_state'] in ('passed', 'doubt'):
            for d in self:
                if d.lawyer_state == 'blocked':
                    d.lawyer_state = 'to_review'
        return res

    # ----- Acciones ABOGADA -----
    def action_lawyer_approve(self):
        for d in self:
            if d.ai_state not in ('passed', 'doubt'):
                raise UserError(_("La IA aún no entregó un dictamen revisable para este documento."))
            pend = d.check_ids.filtered(lambda c: not c.lawyer_ok)
            if pend:
                raise UserError(_(
                    "Revisa y marca como conforme todos los puntos de la lista antes de "
                    "aprobar. Faltan: %s") % ', '.join(pend.mapped('name')[:6]))
            d.write({'lawyer_state': 'approved', 'lawyer_reason': False,
                     'commercial_state': 'to_review'})

    def action_lawyer_reject(self):
        for d in self:
            if d.ai_state not in ('passed', 'doubt'):
                raise UserError(_("La IA aún no entregó un dictamen revisable para este documento."))
            if not (d.lawyer_reason or '').strip():
                raise UserError(_("Indique el motivo de rechazo: el cliente verá ese motivo."))
            d.write({'lawyer_state': 'rejected', 'commercial_state': 'blocked'})

    def action_lawyer_reopen(self):
        for d in self:
            if d.ai_state in ('passed', 'doubt'):
                d.write({'lawyer_state': 'to_review', 'commercial_state': 'blocked'})

    # ----- Acciones COMERCIAL -----
    def action_commercial_approve(self):
        for d in self:
            if d.lawyer_state != 'approved':
                raise UserError(_("La abogada aún no aprobó este documento."))
            d.write({'commercial_state': 'approved', 'commercial_reason': False})
            # Si con esto el expediente queda completo, acreditar la empresa.
            d.lead_id._try_accredit_from_expediente()

    def action_commercial_reject(self):
        for d in self:
            if d.lawyer_state != 'approved':
                raise UserError(_("La abogada aún no aprobó este documento."))
            if not (d.commercial_reason or '').strip():
                raise UserError(_("Indique el motivo de rechazo: el cliente verá ese motivo."))
            d.write({'commercial_state': 'rejected'})

    def action_commercial_reopen(self):
        for d in self:
            if d.lawyer_state == 'approved':
                d.write({'commercial_state': 'to_review'})

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
            'res_model': 'pyxel.lead.document',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('pyxel_enetradex_backend.view_pyxel_lead_document_form').id, 'form')],
            'target': 'current',
        }

    def _get_notes_recipients(self):
        self.ensure_one()
        partner = self.lead_id.partner_id
        recips = self.env['res.partner']
        if partner and partner.email:
            recips |= partner
        for c in partner.child_ids:
            if c.email:
                recips |= c
        return recips

    def _build_notes_email_body(self):
        self.ensure_one()
        ai_label = dict(self._fields['ai_state'].selection).get(self.ai_state) or ''
        html = '<p>Documento: <b>%s</b></p>' % (self.document_label or '')
        html += '<p>Dictamen IA: <b>%s</b>' % ai_label
        if self.ai_confidence:
            html += ' (confianza %.0f%%)' % self.ai_confidence
        html += '</p>'
        if self.ai_reason:
            html += '<p>%s</p>' % self.ai_reason
        if self.portal_state == 'rejected':
            if self.lawyer_reason:
                html += '<p><b>Motivo (abogada):</b> %s</p>' % self.lawyer_reason
            if self.commercial_reason:
                html += '<p><b>Motivo (comercial):</b> %s</p>' % self.commercial_reason
        return html

    def action_send_notes_email(self):
        self.ensure_one()
        recips = self._get_notes_recipients()
        if not recips:
            raise UserError(_("No hay destinatarios con correo en la empresa."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_model': 'crm.lead',
                'default_res_id': self.lead_id.id,
                'default_partner_ids': recips.ids,
                'default_subject': _("Acreditación — %s") % (self.document_label or ''),
                'default_body': self._build_notes_email_body(),
                'default_composition_mode': 'comment',
            },
        }

    @api.model
    def get_client_type_for_keys(self, doc_keys):
        # Reservado por compatibilidad con el spec; aquí el tipo se pasa explícito.
        return False

    @api.model
    def _docvalidator_verify(self, file_b64, label):
        """Llama al DocValidator (modelo PYME) y devuelve el veredicto IA mapeado.
        Sin mapeo o si el servicio falla -> queda en 'validating'."""
        doc_type = LABEL_TO_DOCVAL.get(label or '')
        if not doc_type or not file_b64:
            return {'ai_state': 'validating'}
        base = self.env['ir.config_parameter'].sudo().get_param(
            'docvalidator.url', 'http://host.docker.internal:8000')
        try:
            import requests
            r = requests.post(base.rstrip('/') + '/pyme/verify',
                              json={'doc_type': doc_type, 'file_b64': file_b64}, timeout=60)
            r.raise_for_status()
            d = r.json()
            inc = d.get('incumplimientos') or []
            reason = '; '.join(filter(None, (x.get('detail') or x.get('label') for x in inc)))
            findings = [{
                'name': f.get('label'), 'base': f.get('base'), 'detail': f.get('detail'),
                'severity': f.get('severity'), 'status': f.get('status'),
            } for f in (d.get('findings') or [])]
            return {
                'ai_state': VERDICT_MAP.get(d.get('verdict'), 'doubt'),
                'ai_confidence': float(d.get('score') or 0),
                'ai_quality': float(d.get('score') or 0),
                'ai_reason': reason or False,
                'ai_extracted_data': json.dumps(d.get('fields') or {}, ensure_ascii=False),
                'findings': findings,
            }
        except Exception as e:
            _logger.warning("DocValidator no disponible: %s", e)
            return {'ai_state': 'validating'}

    @api.model
    def build_expediente(self, lead, client_type, uploaded, verdicts=None):
        """Crea una línea por documento del catálogo del tipo. `uploaded` es un
        dict {etiqueta: attachment_id}; `verdicts` {etiqueta: dict del veredicto IA}."""
        catalog = DOC_CATALOG.get(client_type or '', [])
        if not catalog:
            return self.browse()
        uploaded = uploaded or {}
        verdicts = verdicts or {}
        Check = self.env['pyxel.lead.document.check'].sudo()
        docs = self.browse()
        seq = 10
        for key, label, required in catalog:
            att_id = uploaded.get(label)
            vals = {
                'lead_id': lead.id, 'sequence': seq,
                'document_key': key, 'document_label': label,
                'client_type': client_type, 'is_required': required,
            }
            findings = []
            if att_id:
                vals.update({'attachment_id': att_id, 'upload_date': fields.Datetime.now(),
                             'ai_state': 'validating'})
                v = verdicts.get(label) or {}
                if v.get('ai_state') in ('passed', 'doubt', 'rejected'):
                    vals['ai_state'] = v['ai_state']
                    vals['ai_confidence'] = v.get('ai_confidence') or 0.0
                    vals['ai_quality'] = v.get('ai_quality') or 0.0
                    vals['ai_reason'] = v.get('ai_reason') or False
                    vals['ai_extracted_data'] = v.get('ai_extracted_data') or False
                    findings = v.get('findings') or []
                    if findings:
                        vals['ai_findings'] = json.dumps(findings, ensure_ascii=False)
                    if v['ai_state'] in ('passed', 'doubt'):
                        # create() no dispara el write() de desbloqueo: activamos a la abogada aquí.
                        vals['lawyer_state'] = 'to_review'
            doc = self.create(vals)
            for i, fd in enumerate(findings):
                st = fd.get('status') if fd.get('status') in ('ok', 'fail', 'imagen') else 'pending'
                sev = fd.get('severity') if fd.get('severity') in ('critico', 'alto', 'medio', 'bajo') else False
                Check.create({
                    'document_id': doc.id, 'sequence': (i + 1) * 10,
                    'name': fd.get('name') or fd.get('label') or _('Punto'),
                    'base': fd.get('base'), 'detail': fd.get('detail'),
                    'severity': sev, 'ai_status': st,
                    'lawyer_ok': (st == 'ok'),
                })
            docs |= doc
            seq += 10
        return docs


class PyxelLeadDocumentCheck(models.Model):
    _name = 'pyxel.lead.document.check'
    _description = 'Punto de validación del documento (lista de chequeo IA + abogada)'
    _order = 'sequence, id'

    document_id = fields.Many2one('pyxel.lead.document', ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Punto a validar", required=True)
    base = fields.Char(string="Base legal")
    detail = fields.Char(string="Detalle de la IA")
    severity = fields.Selection([
        ('critico', 'Crítico'), ('alto', 'Alto'), ('medio', 'Medio'), ('bajo', 'Bajo'),
    ], string="Severidad")
    ai_status = fields.Selection([
        ('ok', 'Cumple'), ('fail', 'No cumple'),
        ('imagen', 'Revisión visual'), ('pending', 'Pendiente'),
    ], string="IA", default='pending')
    lawyer_ok = fields.Boolean(string="Conforme")
    lawyer_comment = fields.Char(string="Comentario")
