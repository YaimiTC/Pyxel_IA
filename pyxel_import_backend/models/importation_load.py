import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ImportationLoad(models.Model):
    _name = 'importation.load'
    _description = 'Import Cargo or Container'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Container Number', required=True, size=11)
    importation_id = fields.Many2one('importation.process', string='Import', required=True)
    purchase_condition = fields.Selection(related='importation_id.purchase_condition', string='Purchase Condition',
                                          readonly=True)
    import_type_id = fields.Many2one(comodel_name='import.type',
                                     related='importation_id.import_type_id', string='IIT')

    cargo_type = fields.Selection([
        ('dry', 'Dry'),
        ('reefer', 'Refrigerated'),
    ], string='Load Type')

    size = fields.Selection(
        selection=[
            ('20', '20 pies'),
            ('40', '40 pies'),
        ],
        string='Size'
    )
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

    days_in_tcm = fields.Integer(string="Days in TCM", compute='_compute_days_in_tcm')
    days_extracted = fields.Integer(string="Days extracted", compute='_compute_days_extracted')

    hide_cargo_type = fields.Boolean(string='Show Cargo Type', compute='_inverse_boolean_value')
    hide_volume = fields.Boolean(string='Show Volume', compute='_inverse_boolean_value')
    hide_bulk = fields.Boolean(string='Show Bulk', compute='_inverse_boolean_value')

    hide_opening_date = fields.Boolean(string='Show Opening Date', compute='_inverse_boolean_value')
    hide_arrival_date = fields.Boolean(string='Show Arrival Date', compute='_inverse_boolean_value')
    hide_release_date = fields.Boolean(string='Show Release Date', compute='_inverse_boolean_value')
    hide_extraction_date = fields.Boolean(string='Show Extraction Date', compute='_inverse_boolean_value')
    hide_return_date = fields.Boolean(string='Show Return Date', compute='_inverse_boolean_value')

    hide_shipping_company = fields.Boolean(string='Show Shipping Company', compute='_inverse_boolean_value')
    hide_airline = fields.Boolean(string='Show Airline', compute='_inverse_boolean_value')
    hide_transit_agency = fields.Boolean(string='Show Transit Agency', compute='_inverse_boolean_value')

    @api.depends('import_type_id')
    def _inverse_boolean_value(self):
        for record in self:
            record.hide_cargo_type = False
            record.hide_volume = False
            record.hide_bulk = False
            record.hide_opening_date = False
            record.hide_arrival_date = False
            record.hide_release_date = False
            record.hide_extraction_date = False
            record.hide_return_date = False
            record.hide_shipping_company = False
            record.hide_airline = False
            record.hide_transit_agency = False
            if record.import_type_id:
                record.hide_cargo_type = not record.import_type_id.show_cargo_type
                record.hide_volume = not record.import_type_id.show_volume
                record.hide_bulk = not record.import_type_id.show_bulk
                record.hide_opening_date = not record.import_type_id.show_opening_date
                record.hide_arrival_date = not record.import_type_id.show_arrival_date
                record.hide_release_date = not record.import_type_id.show_release_date
                record.hide_extraction_date = not record.import_type_id.show_extraction_date
                record.hide_return_date = not record.import_type_id.show_return_date
                record.hide_shipping_company = not record.import_type_id.show_shipping_company
                record.hide_airline = not record.import_type_id.show_airline
                record.hide_transit_agency = not record.import_type_id.show_transit_agency

    # @api.depends('arrival_date', 'extraction_date')
    def _compute_days_in_tcm(self):
        today = datetime.date.today()
        for rec in self:
            if rec.arrival_date:
                end_date = rec.extraction_date or today
                rec.days_in_tcm = (end_date - rec.arrival_date).days
            else:
                rec.days_in_tcm = 0

    # @api.depends('extraction_date', 'return_date')
    def _compute_days_extracted(self):
        today = datetime.date.today()
        for rec in self:
            if rec.extraction_date:
                end_date = rec.return_date or today
                rec.days_extracted = (end_date - rec.extraction_date).days
            else:
                rec.days_extracted = 0

    # Estado automático
    state = fields.Selection([
        ('to_arrive', 'To arrive'),
        ('ready_extract', 'Ready to extract'),
        ('to_extract', 'To extract'),
        ('to_return', 'To return'),
        ('returned', 'Returned'),
    ], string='State', compute='_compute_state', store=True, readonly=True, tracking=True)

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
    total_cargo_line = fields.Float(string='Amount of line', compute='_compute_total_cargo_line')

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True,
        readonly=False,
    )

    @api.depends('cargo_line_ids')
    def _compute_total_cargo_line(self):
        for rec in self:
            total = 0.0
            for line in rec.cargo_line_ids:
                total += line.quantity * line.price
            rec.total_cargo_line = total

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
            prev_state = record.state
            if record.return_date:
                record.state = 'returned'
            elif record.extraction_date:
                record.state = 'to_return'
            elif record.release_date:
                record.state = 'ready_extract'
            elif record.arrival_date:
                record.state = 'to_extract'
            else:
                record.state = 'to_arrive'

        # # Si cambió el valor del estado, lo sincronizas
        # if record.state != prev_state:
        #     record.update_stage_importation()

    def update_stage_importation(self):
        for record in self:
            importation = record.importation_id
            if not importation:
                continue

            priority_states = [
                ('to_arrive', 'EN TRANSITO A PUERTO DE DESTINO'),
                ('to_extract', 'TRÁMITES EN DESTINO'),
                ('ready_extract', 'LISTO PARA EXTRAER'),
                ('to_return', 'EN ALMACÉN CLIENTE'),
                ('returned', 'DEVOLUCION DEL CONTENEDOR'),
            ]

            # Obtener estados de los contenedores relacionados
            states = list(set(filter(None, importation.load_tracking_ids.mapped('state'))))
            has_opening_date = any(importation.load_tracking_ids.mapped('opening_date'))

            # Si está en etapa inicial y no hay contenedores abiertos, no avanzar
            if not has_opening_date and importation.stage_id.name in ('SOLICITUD', 'TRÁMITES EN ORIGEN'):
                continue

            # Determinar la etapa correspondiente según las prioridades
            stage_record = None

            if states:
                # Si hay un solo estado
                if len(states) == 1:
                    single_state = states[0]
                    for internal_state, stage_name in priority_states:
                        if single_state == internal_state:
                            stage_record = self.env['importation.stage'].search([('name', '=', stage_name)], limit=1)
                            break
                else:
                    # Múltiples estados, aplicar prioridad
                    for internal_state, stage_name in priority_states:
                        if internal_state in states:
                            stage_record = self.env['importation.stage'].search([('name', '=', stage_name)], limit=1)
                            break

            # Solo actualizar si se encontró una nueva etapa diferente
            if stage_record and importation.stage_id.id != stage_record.id:
                importation.stage_id = stage_record.id

    @api.model
    def create(self, vals):
        res = super().create(vals)
        # Si se trata del primer contenedor de esa importación
        if res.importation_id and len(res.importation_id.load_tracking_ids) == 1:
            transit_stage = self.env['importation.stage'].search([('name', '=', 'EN TRANSITO A PUERTO DE DESTINO')],
                                                                 limit=1)
            if transit_stage and res.importation_id.stage_id.name in ['SOLICITUD', 'TRÁMITES EN ORIGEN']:
                res.importation_id.stage_id = transit_stage.id

        if any(f in vals for f in ['arrival_date', 'release_date', 'extraction_date', 'return_date']):
            res._compute_state()  # Forzar el recompute en memoria para los nuevos registros
            res.update_stage_importation()  # Actualizar la etapa de la importación
        return res

    def write(self, vals):
        res = super().write(vals)
        # Si se trata del primer contenedor de esa importación
        if self.importation_id and len(self.importation_id.load_tracking_ids) == 1:
            transit_stage = self.env['importation.stage'].search([('name', '=', 'EN TRANSITO A PUERTO DE DESTINO')],
                                                                 limit=1)
            if transit_stage and self.importation_id.stage_id.name in ['SOLICITUD', 'TRÁMITES EN ORIGEN']:
                self.importation_id.stage_id = transit_stage.id
        if any(f in vals for f in ['arrival_date', 'release_date', 'extraction_date', 'return_date']):
            for record in self:
                record._compute_state()  # Forzar el recompute en memoria
                record.update_stage_importation()
        return res

    @api.constrains('name')
    def _check_container_number_length(self):
        for record in self:
            if not record.name or len(record.name) != 11 or not record.name.isalnum():
                raise ValidationError("The container number must have exactly 11 alphanumeric characters.")

    @api.constrains('name', 'importation_id')
    def _check_unique_container_per_import(self):
        for record in self:
            if not record.name or not record.importation_id:
                continue

            # Busca contenedores con el mismo nombre dentro de la misma importación, excluyéndose a sí mismo
            duplicate = self.search([
                ('name', '=', record.name),
                ('importation_id', '=', record.importation_id.id),
                ('id', '!=', record.id)
            ], limit=1)

            if duplicate:
                raise ValidationError(
                    f"A container with the name '{record.name}' already exists in this import."
                )


