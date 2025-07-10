from odoo import fields, models, api


class Partner(models.Model):
    _inherit = "res.partner"

    website_size_x = fields.Integer("Size X", default=1)
    website_size_y = fields.Integer("Size Y", default=1)
    website_ribbon_id = fields.Many2one("product.ribbon", string="Ribbon")
    is_fx_published = fields.Boolean(string="Published")
    profile_banner = fields.Binary(string="Profile Banner", copy=False)

    # x_studio_note = fields.Text(string="Product Required")
    # x_name = fields.Text(string="Name Product Required")

    