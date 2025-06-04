from odoo import models, fields, api
from odoo.exceptions import UserError


class ContainerFillWizard(models.TransientModel):
    _name = 'importation_load_fill_wizard'
    _description = 'Wizard to fill container lines'

    load_id = fields.Many2one('importation.load', string="Load", required=True)

    purchase_order_ids = fields.Many2many(
        'purchase.order',
        string='Órdenes de compra',
        domain="[('id', 'in', available_purchase_order_ids)]"
    )
    available_purchase_order_ids = fields.Many2many(
        'purchase.order',
        compute='_compute_available_purchase_order_ids',
        store=False
    )

    @api.depends('load_id')
    def _compute_available_purchase_order_ids(self):
        for wizard in self:
            if wizard.load_id and wizard.load_id.importation_id:
                wizard.available_purchase_order_ids = wizard.load_id.importation_id.purchase_order_ids.ids
            else:
                wizard.available_purchase_order_ids = []

    @api.onchange('load_id')
    def _onchange_container_id(self):
        if self.load_id and self.load_id.importation_id:
            self.purchase_order_ids = self.load_id.importation_id.purchase_order_ids
        else:
            self.purchase_order_ids = [(5, 0, 0)]

    def action_fill_load_lines(self):
        """Llena las líneas del contenedor según las órdenes de compra seleccionadas"""
        self.ensure_one()
        load = self.load_id

        # Verificar si el contenedor ya tiene líneas asociadas
        if load.cargo_line_ids:
            raise UserError("This container already has lines associated with it")

        # Validar órdenes seleccionadas
        purchase_orders = self.purchase_order_ids
        if not purchase_orders:
            raise UserError("You must select at least one purchase order.")

        load_lines = []
        for purchase_order in purchase_orders:
            for line in purchase_order.order_line:
                if line.quantity_available > 0:
                    quantity_to_add = min(line.quantity_available, line.product_qty)
                    load_lines.append((0, 0, {
                        'cargo_id': load.id,
                        'purchase_order_line_id': line.id,
                        'product_id': line.product_id.id,
                        'quantity': quantity_to_add,
                        'price': line.price_unit,
                    }))

        if not load_lines:
            raise UserError("There are no valid lines to add to the container.")

        load.write({'cargo_line_ids': load_lines})
        return {'type': 'ir.actions.act_window_close'}
