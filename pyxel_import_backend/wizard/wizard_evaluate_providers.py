from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class WizardEvaluateProviders(models.TransientModel):
    _name = 'wizard.evaluate.providers'

    sale_order_id = fields.Many2one('sale.order', required=True)
    apply_supplier_id = fields.Many2one('res.partner', string="Supplier to apply")
    evaluation_line_ids = fields.One2many('wizard.evaluate.providers.line', 'wizard_id')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if len(self.evaluation_line_ids) == 0:
            active_id = self.env.context.get('default_sale_order_id')
            print("Contexto:", self.env.context)
            print("Active ID:", active_id)

            if not active_id:
                print("No active_id, returning empty res")
                return res

            sale_order = self.env['sale.order'].browse(active_id)
            print("sales order:", sale_order.name)
            lines = []
            for line in sale_order.order_line:
                if line.product_id.type in ('consu', 'product') and \
                        line.product_id.qty_available < line.product_uom_qty:
                    print(f"Valid product: {line.product_id.name}, ID: {line.product_id.id}")
                    lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'quantity': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                    }))
            print("Generated lines:", lines)
            if not lines:
                raise ValidationError("There are no products that require supplier evaluation..")
            res.update({
                'sale_order_id': sale_order.id,
                'evaluation_line_ids': lines,
            })
            return res

    def action_confirm(self):
        print("Starting action_confirm")
        print("sales order:", self.sale_order_id.name)
        existing_eval = self.env['purchase.provider.evaluation'].search([
            ('sale_order_id', '=', self.sale_order_id.id),
            ('state', 'in', ['apply']),
        ], limit=1)
        print("Existing evaluation:", existing_eval)
        if existing_eval:
            raise ValidationError('There is already an active evaluation for this quote.')

        valid_lines = self.evaluation_line_ids.filtered(lambda l: l.product_id)
        print("Valid lines:", valid_lines)
        if not valid_lines:
            raise ValidationError("There are no valid lines to evaluate.")

        evaluation = self.env['purchase.provider.evaluation'].create({
            'state': 'evaluated',
            'sale_order_id': self.sale_order_id.id,
            'evaluation_line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.quantity,
                'suggested_supplier_id': line.selected_supplier_id.id,
                'price_unit': line.estimated_price,
            }) for line in valid_lines]
        })
        print("Evaluation created:", evaluation)
        evaluation.action_generate_purchase_orders()
        print("Purchase orders generated")
        return {'type': 'ir.actions.act_window_close'}

    @api.onchange('apply_supplier_id')
    def _onchange_apply_supplier(self):
        """Actualizar las líneas de evaluación con el proveedor seleccionado."""
        if self.apply_supplier_id:
            for line in self.evaluation_line_ids:
                supplier_info = line.product_id.seller_ids.filtered(
                    lambda s: s.partner_id.id == self.apply_supplier_id.id
                )
                if supplier_info:
                    line.selected_supplier_id = self.apply_supplier_id.id
                    line.estimated_price = supplier_info[0].price or 0.0
                else:
                    line.selected_supplier_id = self.apply_supplier_id.id
                    line.estimated_price = 0.0


class WizardEvaluateProvidersLine(models.TransientModel):
    _name = 'wizard.evaluate.providers.line'

    wizard_id = fields.Many2one('wizard.evaluate.providers', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product')
    product_uom = fields.Many2one('uom.uom', string='Unit of measurement')
    quantity = fields.Float(string='Amount')
    available_supplier_ids = fields.Many2one(
        'res.partner', string='Available providers', compute='_compute_suppliers'
    )
    selected_supplier_id = fields.Many2one('res.partner', string='Selected supplier')
    estimated_price = fields.Float(string='Estimated price')

    @api.depends('product_id')
    def _compute_suppliers(self):
        for rec in self:
            supplier_info = rec.product_id.seller_ids[:1]  # Solo el primer proveedor disponible
            if supplier_info:
                rec.available_supplier_ids = supplier_info.partner_id
                rec.estimated_price = supplier_info.price or 0.0
            else:
                rec.available_supplier_ids = False
                rec.estimated_price = 0.0

    @api.onchange('selected_supplier_id')
    def _onchange_selected_supplier_id(self):
        for rec in self:
            if rec.product_id and rec.selected_supplier_id:
                # Buscar si el proveedor seleccionado está entre los seller_ids del producto
                supplier_info = rec.product_id.seller_ids.filtered(
                    lambda s: s.partner_id == rec.selected_supplier_id
                )
                if supplier_info:
                    rec.estimated_price = supplier_info[0].price or 0.0
                else:
                    rec.estimated_price = 0.0
