# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            try:
                self.env["whatsapp.message.log"]._send_event(
                    "sale_confirm", order, order.partner_id)
            except Exception:
                _logger.exception("WhatsApp sale_confirm notification failed (%s)", order.name)
        return res
