from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            partner = order.partner_id
            phone = partner.whatsapp_phone or partner.mobile or partner.phone
            if not phone:
                continue
            msg = (
                f"✅ *ENETRADEX* — Cotización confirmada\n\n"
                f"Estimado/a {partner.name},\n"
                f"Su orden *{order.name}* ha sido confirmada.\n"
                f"Total: *{order.currency_id.symbol} {order.amount_total:,.2f}*\n\n"
                f"Nuestro equipo se pondrá en contacto pronto.\n"
                f"📞 +53 5280 7765 | comercial@enetec.telmark.com.cu"
            )
            self.env['whatsapp.service'].send(phone, msg)
        return res
