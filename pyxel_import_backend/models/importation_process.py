from odoo import models, fields, api
from odoo.exceptions import ValidationError

STATE_SELECTION = [
    ('in_progress', 'Importación en Progreso'),
    ('done', 'Finalizado'),
    ('cancelled', 'Cancelado'),
]


class ImportationProcess(models.Model):
    _name = 'importation.process'
    _description = 'Proceso de importación'

    name = fields.Char(string='Referencia', required=True, default='Nuevo')
    stage_id = fields.Many2one('importation.stage', string='Etapa del Proceso',
                               default=lambda self: self.env['importation.stage'].search([], limit=1),
                               group_expand='_group_expand_stage_id',
                               ondelete='restrict')
    state = fields.Selection(
        STATE_SELECTION,
        string='Estado',
        default='draft',
        tracking=True,
    )
    purchase_order_ids = fields.Many2many('purchase.order', string='Órdenes de Compra')
    cost_line_ids = fields.One2many('importation.cost.line', 'importation_id', string='Costos adicionales')
    total_cost = fields.Monetary(string='Costo Total', compute='_compute_total_cost')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    sale_order_id = fields.Many2one('sale.order', string='Presupuesto original',)
    final_sale_order_id = fields.Many2one('sale.order', string='Oferta Final Generada', readonly=True)

    provider_id = fields.Many2one('res.partner', string='Proveedor')

    country_origin_id = fields.Many2one('res.country', string='País de Origen')
    is_third_party_contract = fields.Boolean(string='Contrato con Tercero')
    declaration = fields.Text(string='Declaración de la mercancía')

    estimated_start_date = fields.Date(string='Fecha estimada de inicio')
    estimated_end_date = fields.Date(string='Fecha estimada de fin')
    departure_date = fields.Date(string='Fecha de salida del origen')
    declaration_date = fields.Date(string='Fecha de declaración de mercancía')
    documentation_sent_date = fields.Date(string='Fecha de envío de documentación')

    port = fields.Char(string='Puerto')
    airport = fields.Char(string='Aeropuerto')

    purchase_condition = fields.Selection([
        ('fcl', 'Importación marítima con contenedor lleno (FCL)'),
        ('air', 'Importación vía aérea'),
        ('local', 'Compra en plaza'),
        ('grouped', 'Carga agrupada')
    ], string='Condición de compra')

    purchase_condition_number = fields.Char(string='Número / Referencia según condición')

    # Documentos adjuntos
    origin_certificate = fields.Binary(string='Certificado de Origen')
    origin_certificate_filename = fields.Char()

    export_certificate = fields.Binary(string='Certificado de Exportación')
    export_certificate_filename = fields.Char()

    quality_certificate = fields.Binary(string='Certificado de Calidad')
    quality_certificate_filename = fields.Char()

    commercial_invoice = fields.Binary(string='Factura Comercial')
    commercial_invoice_filename = fields.Char()

    signed_offer = fields.Binary(string='Oferta Firmada')
    signed_offer_filename = fields.Char()

    documentation_file = fields.Binary(string='Documentación (FCL / AWB)')
    documentation_file_filename = fields.Char()

    packing_list = fields.Binary(string='Lista de Empaque')
    packing_list_filename = fields.Char()

    load_tracking_ids = fields.One2many(
        'importation.load',
        'importation_id',
        string="Modelo de carga"
    )

    @api.depends('cost_line_ids.amount')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(line.amount for line in rec.cost_line_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nuevo') == 'Nuevo':
            sequence = self.env['ir.sequence'].next_by_code('importation.process')
            vals['name'] = sequence or 'Nuevo'
        return super().create(vals)

    def action_start_progress(self):
        self.write({'state': 'in_progress'})

    def action_finish_progress(self):
        self.write({'state': 'done'})

    @api.model
    def _group_expand_stage_id(self, stages, domain, order):
        return self.env['importation.stage'].search([], order=order)


class ImportationCostLine(models.Model):
    _name = 'importation.cost.line'
    _description = 'Línea de costo adicional de importación'

    importation_id = fields.Many2one('importation.process', string='Proceso de importación')
    product_id = fields.Many2one(
        'product.product',
        string='Servicio',
        domain=[('detailed_type', '=', 'service')],
        required=True
    )

    name = fields.Char(string='Descripción', compute='_compute_name',  required=True)
    amount = fields.Monetary(string='Monto')
    distribution_type = fields.Selection([
        ('fixed', 'Monto Fijo por orden'),
        ('percentage', 'Porcentaje sobre orden'),
    ], string='Tipo de distribución', required=True)
    currency_id = fields.Many2one('res.currency', related='importation_id.currency_id', readonly=True)


    # validar si aplica en divep (porq este habría q identificarlo en la línea para saber
    # q se tiene en cuenta para diferencirlo en el reporte de conciliación de la facturación)

    is_cost_special = fields.Boolean(string='Cost special', default=False)

    @api.depends('product_id')
    def _compute_name(self):
        for record in self:
            record.name = record.product_id.display_name or ''


class ImportationStage(models.Model):
    _name = 'importation.stage'
    _description = 'Etapas del proceso de importación'

    name = fields.Char(string='Nombre', required=True)
    description = fields.Char(string='Descripcion')
    sequence = fields.Integer(required=True, default=1)
    fold = fields.Boolean('Colapsado en Kanban', default=False)

