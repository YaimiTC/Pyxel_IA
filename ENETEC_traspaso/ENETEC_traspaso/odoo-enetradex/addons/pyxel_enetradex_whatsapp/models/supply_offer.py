from odoo import models, api


class EnSupplyOffer(models.Model):
    _inherit = 'en.supply.offer'

    def write(self, vals):
        old_states = {r.id: r.state for r in self}
        res = super().write(vals)
        if vals.get('state') == 'published':
            for offer in self:
                if old_states.get(offer.id) != 'published':
                    self._notify_published(offer)
        return res

    def _notify_published(self, offer):
        partner = offer.supplier_id
        phone = partner.whatsapp_phone or partner.mobile or partner.phone
        if not phone:
            return
        products = ', '.join(offer.line_ids.mapped('product_id.name')) or 'N/A'
        msg = (
            f"📦 *ENETRADEX* — Oferta publicada\n\n"
            f"Estimado/a {partner.name},\n"
            f"Su oferta de *{products}* ya está visible en el catálogo de proveedores.\n"
            f"Puerto: {offer.port or 'N/A'} | Incoterm: {offer.incoterm_id.code if offer.incoterm_id else 'N/A'}\n\n"
            f"Los compradores ya pueden contactarle.\n"
            f"📞 +53 5280 7765 | comercial@enetec.telmark.com.cu"
        )
        self.env['whatsapp.service'].send(phone, msg)
