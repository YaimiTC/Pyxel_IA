# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MAX_RETRY = 3


class WhatsappMessageLog(models.Model):
    """Registro de cada mensaje (entrante/saliente) con su estado, respuesta de
    la API y el registro de Odoo que lo originó. Es el corazón del mini-CRM."""
    _name = "whatsapp.message.log"
    _description = "WhatsApp Message Log"
    _order = "create_date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name")
    partner_id = fields.Many2one("res.partner", string="Contacto", index=True, ondelete="set null")
    phone = fields.Char(string="Número (E.164)", index=True)
    direction = fields.Selection(
        [("outbound", "Saliente"), ("inbound", "Entrante")],
        required=True, default="outbound", index=True)
    msg_type = fields.Selection(
        [("text", "Texto"), ("template", "Plantilla"), ("other", "Otro")],
        required=True, default="text")
    template_mapping_id = fields.Many2one("whatsapp.template.mapping", string="Plantilla (mapeo)")
    template_name = fields.Char()
    body = fields.Text(string="Mensaje")
    state = fields.Selection(
        [("draft", "Borrador"), ("queued", "En cola"), ("sent", "Enviado"),
         ("delivered", "Entregado"), ("read", "Leído"), ("received", "Recibido"),
         ("failed", "Fallido")],
        default="draft", required=True, index=True, tracking=True)
    wa_message_id = fields.Char(string="ID de WhatsApp", index=True)
    error = fields.Char(string="Error")
    response_json = fields.Text(string="Respuesta API")
    res_model = fields.Char(string="Modelo origen", index=True)
    res_id = fields.Integer(string="ID origen", index=True)
    event = fields.Char(string="Evento")
    retry_count = fields.Integer(default=0)

    @api.depends("partner_id", "direction", "msg_type", "create_date")
    def _compute_display_name(self):
        for rec in self:
            who = rec.partner_id.display_name or rec.phone or "?"
            arrow = "↗" if rec.direction == "outbound" else "↘"
            rec.display_name = "%s %s (%s)" % (arrow, who, rec.msg_type or "")

    # ---------- Reglas de ventana de 24h ----------
    def _within_24h(self):
        """True si hay un mensaje ENTRANTE del contacto en las últimas 24h
        (ventana de servicio en la que se permite texto libre)."""
        self.ensure_one()
        if not self.partner_id and not self.phone:
            return False
        domain = [("direction", "=", "inbound"),
                  ("create_date", ">=", fields.Datetime.now() - timedelta(hours=24))]
        if self.partner_id:
            domain.append(("partner_id", "=", self.partner_id.id))
        else:
            domain.append(("phone", "=", self.phone))
        return bool(self.search_count(domain))

    # ---------- Envío ----------
    def action_send(self):
        for rec in self:
            rec._send_now()
        return True

    def _send_now(self):
        self.ensure_one()
        Api = self.env["whatsapp.api"]
        to = self.phone or (self.partner_id and self.partner_id._wa_phone())
        if not to:
            return self._mark_failed(_("Sin número de WhatsApp."))
        if self.msg_type == "template":
            mp = self.template_mapping_id
            name = self.template_name or (mp and mp.template_name)
            if not name:
                return self._mark_failed(_("Falta el nombre de la plantilla."))
            components = []
            if mp and self.res_model and self.res_id:
                rec = self.env[self.res_model].browse(self.res_id)
                components = mp.build_components(rec)
            payload = Api.build_template_payload(to, name, mp and mp.lang_code or "es", components)
        else:
            # Texto libre: solo permitido dentro de la ventana de 24h.
            if not self._within_24h():
                return self._mark_failed(_(
                    "Fuera de la ventana de 24h: este contacto requiere una plantilla aprobada."))
            payload = Api.build_text_payload(to, self.body)
        res = Api.send(payload)
        self.response_json = json.dumps(res.get("response") or {}, ensure_ascii=False, indent=2)
        if res.get("ok"):
            self.write({"state": "sent", "wa_message_id": res.get("wa_message_id"),
                        "error": False, "phone": to})
        else:
            self._mark_failed(res.get("error") or _("Error desconocido"))
        return res.get("ok")

    def _mark_failed(self, error):
        self.ensure_one()
        self.write({"state": "failed", "error": (error or "")[:512]})
        return False

    # ---------- API de alto nivel (la usan los hooks de eventos) ----------
    @api.model
    def _send_event(self, event, record, partner):
        """Crea y envía (vía plantilla) la notificación de un evento de negocio.
        Respeta opt-in y existencia de número y plantilla."""
        if not partner or not partner.whatsapp_opt_in:
            return False
        to = partner._wa_phone()
        if not to:
            return False
        mp = self.env["whatsapp.template.mapping"]._find(event, record._name)
        if not mp:
            _logger.info("WhatsApp: sin plantilla para evento %s (%s)", event, record._name)
            return False
        log = self.create({
            "partner_id": partner.id, "phone": to, "direction": "outbound",
            "msg_type": "template", "template_mapping_id": mp.id,
            "template_name": mp.template_name, "event": event,
            "res_model": record._name, "res_id": record.id, "state": "queued",
            "body": _("Plantilla: %s") % mp.template_name,
        })
        log._send_now()
        log._post_to_origin(record)
        return log

    @api.model
    def _send_text(self, partner, body, record=False):
        """Envía texto libre (sujeto a ventana 24h)."""
        to = partner and partner._wa_phone()
        if not to:
            return False
        vals = {"partner_id": partner.id, "phone": to, "direction": "outbound",
                "msg_type": "text", "body": body, "state": "queued"}
        if record:
            vals.update(res_model=record._name, res_id=record.id)
        log = self.create(vals)
        log._send_now()
        return log

    def _post_to_origin(self, record):
        """Deja traza en el chatter del registro origen."""
        self.ensure_one()
        if record and hasattr(record, "message_post"):
            state = dict(self._fields["state"].selection).get(self.state, self.state)
            record.message_post(body=_(
                "WhatsApp → %(to)s · plantilla <b>%(tpl)s</b> · estado: %(st)s") % {
                    "to": self.phone, "tpl": self.template_name or "-", "st": state})

    # ---------- Reintentos (cron) ----------
    @api.model
    def _cron_retry_failed(self):
        fails = self.search([("direction", "=", "outbound"), ("state", "=", "failed"),
                             ("retry_count", "<", MAX_RETRY)], limit=100)
        for rec in fails:
            rec.retry_count += 1
            rec._send_now()

    # ---------- Inbound / estados (los llama el webhook) ----------
    @api.model
    def _log_inbound(self, phone, body, wa_message_id=False, msg_type="text"):
        partner = self.env["res.partner"].sudo()._wa_find_by_phone(phone)
        log = self.sudo().create({
            "partner_id": partner.id if partner else False, "phone": phone,
            "direction": "inbound", "msg_type": msg_type, "body": body,
            "wa_message_id": wa_message_id, "state": "received",
        })
        if partner:
            partner.message_post(body=_("WhatsApp ↘ <b>%(p)s</b>: %(b)s") % {
                "p": phone, "b": (body or "")[:500]})
        return log

    @api.model
    def _cron_pull_gateway(self):
        """Consulta el gateway exterior y procesa los eventos encolados
        (mensajes entrantes y acuses de estado)."""
        Api = self.env["whatsapp.api"]
        if not Api._use_gateway():
            return
        events = Api.pull_gateway(limit=100)
        for ev in events:
            kind = ev.get("kind")
            p = ev.get("payload") or {}
            try:
                if kind == "message":
                    mtype = p.get("type", "text")
                    body = (p.get("text") or {}).get("body", "") if mtype == "text" else "[%s]" % mtype
                    self._log_inbound(p.get("from"), body, p.get("id"), mtype)
                elif kind == "status":
                    self._update_status(p.get("id"), p.get("status"))
            except Exception:
                _logger.exception("Error procesando evento del gateway: %s", ev.get("id"))

    @api.model
    def _update_status(self, wa_message_id, status):
        """Actualiza el estado (sent/delivered/read/failed) por id de WhatsApp."""
        mapping = {"sent": "sent", "delivered": "delivered", "read": "read", "failed": "failed"}
        new = mapping.get(status)
        if not (wa_message_id and new):
            return False
        logs = self.sudo().search([("wa_message_id", "=", wa_message_id)], limit=1)
        if logs and logs.state not in ("read",):
            logs.state = new
        return bool(logs)
