from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ImportationLoad(models.Model):
    _name = 'importation.load'
    _description = 'Import Cargo or Container'

    name = fields.Char(string='Container Number', required=True, size=11)
    importation_id = fields.Many2one('importation.process', string='Import', required=True)
    purchase_condition = fields.Selection(related='importation_id.purchase_condition', string='Purchase Condition',
                                          readonly=True)

    cargo_type = fields.Selection([
        ('dry', 'Dry'),
        ('reefer', 'Refrigerated'),
    ], string='Load Type', required=True)

    size = fields.Char(string='Size')
    weight = fields.Float(string='Weight (Kg)')
    volume = fields.Float(string='Volume (m³)')
    bulk = fields.Float(string='Bulk')
    supplier_invoice_number = fields.Char(string='Supplier Invoice Number')

    is_transferred = fields.Boolean(string='Transferred')
    is_transshipment = fields.Boolean(string='Transfer')
    transshipment_type = fields.Selection([
        ('stgo', 'Santiago de Cuba Terminal'),
        ('havana', 'Havana Terminal'),
        ('mariel', 'Mariel Terminal'),
    ], string='Type of Transfer')

    # Fechas clave
    opening_date = fields.Date(string='Opening Date')
    arrival_date = fields.Date(string='Arrival Date')
    release_date = fields.Date(string='Release Date')
    extraction_date = fields.Date(string='Extraction Date')
    return_date = fields.Date(string='Return Date')

    # Estado automático
    state = fields.Selection([
        ('to_arrive', 'To arrive'),
        ('ready_extract', 'Ready to extract'),
        ('to_extract', 'To extract'),
        ('to_return', 'To return'),
        ('returned', 'Returned'),
    ], string='State', compute='_compute_state', store=True, readonly=True)

    # Información logística adicional
    shipping_company = fields.Char(string='Shipping company')
    airline = fields.Char(string='Airline')
    transit_agency = fields.Char(string='Transitory')

    # Información del Transportista
    pre_appointment_date = fields.Date(string='Date Prior to the Appointment')
    appointment_date = fields.Date(string='Appointment Date')
    transport_company = fields.Char(string='Transport Company')
    province = fields.Char(string='Province')
    truck_plate = fields.Char(string='Truck')
    destination = fields.Char(string='Destination')
    driver = fields.Char(string='Driver')

    # Líneas de producto asignadas a la carga (fracción de ordenes de compra)
    cargo_line_ids = fields.One2many('importation.load.line', 'cargo_id', string='Products transported')

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True,
        readonly=False,
    )

    @api.depends('cargo_line_ids.purchase_order_line_id.order_id.currency_id')
    def _compute_currency_id(self):
        for record in self:
            currencies = record.cargo_line_ids.mapped('purchase_order_line_id.order_id.currency_id')
            record.currency_id = currencies[0] if currencies else False

    purchase_order_ids = fields.Many2many('purchase.order', compute='_compute_purchase_orders', store=False)

    @api.depends('importation_id')
    def _compute_purchase_orders(self):
        for rec in self:
            rec.purchase_order_ids = rec.importation_id.purchase_order_ids

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
    def create(self, vals):
        record = super().create(vals)
        if 'state' in vals:
            record.update_stage_importation()
        return record

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            for record in self:
                record.update_stage_importation()
        return res

    @api.constrains('name')
    def _check_container_number_length(self):
        for record in self:
            if not record.name or len(record.name) != 11 or not record.name.isalnum():
                raise ValidationError("The container number must have exactly 11 alphanumeric characters.")


class ImportationLoadLine(models.Model):
    _name = 'importation.load.line'
    _description = 'Product within Import Cargo'

    cargo_id = fields.Many2one('importation.load', string='Load', required=True, ondelete='cascade')
    purchase_order_line_id = fields.Many2one('purchase.order.line', string='Purchase Line', required=True)
    product_id = fields.Many2one(related='purchase_order_line_id.product_id', string='Product', store=True,
                                 readonly=True)
    quantity = fields.Float(string='Allocated Amount', required=True)
    price = fields.Float(string='Price')

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity > line.purchase_order_line_id.product_qty:
                raise ValidationError("The allocated quantity exceeds the quantity available in the purchase line.")
