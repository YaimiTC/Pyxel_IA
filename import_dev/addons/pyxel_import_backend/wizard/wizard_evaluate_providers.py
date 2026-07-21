from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class WizardEvaluateProviders(models.TransientModel):
    _name = 'wizard.evaluate.providers'

    sale_order_id = fields.Many2one('sale.order', required=True)
    apply_supplier_id = fields.Many2one('res.partner', string="Supplier to apply",
                                        domain="[('contact_type_id.type_of_contact', '=', 'Supplier'), "
                                               "('is_accredited', '=', True)]")
    evaluation_line_ids = fields.One2many('wizard.evaluate.providers.line', 'wizard_id')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('default_sale_order_id')

        if not active_id:
            return res

        sale_order = self.env['sale.order'].browse(active_id)
        lines = []
        for line in sale_order.order_line:
            if line.product_id.type in ('consu', 'product') and \
                    line.product_id.qty_available < line.product_uom_qty:
                # Obtener el precio estimado desde el primer proveedor del producto
                supplier_info = line.product_id.seller_ids[:1]
                estimated_price = supplier_info.price if supplier_info else 0.0
                lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'estimated_price': estimated_price
                }))

        if not lines:
            raise ValidationError("There are no products that require supplier evaluation.")

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

        # 🔒 Asegura que todos los registros estén cargados correctamente
        self.ensure_one()
        self.evaluation_line_ids._compute_suppliers()

        valid_lines = self.evaluation_line_ids.filtered(lambda l: isinstance(l, models.BaseModel) and l.product_id)
        print("Valid lines:", valid_lines)

        if not valid_lines:
            raise ValidationError("There are no valid lines to evaluate.")

        evaluation_lines = []
        for line in valid_lines:
            price = line.estimated_price or 0.0
            print(
                f"Line for product {line.product_id.name}, supplier: {line.selected_supplier_id.name}, price: {price}")
            evaluation_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.quantity,
                'suggested_supplier_id': line.selected_supplier_id.id,
                'price_unit': price,
            }))

        evaluation = self.env['purchase.provider.evaluation'].create({
            'state': 'evaluated',
            'sale_order_id': self.sale_order_id.id,
            'evaluation_line_ids': evaluation_lines,
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
    selected_supplier_id = fields.Many2one('res.partner', string='Selected supplier',
                                           domain="[('contact_type_id.code', '=', 'proveedor_extranjero')]")
    estimated_price = fields.Float(string='Estimated price')

    @api.depends('product_id')
    def _compute_suppliers(self):
        for rec in self:
            supplier_info = rec.product_id.seller_ids[:1]  # Solo el primer proveedor disponible
            if supplier_info:
                rec.available_supplier_ids = supplier_info.partner_id
                # rec.estimated_price = supplier_info.price or 0.0
            else:
                rec.available_supplier_ids = False
                # rec.estimated_price = 0.0

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
