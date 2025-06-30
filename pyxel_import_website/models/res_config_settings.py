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

    solicitud_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Adjunto de la Plantilla",
        config_parameter="solicitud.attachment_id",
        help="Adjunte aquí la plantilla de la solicitud. "
             "Esta plantilla se utilizará en el formulario de importación."
    )

    ficha_cliente_estatal_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Adjunto de la Plantilla",
        config_parameter="ficha_cliente_estatal.attachment_id",
        help="Adjunte aquí la plantilla de la ficha de clientes estatales. "
             "Esta plantilla se utilizará en el formulario de importación."
    )

    ficha_cliente_fgne_tcp_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Adjunto de la Plantilla",
        config_parameter="ficha_cliente_fgne_tcp.attachment_id",
        help="Adjunte aquí la plantilla de la ficha de clientes FGNE o TCP. "
             "Esta plantilla se utilizará en el formulario de importación."
    )

    cuban_partner_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Adjunto de la Plantilla",
        config_parameter="cuban_partner.attachment_id",
        help="Adjunte aquí la plantilla del socio con nacionalidad cubana. "
             "Esta plantilla se utilizará en el formulario de importación."
    )