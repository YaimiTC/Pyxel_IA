from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_type = fields.Selection(
        selection=[
            ("import_service", "Servicios de importación"),
            ("tariff_service", "Aranceles y servicios"),
            ("other_costs", "Otros gastos"),
        ],
        string="Invoice type",
        default="other_costs",
        copy=False,
        tracking=True,
        help="Clasificación para conciliación. Solo 'Servicios de importación' se reporta en la conciliación.",
    )

    importation_process_id = fields.Many2one(
        'importation.process',
        string="Import process"
    )

    container_ids = fields.One2many(
        related='importation_process_id.load_tracking_ids',
        string='Containers',
        readonly=True
    )

    container_names = fields.Char(
        string="Containers",
        compute='_compute_container_names',
        store=True
    )

    @api.depends('importation_process_id.load_tracking_ids.name')
    def _compute_container_names(self):
        for record in self:
            containers = record.importation_process_id.load_tracking_ids
            record.container_names = ', '.join(containers.mapped('name')) if containers else ''

    @api.model
    def default_get(self, fields_list):
        """
        Default inteligente:
        - Si la factura se crea desde un SO en contexto (active_model='sale.order')
          y el SO tiene order_type='importation_process' => import_service
        - En cualquier otro caso => other_costs
        """
        res = super().default_get(fields_list)

        # Solo aplica para facturas de cliente (opcional, si quieres limitarlo)
        move_type = res.get("move_type") or self.env.context.get("default_move_type")
        if move_type and move_type not in ("out_invoice", "out_refund"):
            return res

        if "invoice_type" not in fields_list:
            return res

        ctx = self.env.context
        if ctx.get("active_model") == "sale.order" and ctx.get("active_id"):
            so = self.env["sale.order"].browse(ctx["active_id"])
            if so and so.exists():
                if getattr(so, "order_type", "ordinary") == "importation_process":
                    res["invoice_type"] = "import_service"
                else:
                    # cualquier otro SO => other_costs
                    res["invoice_type"] = "other_costs"

        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    is_cost_special = fields.Boolean(string="Special Cost", default=False)
