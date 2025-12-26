import datetime
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_id = fields.Many2one(
        domain="[('contact_type_id.type_of_contact', '=', 'Client'), ('is_accredited', '=', True)]",
    )

    purchase_order_count = fields.Integer(string="Purchase Orders", compute='_compute_purchase_order_count')
    provider_names = fields.Char(string="Providers", compute="_compute_purchase_order_name")
    invoice_names = fields.Char(string='Invoices', compute='_compute_invoice_names')

    purchase_provider_evaluation_ids = fields.One2many('purchase.provider.evaluation', 'sale_order_id')

    purchase_evaluation_count = fields.Integer(string="Evaluations", compute='_compute_purchase_evaluation_count')

    evaluation_apply_id = fields.Many2one('purchase.provider.evaluation', string='Applied Evaluation')

    has_applicable_evaluations = fields.Boolean(
        string='Has Applicable Evaluations',
        compute='_compute_has_applicable_evaluations'
    )

    order_type = fields.Selection([
        ('ordinary', 'Ordinary'),
        ('evaluation_initial', 'Initial Evaluation'),
        ('evaluation_final', 'Final Evaluation'),
        ('importation_process', 'Importation Process')
    ], string='Order Type', default='ordinary')

    importation_process_id = fields.Many2one(
        'importation.process',
        string='Importation Process',
        readonly=True,
        help='Importation process generated from this evaluation.'
    )

    # Campo para año de importación (relacionado con el proceso)
    import_year = fields.Char(
        string="Año Importación",
        compute='_compute_import_year',
        store=True
    )

    @api.depends('importation_process_id')
    def _compute_import_year(self):
        for order in self:
            if order.importation_process_id and order.importation_process_id.estimated_start_date:
                order.import_year = order.importation_process_id.estimated_start_date.strftime('%y')
            else:
                order.import_year = False

    is_third_party_contract = fields.Boolean(
        string='Third-Party Contract',
        related='importation_process_id.is_third_party_contract',
        store=True,
        readonly=False  # Solo si quieres permitir editar desde el sale.order
    )

    contract_reference_customer = fields.Char(
        string='Customer Contract Reference',
        help='Reference of the contract between the customer and the importer'
    )

    contract_reference_supplier = fields.Char(
        string='Supplier Contract Reference',
        help='Reference of the contract between the supplier and the importer'
    )

    @api.depends('purchase_provider_evaluation_ids.has_evaluations_to_apply')
    def _compute_has_applicable_evaluations(self):
        for order in self:
            order.has_applicable_evaluations = any(
                ev.has_evaluations_to_apply for ev in order.purchase_provider_evaluation_ids
            )

    process_id = fields.Many2one("sale.order.process", string="Secuencia", ondelete="set null", index=True)

    @api.onchange('import_progress_id')
    def _check_importation_and_close_process(self):
        for order in self:
            if order.import_progress_id and order.process_id:
                order.process_id.state = 'closed'

    def action_initial_process_importation(self):

        if self.order_type != 'evaluation_final':
            raise UserError(_("La orden debe ser dfe tipo 'Evaluación Final' para iniciar la importación."))

        if not (
                self.contract_reference_customer and self.contract_reference_supplier
        ):
            raise UserError(_(
                "Debe definir al menos una referencia de contrato (cliente o proveedor) para iniciar la importación."
            ))
        provider = self.evaluation_apply_id.purchase_order_ids[0].partner_id

        # 🔒 Validación controlada del país de origen
        if not provider.country_id:
            raise UserError("El proveedor seleccionado no tiene definido un país de origen.\nPor favor, complete este"
                            " dato antes de iniciar el proceso de importación.")
            
        incoterms = self.evaluation_apply_id.purchase_order_ids.mapped('incoterm_id')
        if len(set(incoterms)) > 1:
            raise UserError(_("Todas las órdenes de compra deben tener el mismo Incoterm para iniciar el proceso de importación."))
        
        incoterm = incoterms[0] if incoterms else False

        cost_lines = [(0, 0, {
            'product_id': line.product_id.id,
            'name': line.name,
            'amount': line.amount,
            'purchase_ids': [(6, 0, self.evaluation_apply_id.purchase_order_ids.ids)],
            'distribution_type': line.distribution_type,
            'is_cost_special': line.is_cost_special,
        }) for line in self.evaluation_apply_id.cost_line_temp_ids]

        # Create the importation process from the evaluation
        importation = self.env['importation.process'].create({
            'provider_id': provider.id,
            'purchase_order_ids': [(6, 0, self.evaluation_apply_id.purchase_order_ids.ids)],
            'sale_order_id': self.id,
            'customer_id': self.partner_id.id,
            'estimated_start_date': datetime.datetime.now(),
            'estimated_end_date': datetime.datetime.now(),
            # 'final_sale_order_id': self.id, aqui cambie la logica para poder usar esta como resultado del proceso de terminacion de la importacion.
            'cost_line_ids': cost_lines,
            'country_origin_id': provider.country_id.id,
            'state': 'in_progress',
            'stage_id': self.env['importation.stage'].search([], limit=1).id,
            'incoterm_id': incoterm.id if incoterm else False,
        })

        self.importation_process_id = importation.id
        # self.order_type = 'importation_process'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'importation.process',
            'view_mode': 'form',
            'res_id': importation.id,
            'target': 'current',
        }

    def _compute_purchase_order_count(self):
        for order in self:
            providers = self.env['purchase.order'].search([('sale_order_id', '=', order.id)])
            order.purchase_order_count = len(providers)

    def _compute_purchase_order_name(self):
        for order in self:
            if order.order_type == 'evaluation_final':
                providers = order.evaluation_apply_id.purchase_order_ids
            elif order.order_type == 'importation_process':
                providers = order.importation_process_id.purchase_order_ids
            else:
                providers = self.env['purchase.order'].search([('sale_order_id', '=', order.id)])

            if providers:
                providers_names = providers.mapped('partner_id.name')
                order.provider_names = ', '.join(sorted(set(providers_names)))
            else:
                order.provider_names = ""

    def _compute_purchase_evaluation_count(self):
        for order in self:
            order.purchase_evaluation_count = self.env['purchase.provider.evaluation'].search_count(
                [('sale_order_id', '=', order.id)])

    @api.depends('invoice_ids.name')
    def _compute_invoice_names(self):
        for order in self:
            invoice_names = order.invoice_ids.mapped('name')
            order.invoice_names = ', '.join(invoice_names)

    def action_view_related_purchase_orders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        if self.importation_process_id:
            invoice_vals['importation_process_id'] = self.importation_process_id.id
        return invoice_vals

    @api.model
    def create(self, vals):
        order = super().create(vals)

        # Proceso “candidato”
        target_process = False

        # Caso 1: si es orden final, hereda el proceso de la evaluación inicial
        eval_id = vals.get('evaluation_apply_id')
        if eval_id:
            evaluation = self.env['purchase.provider.evaluation'].browse(eval_id)
            origin_order = getattr(evaluation, 'sale_order_id', False)
            target_process = getattr(origin_order, 'process_id', False)

        # Caso 2: si es creada desde importación, hereda el proceso de la SO origen
        elif vals.get('importation_process_id'):
            importation = self.env['importation.process'].browse(vals['importation_process_id'])
            origin_so = getattr(importation, 'origin_sale_order_id', False)
            target_process = getattr(origin_so, 'process_id', False)

        # Asignar proceso:
        # - Si ya vino en vals o se asignó por los casos anteriores, se respeta.
        # - Si NO hay proceso aún, crear uno nuevo en estado 'open'.
        if not order.process_id:
            if target_process:
                order.process_id = target_process.id
            else:
                new_process = self.env['sale.order.process'].create({'state': 'open'})
                order.process_id = new_process.id

        return order

    def copy(self, default=None):
        default = dict(default or {})
        if 'process_id' not in default:
            default['process_id'] = self.env['sale.order.process'].create({'state': 'open'}).id
        return super().copy(default)

    def _resequence_sale_lines(self):
        for order in self:
            # ⚠️ Solo por sequence
            lines = order.order_line.sorted(lambda l: l.sequence)
            # Para ignorar secciones/notas:
            # lines = lines.filtered(lambda l: not l.display_type)
            for idx, line in enumerate(lines, start=1):
                if line.line_number != idx:
                    line.sudo().write({'line_number': idx})


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_cost_special = fields.Boolean(string="Special Cost", default=False)

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        vals["is_cost_special"] = self.is_cost_special
        return vals

    clean_description = fields.Char(
        string='Clean Description',
        compute='_compute_clean_description',
        store=False
    )

    @api.depends('name')
    def _compute_clean_description(self):
        for line in self:
            if line.name:
                line.clean_description = re.sub(r'^\[[^\]]+\]\s*', '', line.name)
            else:
                line.clean_description = ''

    line_number = fields.Integer(
        string="N°",
        compute="_compute_line_number",
        store=True,
        readonly=True,
        help="Número de línea autocalculado, inicia en 1 y se reenumera sin huecos."
    )

    @api.depends('order_id.order_line.sequence', 'order_id.order_line.display_type')
    def _compute_line_number(self):
        orders = self.mapped('order_id')
        for order in orders:
            if not order:
                continue
            # ⚠️ Solo por sequence para evitar comparar NewId
            lines = order.order_line.sorted(lambda l: l.sequence)
            # Si no quieres numerar secciones/notas:
            # lines = lines.filtered(lambda l: not l.display_type)
            for idx, line in enumerate(lines, start=1):
                line.line_number = idx

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        (records.mapped('order_id'))._resequence_sale_lines()
        return records

    def write(self, vals):
        orders_before = self.mapped('order_id')
        res = super().write(vals)
        (self.mapped('order_id') | orders_before)._resequence_sale_lines()
        return res

    def unlink(self):
        orders = self.mapped('order_id')
        res = super().unlink()
        orders._resequence_sale_lines()
        return res