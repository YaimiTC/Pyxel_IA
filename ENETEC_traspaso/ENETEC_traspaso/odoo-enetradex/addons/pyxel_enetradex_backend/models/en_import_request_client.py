# -*- coding: utf-8 -*-
from odoo import models, fields, api


class EnImportRequestClient(models.Model):
    """Bloque de cliente dentro de una solicitud de importación.
    Un proveedor puede registrar varios clientes por envío; un cliente
    solo registra el suyo propio."""
    _name = 'en.import.request.client'
    _description = "Cliente de solicitud de importación"
    _order = 'sequence, id'

    process_id = fields.Many2one(
        'importation.process', string="Solicitud", required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)

    customer_id = fields.Many2one(
        'res.partner', string="Cliente", required=True,
        domain="[('contact_type_id.type_of_contact', '=', 'Client')]")
    is_accredited = fields.Boolean(
        related='customer_id.is_accredited', string="Acreditado", readonly=True)
    customer_contact_id = fields.Many2one(
        'res.partner', string="Contacto de la empresa",
        domain="[('parent_id', '=', customer_id), ('type', '=', 'contact')]")

    bl_number = fields.Char(string="No. BL / AWB")

    # Productos solicitados para este cliente
    product_line_ids = fields.One2many(
        'en.import.request.client.line', 'client_block_id', string="Productos")

    # Documentos específicos de este cliente (CRUD completo)
    document_ids = fields.One2many(
        'en.import.request.document', 'client_block_id', string="Documentos")

    # Condiciones comerciales de este cliente
    en_delivery_date = fields.Date(string="Fecha de entrega deseada")
    en_payment_method_id = fields.Many2one('en.payment.method', string="Forma de pago")
    en_currency_usd_id = fields.Many2one(
        'res.currency', string="Moneda (USD)", readonly=True,
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))
    en_budget_usd = fields.Monetary(
        string="Presupuesto disponible (USD)", currency_field='en_currency_usd_id')
    en_operation_currency_id = fields.Many2one(
        'res.currency', string="Moneda de la operación",
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))
    en_margin_percent = fields.Float(string="Margen ENETEC (%)")
    en_specifications = fields.Text(string="Especificaciones")
    en_observations = fields.Text(string="Observaciones")

    # OC y OV generadas al aprobar (solo lectura)
    purchase_order_id = fields.Many2one(
        'purchase.order', string="Orden de compra", readonly=True, copy=False)
    sale_order_id = fields.Many2one(
        'sale.order', string="Oferta de venta", readonly=True, copy=False)

    def name_get(self):
        res = []
        for rec in self:
            label = rec.customer_id.display_name or '—'
            res.append((rec.id, label))
        return res


class EnImportRequestClientLine(models.Model):
    """Línea de producto dentro de un bloque de cliente."""
    _name = 'en.import.request.client.line'
    _description = "Línea de producto por cliente en solicitud"
    _order = 'sequence, id'

    client_block_id = fields.Many2one(
        'en.import.request.client', string="Bloque cliente",
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string="Producto")
    product_name = fields.Char(string="Producto (texto)")
    qty = fields.Float(string="Cantidad")
    # Campo intermedio de un solo salto: el dominio del campo de abajo no puede
    # resolver de forma confiable una cadena de dos relaciones
    # (product_id.uom_id.category_id) en el navegador.
    product_uom_category_id = fields.Many2one(
        'uom.category', related='product_id.uom_id.category_id', string="Categoría UdM")
    # Litro/Galón (US): categoría Volumen (id 6) restringida a esas 2 unidades.
    product_uom_id = fields.Many2one(
        'uom.uom', string="Unidad de medida",
        domain="['&', ('category_id', '=', product_uom_category_id), '|', ('category_id', '!=', 6), ('id', 'in', [11, 25])]")
    packaging = fields.Selection(
        [('isotanque', 'Isotanque'), ('isomodulo', 'Isomódulo')],
        string="Tipo de envase")

    @api.onchange('product_id')
    def _onchange_product_id_uom(self):
        for rec in self:
            if rec.product_id and not rec.product_uom_id:
                rec.product_uom_id = rec.product_id.uom_id
