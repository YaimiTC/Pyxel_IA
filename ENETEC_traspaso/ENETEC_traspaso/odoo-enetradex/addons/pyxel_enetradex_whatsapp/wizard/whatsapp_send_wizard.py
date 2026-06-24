from odoo import models, fields, _
from odoo.exceptions import UserError


class WhatsappSendWizard(models.TransientModel):
    _name = 'whatsapp.send.wizard'
    _description = 'Enviar mensaje WhatsApp'

    partner_id = fields.Many2one('res.partner', string='Contacto')
    phone = fields.Char('Número WhatsApp', required=True)
    message = fields.Text('Mensaje', required=True)

    def action_send(self):
        ok, info = self.env['whatsapp.service'].send(self.phone, self.message)
        if not ok:
            raise UserError(_('Error enviando WhatsApp: %s') % info)
        if self.partner_id:
            self.partner_id.message_post(
                body=f'WhatsApp enviado a {self.phone}: {self.message}',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        return {'type': 'ir.actions.act_window_close'}
