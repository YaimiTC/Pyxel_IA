from odoo import models, fields, api, _
from collections import defaultdict
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class PurchaseProviderEvaluation(models.Model):
    _name = 'purchase.provider.evaluation'
    _description = 'Evaluación de Proveedores'

    name = fields.Char(string="Referencia", required=True, default='/')
    sale_order_id = fields.Many2one('sale.order', string='Presupuesto')
    evaluation_line_ids = fields.One2many('purchase.provider.evaluation.line', 'evaluation_id',
                                          string='Líneas de evaluación')

    purchase_order_ids = fields.One2many(
        'purchase.order',
        'evaluation_id',
        string='Órdenes de compra'
    )

    has_evaluations_to_apply = fields.Boolean(
        compute='_compute_has_evaluations_to_apply',
        string='Tiene evaluaciones aplicables'
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('evaluated', 'Evaluado'),
        ('po_created', 'Órdenes Generadas'),
        ('cancelled', 'Cancelado'),
        ('apply', 'Aplicada'),
        ('evaluating_offer', 'Evaluacion Oferta'),
    ], default='draft', string='Estado')

    purchase_order_count = fields.Integer(string="Cantidad de Órdenes", compute='_compute_purchase_order_count',
                                          store=True)

    cost_line_temp_ids = fields.One2many('purchase.provider.evaluation.cost.line', 'evaluation_id',
                                         string='Costos adicionales')

    final_sale_order_id = fields.Many2one('sale.order', string='Oferta Final Generada', readonly=True)

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for record in self:
            record.purchase_order_count = len(record.purchase_order_ids)

    def action_generate_purchase_orders(self):
        """Genera órdenes de compra por proveedor basado en la evaluación."""
        PurchaseOrder = self.env['purchase.order']
        grouped_lines = defaultdict(list)

        # Agrupar por proveedor
        for line in self.evaluation_line_ids:
            if not line.suggested_supplier_id:
                raise ValidationError(f'No se ha definido proveedor para el producto {line.product_id.display_name}')
            grouped_lines[line.suggested_supplier_id].append(line)

        created_pos = []

        for supplier, lines in grouped_lines.items():
            po = PurchaseOrder.create({
                'partner_id': supplier.id,
                'sale_order_id': self.sale_order_id.id,
                'evaluation_id': self.id,
                'order_line': [(0, 0, {
                    'product_id': line.product_id.id,
                    'product_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'price_unit': line.price_unit or 0.0,
                    'date_planned': fields.Date.today(),
                    'sale_order_line_id': line.sale_order_line_id.id,
                    'name': line.product_id.name,
                }) for line in lines],
            })
            created_pos.append(po)
            self.state = 'po_created'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Órdenes de Compra Generadas',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', [po.id for po in created_pos])],
        }

    @api.depends('purchase_order_ids.state')
    def _compute_has_evaluations_to_apply(self):
        for evaluation in self:
            # Si alguna orden está en estado diferente a 'draft' o 'cancel', entonces se puede aplicar
            evaluation.has_evaluations_to_apply = any(
                po.state not in ('draft', 'cancel') for po in evaluation.purchase_order_ids
            )

    def _check_apply_status(self):
        for evaluation in self:
            if evaluation.state != 'apply':
                # Si alguna de las órdenes generadas por esta evaluación está en estado 'done'
                related_orders = self.env['purchase.order'].search([
                    ('evaluation_id', '=', evaluation.id),
                    ('state', '=', 'done')
                ])
                if related_orders:
                    evaluation.state = 'apply'

    @api.depends('purchase_order_ids')
    def _compute_state(self):
        for rec in self:
            if not rec.purchase_order_ids:
                rec.state = 'draft'

    def unlink(self):
        for record in self:
            # Solo se permite si está en estado 'draft' o 'cancel'
            if record.state not in ['draft', 'cancelled']:
                raise ValidationError(_("Solo se pueden eliminar evaluaciones en estado Borrador o Cancelado."))

            # Verifica si todas las órdenes están canceladas o no hay órdenes
            if record.purchase_order_ids:
                if any(p.state != 'cancel' for p in record.purchase_order_ids):
                    raise ValidationError(_("Todas las órdenes deben estar canceladas para eliminar esta evaluación."))

        return super(PurchaseProviderEvaluation, self).unlink()

    def action_revaluate(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("Solo puedes reevaluar evaluaciones en estado borrador."))
            if record.purchase_order_ids:
                raise ValidationError(_("Esta evaluación ya tiene órdenes asociadas."))

            # Aquí iría tu lógica para regenerar las órdenes
            record.action_generate_purchase_orders()

    @api.model
    def create(self, vals):
        sale_order_id = vals.get('sale_order_id')
        if sale_order_id:
            existing = self.search([
                ('sale_order_id', '=', sale_order_id),
                ('state', '=', 'apply'),
            ], limit=1)
            if existing:
                raise ValidationError("Ya existe una evaluación aplicada para este pedido de venta. No se puede crear "
                                      "otra.")
        if vals.get('name', '/') == '/':
            sale_order = self.env['sale.order'].browse(vals.get('sale_order_id'))
            if not sale_order:
                raise ValidationError("Se requiere un presupuesto (sale.order) para generar la secuencia.")

            # Cambiar el tipo del sale.order a inicial_evaluacion
            sale_order.order_type = 'evaluation_initial'
            sale_order_ref = sale_order.name
            # Contar cuántas evaluaciones existen ya para este sale_order
            count = self.search_count([('sale_order_id', '=', sale_order.id)]) + 1
            vals['name'] = f"EVAL/{sale_order_ref}/{count:02d}"
        return super().create(vals)

    def copy(self, default=None):
        self.ensure_one()
        if self.sale_order_id:
            existing = self.search([
                ('sale_order_id', '=', self.sale_order_id.id),
                ('state', '=', 'apply'),
                ('id', '!=', self.id),
            ], limit=1)
            if existing:
                raise ValidationError("Ya existe una evaluación aplicada para este pedido de venta. No se puede "
                                      "duplicar.")
        return super().copy(default)

    def action_generate_eval_offer(self):
        self.ensure_one()
        if self.final_sale_order_id:
            raise ValidationError("Ya se ha generado la Oferta Final para este proceso.")

        # Cliente del presupuesto original
        partner = self.sale_order_id.partner_id

        # Crear nuevo pedido de venta
        final_so = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_type': 'evaluation_final',
            'evaluation_apply_id': self.id,
            'origin': self.name,
            'opportunity_id': self.sale_order_id.opportunity_id.id,
            'order_line': []
        })

        order_lines = []

        # Agregar líneas con stock del presupuesto original
        for line in self.sale_order_id.order_line:
            if line.product_id.qty_available >= line.product_uom_qty:
                order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'price_unit': line.price_unit,
                    'name': line.name,
                }))

        # Agregar productos importados desde las órdenes de compra
        for po in self.purchase_order_ids:
            for po_line in po.order_line:
                order_lines.append((0, 0, {
                    'product_id': po_line.product_id.id,
                    'product_uom_qty': po_line.product_qty,
                    'product_uom': po_line.product_uom.id,
                    'price_unit': po_line.price_unit,
                    'name': f"Importado desde OC {po.name}",
                }))

        # Agregar costos adicionales consolidados
        for cost_line in self.cost_line_temp_ids:
            # Sumamos el valor real del costo si es porcentaje, distribuyéndolo
            amount = cost_line.amount
            if cost_line.distribution_type == 'percentage':
                amount = sum((po.amount_total * (cost_line.amount / 100)) for po in self.purchase_order_ids)
            order_lines.append((0, 0, {
                'product_id': cost_line.product_id.id,
                'name': f"Costo adicional: {cost_line.name}",
                'product_uom_qty': 1,
                'product_uom':  cost_line.product_id.uom_id.id,
                'price_unit': amount,

            }))

        # Escribir las líneas
        final_so.write({'order_line': order_lines})
        self.final_sale_order_id = final_so.id
        self.state = "evaluating_offer"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': final_so.id,
            'target': 'current',
        }


