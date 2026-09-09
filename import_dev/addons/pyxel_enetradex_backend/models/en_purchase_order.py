# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    cert_no_adeudo = fields.Binary(string="Cert. No Adeudo")
    cert_no_adeudo_filename = fields.Char()
    bl_awb_attachment = fields.Binary(string="BL / AWB")
    bl_awb_attachment_filename = fields.Char()
    en_customer_id = fields.Many2one(
        'res.partner', string="Cliente", related='importation_id.customer_id', readonly=True)

    # Cliente real de ESTA OC en operaciones multi-cliente (una OC por
    # cliente, ver en.import.request.client) -- en_customer_id de arriba es
    # legado, related al customer_id unico del proceso, y queda vacio/erroneo
    # cuando hay varios clientes reales; este es el que escribe el wizard.
    customer_id = fields.Many2one('res.partner', string="Cliente (real, por OC)")
    bl_number = fields.Char(string="No. BL / AWB")

    _DEFAULT_ORIGIN_SERVICES = [
        "Alquiler isotanque + lavado", "Descuento", "Entrega estándar",
        "Flete marítimo", "Flete reportación ISO TANQUE", "Gasto FOB",
        "Gastos Asociados", "Gastos de Despacho", "Gastos FOB", "IMO",
        "Impuestos y tasas USA", "Inspección en origen", "ISPSD", "ISPSO",
        "Seguro marítimo", "THCD", "THCDA", "THCO",
    ]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'order_line' in fields_list and self.env.context.get('default_importation_id'):
            line_vals = self._build_default_origin_line_vals()
            if line_vals:
                res['order_line'] = (res.get('order_line') or []) + line_vals
        return res

    def _build_default_origin_line_vals(self):
        Product = self.env['product.product']
        lines = []
        for svc_name in self._DEFAULT_ORIGIN_SERVICES:
            prod = Product.search(
                [('name', '=', svc_name), ('type', '=', 'service')], limit=1)
            if prod:
                lines.append((0, 0, {
                    'product_id': prod.id,
                    'name': prod.display_name,
                    'product_qty': 0.0,
                    'price_unit': 0.0,
                    'product_uom': prod.uom_po_id.id or prod.uom_id.id,
                    'taxes_id': [(6, 0, [])],
                }))
        return lines

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        with_imp = orders.filtered('importation_id')
        if with_imp:
            self.env['pyxel.import.document'].build_oc_expediente(with_imp)
            if not self.env.context.get('en_approval_creating_po'):
                for po in with_imp:
                    existing = set(po.order_line.mapped('product_id.name'))
                    if not any(s in existing for s in self._DEFAULT_ORIGIN_SERVICES):
                        self._add_default_origin_services(po)
        return orders

    def _add_default_origin_services(self, po):
        Product = self.env['product.product']
        POLine = self.env['purchase.order.line']
        for svc_name in self._DEFAULT_ORIGIN_SERVICES:
            prod = Product.search(
                [('name', '=', svc_name), ('type', '=', 'service')], limit=1)
            if prod:
                POLine.create({
                    'order_id': po.id,
                    'product_id': prod.id,
                    'name': prod.display_name,
                    'product_qty': 0.0,
                    'price_unit': 0.0,
                    'product_uom': prod.uom_po_id.id or prod.uom_id.id,
                    'taxes_id': [(6, 0, [])],
                })

    def write(self, vals):
        res = super().write(vals)
        if vals.get('importation_id'):
            self.env['pyxel.import.document'].build_oc_expediente(self.filtered('importation_id'))
        return res
