from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # TCM Block
    email_from = fields.Char(string='From', config_parameter='email_from')
    notification_emails = fields.Char(string='To', config_parameter='notification_emails')
    outgoing_mail_server_id = fields.Many2one(
        comodel_name='ir.mail_server',
        string='Outgoing Mail Server',
        config_parameter='outgoing_mail_server_id')

    # Contracts Block
    contract_outgoing_mail_server_id = fields.Many2one(
        comodel_name='ir.mail_server',
        string='Outgoing Mail Server for contracts',
        config_parameter='contract_outgoing_mail_server_id')

    salespersons_emails = fields.Char(string='Salespersons emails', config_parameter='salespersons_emails')

    days_until_expiration = fields.Integer(string='Days Until Expiration', config_parameter='days_until_expiration',
                                           default=5)
    # Containers Block
    containers_outgoing_mail_server_id = fields.Many2one(
        comodel_name='ir.mail_server',
        string='Outgoing Mail Server for contrainers',
        config_parameter='containers_outgoing_mail_server_id')

    containers_salespersons_emails = fields.Char(string='Salespersons emails',
                                                 config_parameter='containers_salespersons_emails')

    perfil_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Adjunto de la Plantilla",
        config_parameter="perfil_proveedor.attachment_id",
        help="Adjunte aquí la plantilla del perfil de proveedores. "
             "Esta plantilla se utilizará en el formulario de acreditación."
    )