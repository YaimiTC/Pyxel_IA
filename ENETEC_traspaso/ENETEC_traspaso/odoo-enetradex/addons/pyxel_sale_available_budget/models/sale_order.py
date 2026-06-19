from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    available_budget = fields.Monetary(
        string='Budget available',
        help='Amount of money the customer has available for this order.',
    )

    # process_id: se asume que ya existe en sale.order

    # ---- Creación: si ya viene con proceso, intenta copiar presupuesto de hermanas
    @api.model
    def create(self, vals):
        order = super().create(vals)
        if order.process_id:
            order._sync_budget_from_process()
        return order

    # ---- Escritura: propagar cambios y/o sincronizar al cambiar de proceso
    def write(self, vals):
        res = super().write(vals)

        # Si cambió el proceso, intentamos tomar budget de una hermana
        if 'process_id' in vals:
            for order in self.filtered('process_id'):
                order._sync_budget_from_process()

        # Si cambió el budget aquí, replicarlo a las demás SO del mismo proceso
        # (evitamos bucle con un flag en el context)
        if 'available_budget' in vals and not self.env.context.get('_skip_budget_broadcast'):
            for order in self.filtered('process_id'):
                siblings = order.process_id.sale_order_ids - order
                if siblings:
                    siblings.with_context(_skip_budget_broadcast=True).write({
                        'available_budget': order.available_budget
                    })

        return res

    # ---- Onchange: al modificar el budget en pantalla, empuja a hermanas (DB) para feedback inmediato
    @api.onchange('available_budget')
    def _onchange_available_budget_broadcast(self):
        for order in self.filtered('process_id'):
            siblings = order.process_id.sale_order_ids - order
            if siblings:
                siblings.with_context(_skip_budget_broadcast=True).write({
                    'available_budget': order.available_budget
                })

    # (Opcional) Onchange de proceso: si eliges un proceso y esta SO no tiene budget,
    # intenta copiar el de una hermana con budget ya definido.
    @api.onchange('process_id')
    def _onchange_process_id_sync_budget(self):
        for order in self:
            if order.process_id and not order.available_budget:
                other = order.process_id.sale_order_ids.filtered(
                    lambda so: so.id != order.id and so.available_budget
                )[:1]
                if other:
                    order.available_budget = other.available_budget

    # ---- Utilidad: toma el budget desde otra SO del mismo proceso si esta no tiene
    def _sync_budget_from_process(self):
        self.ensure_one()
        if not self.process_id:
            return
        if self.available_budget:
            return  # ya tiene; no pisar
        other = self.process_id.sale_order_ids.filtered(
            lambda so: so.id != self.id and so.available_budget
        )[:1]
        if other:
            self.available_budget = other.available_budget
