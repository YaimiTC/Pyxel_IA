# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        Log = self.env["whatsapp.message.log"]
        for move in posted.filtered(lambda m: m.move_type == "out_invoice"):
            try:
                Log._send_event("invoice_posted", move, move.partner_id)
            except Exception:
                _logger.exception("WhatsApp invoice_posted notification failed (%s)", move.name)
        return posted

    def action_wa_payment_reminder(self):
        """Botón: envía un recordatorio de pago por WhatsApp (plantilla)."""
        Log = self.env["whatsapp.message.log"]
        for move in self.filtered(lambda m: m.move_type == "out_invoice"):
            Log._send_event("payment_reminder", move, move.partner_id)
        return True
