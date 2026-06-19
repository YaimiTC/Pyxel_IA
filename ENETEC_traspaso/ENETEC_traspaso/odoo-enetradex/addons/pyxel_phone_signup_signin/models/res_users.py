from odoo import models, api, tools, _
from odoo.exceptions import UserError
import re


class ResUsers(models.Model):
    _inherit = 'res.users'

    @staticmethod
    def is_valid_phone(phone):
        """
        Verifica si el valor dado es un número de teléfono válido.
        Acepta formatos como +1234567890 o 1234567890 (7 a 15 dígitos).
        """
        phone_regex = r'^\+?\d{7,15}$'
        return bool(re.match(phone_regex, phone))

    @api.onchange('login')
    def on_change_login(self):
        if self.login:
            if tools.single_email_re.match(self.login):
                self.email = self.login

            if self.is_valid_phone(self.login) and self.partner_id:
                self.partner_id.sudo().write({'phone': self.login})

    def _create_user_from_template(self, values):
        login = values.get('login')
        if login:
            if self.is_valid_phone(login):
                values['phone'] = login
                values['email'] = False  # Evita que se copie al partner.email
            else:
                # Cualquier otro login se trata como email (no se bloquea el registro).
                values['email'] = login
                values['phone'] = False

        return super()._create_user_from_template(values)
