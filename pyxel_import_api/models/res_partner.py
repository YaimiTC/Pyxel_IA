from odoo import fields, models, api, _


class Users(models.Model):
    _inherit = 'res.users'

    access_token = fields.Char(string='Access Token')


class Partner(models.Model):
    _inherit = 'res.partner'

    access_token = fields.Char(string='Access Token')

    def generate_token(self):
        self.ensure_one()
        access_token = self.env['res.users.apikeys']._generate(None, 'Access Token Auth')
        self.write({'access_token': access_token})
        for user in self.user_ids:
            user.write({'access_token': access_token})
