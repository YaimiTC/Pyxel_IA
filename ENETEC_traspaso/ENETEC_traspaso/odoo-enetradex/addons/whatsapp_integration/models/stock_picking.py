# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        Log = self.env["whatsapp.message.log"]
        for pk in self.filtered(lambda p: p.state == "done" and p.picking_type_code == "outgoing"):
            try:
                Log._send_event("delivery_done", pk, pk.partner_id)
            except Exception:
                _logger.exception("WhatsApp delivery_done notification failed (%s)", pk.name)
        return res