class PurchaseProviderEvaluationLine(models.Model):
    _name = 'purchase.provider.evaluation.line'
    _description = 'Evaluación de proveedor por producto'

    evaluation_id = fields.Many2one('purchase.provider.evaluation', string='Evaluación')
    sale_order_line_id = fields.Many2one('sale.order.line', string='Línea de presupuesto')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    product_uom_qty = fields.Float(string='Cantidad', required=True)
    product_uom = fields.Many2one('uom.uom', string='Unidad de medida', required=True)
    price_unit = fields.Float(string='Precio estimado')  # Este se usará en la orden de compra

    suggested_supplier_id = fields.Many2one('res.partner', string='Proveedor sugerido')
    supplier_ids = fields.Many2many('res.partner', string='Proveedores disponibles', compute='_compute_suppliers',
                                    store=False)

    @api.depends('product_id')
    def _compute_suppliers(self):
        for rec in self:
            rec.supplier_ids = rec.product_id.seller_ids.mapped('partner_id')


class EvaluationCostLine(models.Model):
    _name = 'purchase.provider.evaluation.cost.line'
    _description = 'Costo adicional temporal'

    evaluation_id = fields.Many2one('purchase.provider.evaluation', ondelete='cascade')
    product_id = fields.Many2one(
        'product.product',
        string='Servicio',
        domain=[('detailed_type', '=', 'service')],
        required=True
    )
    name = fields.Char(compute='_compute_name', required=True)
    amount = fields.Float(required=True)
    distribution_type = fields.Selection([
        ('fixed', 'Monto Fijo'),
        ('percentage', 'Porcentaje'),
    ], required=True)
    is_cost_special = fields.Boolean()

    @api.depends('product_id')
    def _compute_name(self):
        for record in self:
            record.name = record.product_id.display_name or ''

