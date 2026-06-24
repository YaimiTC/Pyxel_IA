# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    whatsapp_token = fields.Char(
        string="Access Token", config_parameter="whatsapp_integration.token")
    whatsapp_phone_number_id = fields.Char(
        string="Phone Number ID", config_parameter="whatsapp_integration.phone_number_id")
    whatsapp_business_account_id = fields.Char(
        string="WhatsApp Business Account ID",
        config_parameter="whatsapp_integration.business_account_id")
    whatsapp_api_version = fields.Char(
        string="API Version", default="v19.0",
        config_parameter="whatsapp_integration.api_version")
    whatsapp_verify_token = fields.Char(
        string="Webhook Verify Token", config_parameter="whatsapp_integration.verify_token")
    whatsapp_app_secret = fields.Char(
        string="App Secret (firma webhook)", config_parameter="whatsapp_integration.app_secret")
    whatsapp_webhook_url = fields.Char(string="Webhook URL", compute="_compute_webhook_url")
    # Modo gateway (servidor exterior que media con Meta).
    whatsapp_gateway_url = fields.Char(
        string="Gateway URL", config_parameter="whatsapp_integration.gateway_url",
        help="URL del gateway exterior (ej. https://wa.tudominio.com). Si se define, "
             "Odoo envía a través del gateway y el token vive en el servidor exterior.")
    whatsapp_gateway_api_key = fields.Char(
        string="Gateway API Key", config_parameter="whatsapp_integration.gateway_api_key")

    def _compute_webhook_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        for rec in self:
            rec.whatsapp_webhook_url = base + "/whatsapp/webhook"
