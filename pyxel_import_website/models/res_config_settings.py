from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    perfil_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Adjunto de la Plantilla",
        config_parameter="perfil_proveedor.attachment_id",
        help="Adjunte aquí la plantilla del perfil de proveedores. "
             "Esta plantilla se utilizará en el formulario de acreditación."
    )