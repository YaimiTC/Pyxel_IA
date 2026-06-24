# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Eventos de negocio que pueden disparar una plantilla.
EVENTS = [
    ("manual", "Manual / por defecto"),
    ("sale_confirm", "Pedido de venta confirmado"),
    ("invoice_posted", "Factura publicada"),
    ("payment_reminder", "Recordatorio de pago"),
    ("delivery_done", "Entrega realizada"),
    ("partner_created", "Contacto creado"),
]


class WhatsappTemplateMapping(models.Model):
    """Relaciona un evento de Odoo con una plantilla pre-aprobada de Meta y
    define cómo se rellenan sus variables desde campos del registro."""
    _name = "whatsapp.template.mapping"
    _description = "WhatsApp Template Mapping"
    _order = "event, sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    event = fields.Selection(EVENTS, required=True, default="manual",
                             help="Evento de Odoo que dispara esta plantilla.")
    model_id = fields.Many2one(
        "ir.model", string="Modelo origen", ondelete="cascade",
        help="Modelo del registro que origina el mensaje (sale.order, account.move...).")
    template_name = fields.Char(
        required=True, help="Nombre EXACTO de la plantilla aprobada en Meta.")
    lang_code = fields.Char(string="Idioma", default="es",
                            help="Código de idioma de la plantilla (es, en_US...).")
    category = fields.Selection(
        [("utility", "Utility"), ("marketing", "Marketing"),
         ("authentication", "Authentication")],
        default="utility", required=True)
    is_default = fields.Boolean(
        string="Por defecto", help="Se usa como respaldo cuando no hay otra plantilla para el evento.")
    variable_ids = fields.One2many(
        "whatsapp.template.variable", "mapping_id", string="Variables ({{1}}, {{2}}...)")
    note = fields.Char(string="Notas")

    @api.model
    def _find(self, event, model_name=False):
        """Busca el mapeo para un evento (y opcionalmente un modelo); si no hay,
        cae al mapeo marcado por defecto del evento."""
        domain = [("event", "=", event)]
        if model_name:
            mdl = self.env["ir.model"]._get(model_name)
            mp = self.search(domain + [("model_id", "=", mdl.id)], limit=1)
            if mp:
                return mp
        mp = self.search(domain, limit=1)
        if mp:
            return mp
        return self.search([("is_default", "=", True)], limit=1)

    def build_components(self, record):
        """Construye los 'components' de la plantilla resolviendo las variables
        del cuerpo desde los campos del registro."""
        self.ensure_one()
        params = []
        for var in self.variable_ids.sorted("sequence"):
            params.append({"type": "text", "text": var._resolve(record)})
        if not params:
            return []
        return [{"type": "body", "parameters": params}]


class WhatsappTemplateVariable(models.Model):
    """Una variable del cuerpo de la plantilla ({{1}}, {{2}}...) mapeada a un
    campo (puede ser una ruta con puntos: partner_id.name)."""
    _name = "whatsapp.template.variable"
    _description = "WhatsApp Template Variable"
    _order = "sequence, id"

    mapping_id = fields.Many2one("whatsapp.template.mapping", required=True, ondelete="cascade")
    sequence = fields.Integer(default=1, help="Posición de la variable ({{1}}, {{2}}...).")
    field_path = fields.Char(
        required=True, help="Ruta del campo en el registro, p.ej. 'name' o 'partner_id.name'.")
    fallback = fields.Char(string="Valor por defecto", default="")

    def _resolve(self, record):
        self.ensure_one()
        try:
            val = record
            for part in (self.field_path or "").split("."):
                if not part:
                    continue
                val = val[part] if isinstance(val, dict) else getattr(val, part)
            if val in (False, None):
                return self.fallback or ""
            return str(val)
        except Exception:
            return self.fallback or ""
