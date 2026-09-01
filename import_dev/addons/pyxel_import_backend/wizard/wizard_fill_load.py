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
        """Llena las líneas del contenedor según las órdenes de compra seleccionadas."""
        self.ensure_one()
        load = self.load_id

        if load.cargo_line_ids:
            raise UserError(
                "Este contenedor ya tiene líneas asignadas. "
                "Elimínelas primero si desea rellenar desde cero."
            )

        purchase_orders = self.purchase_order_ids
        if not purchase_orders:
            raise UserError("Debe seleccionar al menos una orden de compra.")

        load_lines = []
        for purchase_order in purchase_orders:
            for line in purchase_order.order_line:
                qty = line.quantity_available
                if qty > 0.001:
                    load_lines.append((0, 0, {
                        'cargo_id': load.id,
                        'purchase_order_line_id': line.id,
                        'product_id': line.product_id.id,
                        'quantity': qty,
                        'price': line.price_unit,
                    }))

        if not load_lines:
            raise UserError(
                "No hay cantidad disponible para asignar a este contenedor. "
                "Compruebe que los contenedores anteriores no tienen el 100% de cada línea asignado."
            )

        load.write({'cargo_line_ids': load_lines})

        # Propagar datos de las OC seleccionadas a la carga si aún no están fijados.
        update_vals = {}
        if not load.customer_id:
            customers = purchase_orders.mapped('customer_id').filtered('id')
            if customers:
                update_vals['customer_id'] = customers[0].id
        if not load.provider_ids:
            providers = purchase_orders.mapped('partner_id').filtered('id')
            if providers:
                update_vals['provider_ids'] = [(6, 0, providers.ids)]
        if not load.supplier_invoice_number:
            refs = [r for r in purchase_orders.mapped('partner_ref') if r]
            if refs:
                update_vals['supplier_invoice_number'] = refs[0]
        if not load.packaging_type_id and load.importation_id:
            pkg = load.importation_id.packaging_type_id
            if pkg:
                update_vals['packaging_type_id'] = pkg.id
        if update_vals:
            load.write(update_vals)

        # Verificar si quedan cantidades sin asignar en alguna OC de la importación
        pendientes = []
        if load.importation_id:
            for po in load.importation_id.purchase_order_ids:
                for line in po.order_line:
                    if line.display_type:
                        continue
                    remaining = line.quantity_available
                    if remaining > 0.001:
                        pendientes.append(
                            f"{po.name} / {line.product_id.display_name}: "
                            f"{remaining:,.2f} {line.product_uom.name or ''} pendientes"
                        )

        if pendientes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cantidad pendiente de asignar',
                    'message': 'Aún quedan cantidades sin contenedor:\n' + '\n'.join(pendientes),
                    'type': 'warning',
                    'sticky': True,
                },
            }

        return {'type': 'ir.actions.act_window_close'}