class ImportationLoadLine(models.Model):
    _name = 'importation.load.line'
    _description = 'Product within Import Cargo'

    cargo_id = fields.Many2one('importation.load', string='Load', required=True, ondelete='cascade')
    purchase_order_line_id = fields.Many2one('purchase.order.line', string='Purchase Line', required=True)
    product_id = fields.Many2one(related='purchase_order_line_id.product_id', string='Product', store=True,
                                 readonly=True)
    quantity = fields.Float(string='Allocated Amount', required=True)
    price = fields.Float(string='Price')

    # ---------- HELPERS ----------

    def _get_allocation_context(self, line):
        """Devuelve (allocated_total, old_qty, allocated_without_current, total_with_new, max_allowed)
        para la purchase_order_line de esta línea.
        """
        po_line = line.purchase_order_line_id
        if not po_line:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        # Cantidad vieja (antes de editar). Si es nueva, 0.
        old_qty = 0.0
        if line._origin and line._origin.id:
            old_qty = line._origin.quantity or 0.0

        # Suma de TODAS las líneas (incluida esta) tal como están ahora en memoria
        all_lines = po_line.container_fix_ids
        allocated_total = sum(all_lines.mapped('quantity') or [])

        # Lo que realmente aportan "los demás" = total - lo que tenía esta línea antes
        allocated_without_current = allocated_total - old_qty

        # Lo que habría si confirmamos la cantidad nueva
        new_qty = line.quantity or 0.0
        total_with_new = allocated_without_current + new_qty

        max_allowed = po_line.product_uom_qty or 0.0

        return allocated_total, old_qty, allocated_without_current, total_with_new, max_allowed

        # ---------- CONSTRAINT ----------

    @api.constrains('quantity', 'purchase_order_line_id')
    def _check_quantity(self):
        for line in self:
            po_line = line.purchase_order_line_id
            if not po_line:
                continue

            if line.quantity is None or line.quantity <= 0:
                raise ValidationError(_("The amount allocated must be greater than zero."))

            (
                allocated_total,
                old_qty,
                allocated_without_current,
                total_with_new,
                max_allowed,
            ) = line._get_allocation_context(line)

            if total_with_new > max_allowed + 1e-6:
                available = max_allowed - allocated_without_current
                raise ValidationError(
                    _("The total allocated quantity exceeds the quantity in the purchase line. "
                      "Available: %(available)s") % {'available': available}
                )

    @api.onchange('quantity', 'purchase_order_line_id')
    def _onchange_quantity(self):
        for line in self:
            if not line.purchase_order_line_id:
                continue

            if line.quantity is None:
                continue

            if line.quantity <= 0:
                line.quantity = 0.0
                return {
                    'warning': {
                        'title': _('Invalid quantity'),
                        'message': _('You cannot assign an amount less than or equal to zero.'),
                    }
                }

            (
                allocated_total,
                old_qty,
                allocated_without_current,
                total_with_new,
                max_allowed,
            ) = line._get_allocation_context(line)

            # Si no se pasa, todo bien
            if total_with_new <= max_allowed:
                continue

            # Si se pasa, ajustamos a lo máximo permitido
            available = max_allowed - allocated_without_current
            if available < 0:
                available = 0.0

            line.quantity = available
            return {
                'warning': {
                    'title': _('Quantity adjusted'),
                    'message': _(
                        'The quantity exceeds the available quantity (%(available)s). '
                        'It has been automatically adjusted.'
                    ) % {'available': available},
                }
            }

    @api.constrains('quantity')
    def _check_quantity_not_zero(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("The amount allocated must be greater than zero."))

    @api.constrains('opening_date', 'arrival_date', 'release_date', 'extraction_date', 'return_date')
    def _check_dates_order(self):
        # Evitar la validación si se pasa un contexto explícito
        if self.env.context.get('skip_date_order_check'):
            return

        for record in self:
            dates = [
                (_("Opening Date"), record.opening_date),
                (_("Arrival Date"), record.arrival_date),
                (_("Release Date"), record.release_date),
                (_("Extraction Date"), record.extraction_date),
                (_("Return Date"), record.return_date),
            ]

            previous_label = None
            previous_date = None

            for label, date in dates:
                if date and previous_date and date < previous_date:
                    raise ValidationError(
                        _("The date '%(current)s' (%(current_date)s) cannot be earlier than '%(previous)s' (%(previous_date)s).") % {
                            'current': label,
                            'current_date': date,
                            'previous': previous_label,
                            'previous_date': previous_date,
                        }
                    )
                if date:
                    previous_label = label
                    previous_date = date
