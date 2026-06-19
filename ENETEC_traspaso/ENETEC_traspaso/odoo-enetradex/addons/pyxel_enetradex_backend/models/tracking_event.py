# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class EnTrackingEvent(models.Model):
    """Evento de la línea de tiempo de seguimiento que ve el cliente en su cuenta.

    Cada cambio de etapa (acreditación o importación), documento o nota genera
    un evento con fecha y responsable. Lo crea el backend automáticamente o el
    comercial. El portal del cliente lo lee (sudo) para pintar la línea de tiempo.
    """
    _name = 'en.tracking.event'
    _description = "Evento de seguimiento de la operación"
    _order = 'date desc, id desc'

    name = fields.Char(string="Resumen", compute='_compute_name', store=True)
    phase = fields.Selection([
        ('accreditation', "Acreditación"),
        ('importation', "Importación"),
    ], string="Fase", required=True, index=True)
    event_type = fields.Selection([
        ('created', "Solicitud recibida"),
        ('stage', "Cambio de etapa"),
        ('doc', "Documento"),
        ('note', "Nota"),
    ], string="Tipo", default='stage', required=True)
    stage_name = fields.Char(string="Etapa")
    note = fields.Text(string="Detalle")
    date = fields.Datetime(string="Fecha", default=fields.Datetime.now, required=True, index=True)
    user_id = fields.Many2one('res.users', string="Responsable", default=lambda s: s.env.user)
    source = fields.Selection([
        ('auto', "Automático"),
        ('manual', "Comercial"),
    ], string="Origen", default='auto', required=True)

    # Vínculos: una de las dos referencias (lead de acreditación o proceso de importación).
    lead_id = fields.Many2one('crm.lead', string="Solicitud (CRM)", ondelete='cascade', index=True)
    operation_id = fields.Many2one('importation.process', string="Operación", ondelete='cascade', index=True)
    # Cliente al que pertenece el evento (para filtrar el portal).
    partner_id = fields.Many2one('res.partner', string="Cliente", index=True)
    is_client_visible = fields.Boolean(string="Visible para el cliente", default=True)

    @api.depends('phase', 'stage_name', 'event_type')
    def _compute_name(self):
        labels = dict(self._fields['event_type'].selection)
        for rec in self:
            if rec.event_type == 'stage' and rec.stage_name:
                rec.name = rec.stage_name
            else:
                rec.name = labels.get(rec.event_type, '') or (rec.stage_name or '')

    # ------------------------------------------------------------------
    # API de registro + notificación (la usan los hooks de lead y proceso)
    # ------------------------------------------------------------------
    @api.model
    def en_log_event(self, record, phase, stage_name, partner,
                     source='auto', event_type='stage', note=False):
        """Crea el evento de la línea de tiempo y notifica al cliente.

        record: el crm.lead o importation.process que cambió.
        partner: el cliente al que pertenece el evento (para el portal y el correo).
        """
        vals = {
            'phase': phase,
            'event_type': event_type,
            'stage_name': stage_name,
            'source': source,
            'note': note or False,
            'partner_id': partner.id if partner else False,
        }
        if record._name == 'crm.lead':
            vals['lead_id'] = record.id
        elif record._name == 'importation.process':
            vals['operation_id'] = record.id
        event = self.sudo().create(vals)
        event._en_notify(record, partner)
        return event

    def _en_notify(self, record, partner):
        """Avisa al cliente: chatter del portal + correo (message_post) y WhatsApp (stub)."""
        self.ensure_one()
        if not self.is_client_visible:
            return
        fase_lbl = dict(self._fields['phase'].selection).get(self.phase) or ''
        body = "<b>%s</b> — %s" % (fase_lbl, self.stage_name or self.name)
        if self.note:
            body += "<br/>%s" % self.note
        # message_post con partner_ids publica en el chatter (portal) y, si el
        # cliente tiene correo, le envía la notificación por email en un solo paso.
        recipients = partner.ids if (partner and partner.email) else []
        try:
            record.sudo().message_post(
                body=body, partner_ids=recipients,
                subtype_xmlid='mail.mt_comment')
        except Exception as e:  # pragma: no cover - el chatter no debe romper el flujo
            _logger.warning("No se pudo postear aviso de seguimiento: %s", e)
        self._en_notify_whatsapp(partner, body)

    def _en_notify_whatsapp(self, partner, body):
        """Punto de integración con WhatsApp Business / Twilio (aún no conectado).

        Se activa con el parámetro de sistema en_seguimiento.whatsapp_enabled=True.
        Cuando se integre un proveedor, aquí se hace la llamada a su API usando el
        móvil del partner y el cuerpo del aviso.
        """
        if not partner:
            return
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('en_seguimiento.whatsapp_enabled') != 'True':
            return
        numero = partner.mobile or partner.phone
        _logger.info("[WhatsApp pendiente de integración] -> %s: %s", numero, body)
