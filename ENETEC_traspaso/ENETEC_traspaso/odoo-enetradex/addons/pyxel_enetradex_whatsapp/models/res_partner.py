from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    whatsapp_phone = fields.Char('WhatsApp', help='Número con código de país. Ej: +5358034112')

    def action_send_whatsapp(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Enviar WhatsApp',
            'res_model': 'whatsapp.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_phone': self.whatsapp_phone or self.mobile or self.phone or '',
            },
        }
