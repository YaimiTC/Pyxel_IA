from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ImportationLoad(models.Model):
    _name = 'importation.load'
    _description = 'Carga o Contenedor de Importación'

    name = fields.Char(string='Número de Contenedor', required=True)
    importation_id = fields.Many2one('importation.process', string='Importación', required=True)
    purchase_condition = fields.Selection(related='importation_id.purchase_condition', string='Condición de Compra', readonly=True)

    cargo_type = fields.Selection([
        ('dry', 'Seca'),
        ('reefer', 'Refrigerada'),
    ], string='Tipo de Carga', required=True)

    size = fields.Char(string='Tamaño')
    weight = fields.Float(string='Peso (Kg)')
    volume = fields.Float(string='Volumen (m³)')
    supplier_invoice_number = fields.Char(string='Número de Factura del Proveedor')

    is_transferred = fields.Boolean(string='Transferido')
    is_transshipment = fields.Boolean(string='Transbordo')
    transshipment_type = fields.Selection([
        ('stgo', 'Terminal Santiago de Cuba'),
        ('havana', 'Terminal La Habana'),
        ('mariel', 'Terminal Mariel'),
    ], string='Tipo de Transbordo')

    # Fechas clave
    opening_date = fields.Date(string='Fecha de Apertura')
    arrival_date = fields.Date(string='Fecha de Arribo')
    release_date = fields.Date(string='Fecha de Liberación')
    extraction_date = fields.Date(string='Fecha de Extracción')
    return_date = fields.Date(string='Fecha de Retorno')

    # Estado automático
    state = fields.Selection([
        ('to_arrive', 'Por Arribar'),
        ('ready_extract', 'Listo para Extraer'),
        ('to_extract', 'Por Extraer'),
        ('to_return', 'Por Devolver'),
        ('returned', 'Devuelto'),
    ], string='Estado', compute='_compute_state', store=True, readonly=True)

    # Información logística adicional
    airline = fields.Char(string='Aerolínea')
    transit_agency = fields.Char(string='Transitaria')

    # Información del Transportista
    pre_appointment_date = fields.Date(string='Fecha Previa a la Cita')
    appointment_date = fields.Date(string='Fecha de Cita')
    transport_company = fields.Char(string='Empresa de Transporte')
    province = fields.Char(string='Provincia')
    truck_plate = fields.Char(string='Camión')
    destination = fields.Char(string='Destino')
    driver = fields.Char(string='Conductor')

    # Líneas de producto asignadas a la carga (fracción de ordenes de compra)
    cargo_line_ids = fields.One2many('importation.load.line', 'cargo_id', string='Productos Transportados')

    @api.depends('arrival_date', 'release_date', 'extraction_date', 'return_date')
    def _compute_state(self):
        for record in self:
            if record.return_date:
                record.state = 'returned'
            elif record.extraction_date:
                record.state = 'to_return'
            elif record.release_date:
                record.state = 'to_extract'
            elif record.arrival_date:
                record.state = 'ready_extract'
            else:
                record.state = 'to_arrive'

    def update_stage_importation(self):
        for record in self:
            importation = record.importation_id
            if not importation:
                continue

            priority_states = [
                ('To arrive', 'EN TRANSITO A PUERTO DE DESTINO'),
                ('To extract', 'TRÁMITES EN DESTINO'),
                ('Ready to extract', 'LISTO PARA EXTRAER'),
                ('To return', 'EN ALMACÉN CLIENTE'),
                ('Returned', 'DEVOLUCION DEL CONTENEDOR'),
            ]

            states = importation.container_ids.mapped('state')
            states = list(filter(None, states))
            unique_states = list(set(states))

            stage = None
            if unique_states:
                if len(unique_states) == 1:
                    unique_state = unique_states[0]
                    for state, stage in priority_states:
                        if unique_state == state:
                            stage = self.env['importation.stage'].search([('name', '=', stage)], limit=1)
                            break
                else:
                    for state, stage in priority_states:
                        if state in unique_states:
                            stage = self.env['importation.stage'].search([('name', '=', stage)], limit=1)
                            break

            if stage:
                importation.stage_id = stage.id

    @api.model
    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            for record in self:
                record.update_stage_importation()
        return res


class ImportationLoadLine(models.Model):
    _name = 'importation.load.line'
    _description = 'Producto dentro de Carga de Importación'

    cargo_id = fields.Many2one('importation.load', string='Carga', required=True, ondelete='cascade')
    purchase_order_line_id = fields.Many2one('purchase.order.line', string='Línea de Compra', required=True)
    product_id = fields.Many2one(related='purchase_order_line_id.product_id', string='Producto', store=True, readonly=True)
    quantity = fields.Float(string='Cantidad Asignada', required=True)

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity > line.purchase_order_line_id.product_qty:
                raise ValidationError("La cantidad asignada excede la cantidad disponible en la línea de compra.")
