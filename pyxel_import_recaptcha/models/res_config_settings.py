from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    recaptcha_site_key = fields.Char(
        string="reCAPTCHA Site Key",
        config_parameter='recaptcha.site_key',
        help="Clave pública proporcionada por Google para reCAPTCHA."
    )
    recaptcha_secret_key = fields.Char(
        string="reCAPTCHA Secret Key",
        config_parameter='recaptcha.secret_key',
        help="Clave secreta proporcionada por Google para la validación del reCAPTCHA."
    )
