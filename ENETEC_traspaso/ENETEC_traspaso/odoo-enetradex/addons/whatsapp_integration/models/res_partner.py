# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models


def _digits(value):
    """Deja solo dígitos (E.164 sin '+', como exige la Cloud API)."""
    if not value:
        return ""
    return re.sub(r"\D", "", value)


class ResPartner(models.Model):
    _inherit = "res.partner"

    whatsapp_number = fields.Char(
        string="WhatsApp", help="Número con código de país en formato E.164 (ej. +5352807765).")
    whatsapp_opt_in = fields.Boolean(
        string="Acepta WhatsApp", help="Consentimiento del contacto para recibir mensajes (GDPR).")
    whatsapp_formatted = fields.Char(
        string="WhatsApp (E.164)", compute="_compute_whatsapp_formatted")
    whatsapp_message_count = fields.Integer(compute="_compute_whatsapp_message_count")

    @api.depends("whatsapp_number", "mobile", "phone")
    def _compute_whatsapp_formatted(self):
        for p in self:
            p.whatsapp_formatted = p._wa_phone()

    def _compute_whatsapp_message_count(self):
        Log = self.env["whatsapp.message.log"]
        for p in self:
            p.whatsapp_message_count = Log.search_count([("partner_id", "=", p.id)])

    def _wa_phone(self):
        """Número normalizado (dígitos con código de país). Usa whatsapp_number,
        si no mobile, si no phone."""
        self.ensure_one()
        return _digits(self.whatsapp_number or self.mobile or self.phone)

    @api.model
    def _wa_find_by_phone(self, phone):
        """Busca el contacto por número (compara solo dígitos)."""
        d = _digits(phone)
        if not d:
            return self.browse()
        # Coincidencia por sufijo razonable para tolerar prefijos/0 iniciales.
        candidates = self.search([
            "|", "|", ("whatsapp_number", "!=", False),
            ("mobile", "!=", False), ("phone", "!=", False)], limit=500)
        for c in candidates:
            if c._wa_phone() and (c._wa_phone() == d or d.endswith(c._wa_phone()[-8:])):
                return c
        return self.browse()

    def action_whatsapp_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "WhatsApp",
            "res_model": "whatsapp.message.log",
            "view_mode": "tree,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id, "default_phone": self._wa_phone()},
        }
