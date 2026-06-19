import os
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

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

    load_products_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Adjunto de la Plantilla",
        config_parameter="load_products.attachment_id",
        help="Adjunte aquí la plantilla de la carga de productos. "
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

    @api.constrains('load_products_attachment_id')
    def _check_load_products_attachment_id(self):
        for record in self:
            if record.load_products_attachment_id:
                allowed_extensions = ['.xlsx']
                allowed_mimetypes = [
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ]
                
                filename = record.load_products_attachment_id.name or ''
                extension = os.path.splitext(filename)[1].lower()
                mimetype = record.load_products_attachment_id.mimetype or ''
                
                if (extension not in allowed_extensions and 
                    mimetype not in allowed_mimetypes):
                    raise ValidationError(
                        _('La plantilla de la Carga de productos sólo puede ser de tipo Excel (.xlsx)')
                    )
