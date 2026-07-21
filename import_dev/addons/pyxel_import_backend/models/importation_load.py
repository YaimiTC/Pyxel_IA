import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ImportationLoad(models.Model):
    _name = 'importation.load'
    _description = 'Import Cargo or Container'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _register_hook(self):
        """Odoo no reescribe la traducción es_ES de field_description cuando
        cambia el string= en Python (solo lo hace en instalaciones nuevas) —
        se queda pegada la traducción vieja hasta que alguien la corrige a
        mano por RPC. Esto se autocorrige acá en cada carga del módulo
        (instalación, -u, o simple reinicio) para que no vuelva a repetirse."""
        res = super()._register_hook()
        self._fix_es_translations()
        return res

    @api.model
    def _fix_es_translations(self):
        fixes = {
            'shipping_company': 'Naviera',
            'airline': 'Aerolínea',
            'transit_agency': 'Transitoria',
            'is_transshipment': 'Transbordo',
            'transshipment_type': 'Tipo de transbordo',
            'days_in_tcm': 'Días en la Terminal',
            'weight': 'Peso Bruto (Kg)',
            'net_weight': 'Peso Neto (Kg)',
        }
        IrField = self.env['ir.model.fields'].sudo()
        for fname, label in fixes.items():
            field = IrField.search([('model', '=', self._name), ('name', '=', fname)], limit=1)
            if not field:
                continue
            current = field.with_context(lang='es_ES').field_description
            if current != label:
                field.with_context(lang='es_ES').write({'field_description': label})

    name = fields.Char(string='Container Number', required=True, size=11)
    importation_id = fields.Many2one('importation.process', string='Import')
    purchase_condition = fields.Selection(related='importation_id.purchase_condition', string='Purchase Condition',
                                          readonly=True)
    import_type_id = fields.Many2one(comodel_name='import.type',
                                              related='importation_id.import_type_id', string='IIT', store=True)

    cargo_type = fields.Selection([
        ('dry', 'Dry'),
        ('reefer', 'Reefer'),
    ], string='Load Type', default='dry')

    size = fields.Selection(
        selection=[
            ('20', '20 pies'),
            ('40', '40 pies'),
        ],
        string='Size'
    )
    weight = fields.Float(string='Peso Bruto (Kg)')
    net_weight = fields.Float(string='Peso Neto (Kg)')
    volume = fields.Float(string='Volume (m³)')
    bulk = fields.Float(string='Bulk')
    supplier_invoice_number = fields.Char(string='Supplier Invoice Number')

    is_transferred = fields.Boolean(string='Transferred')
    is_transshipment = fields.Boolean(string='Transshipment')
    transshipment_type = fields.Selection([
        ('stgo', 'Santiago de Cuba Terminal'),
        ('havana', 'Havana Terminal'),
        ('mariel', 'Mariel Terminal'),
    ], string='Type of Transshipment')

    # Fechas clave
    opening_date = fields.Date(string='Opening Date')
    arrival_date = fields.Date(string='Arrival Date')
    release_date = fields.Date(string='Release Date')
    extraction_date = fields.Date(string='Extraction Date')
    return_date = fields.Date(string='Return Date')

    # Datos del reporte de la Terminal (TCM) que hoy no tienen otro campo
    # donde caer. master_bl_number y mbl_release_date son del Master BL (el
    # BL house real del contenedor se sigue guardando en bl_number). El DM
    # real vive en purchase_order.declaration/declaration_date cuando el
    # contenedor tiene proceso/OC; mientras el contenedor es huérfano, la
    # fecha del reporte de la Terminal se deja aquí como referencia.
    master_bl_number = fields.Char(string='Master BL')
    mbl_release_date = fields.Date(string='Fecha liberación Master BL')
    container_release_partner = fields.Char(string='Consignatario liberación contenedor')
    container_release_date = fields.Date(string='Fecha liberación consignado')
    declaration_date_probable = fields.Date(string='Fecha DM')

    # Marca interna: la última corrida en que el reporte de la Terminal trajo
    # este contenedor asignado a NUESTRA empresa (H o J = importadora). Sirve
    # para detectar la corrida exacta en que "dejó de salir como nuestro": si
    # una corrida lo trae con otra importadora y esta marca estaba en True, es
    # el cambio (se cuenta como 'Cambió a otra importadora' y se apaga la
    # marca); si ya estaba en False, es que venía de antes ('Otro valor').
    belongs_to_us = fields.Boolean(
        string='Visto como nuestro en la última corrida', default=False, copy=False)

    days_in_tcm = fields.Integer(string="Days in Terminal", compute='_compute_days_in_tcm')
    days_extracted = fields.Integer(string="Days extracted", compute='_compute_days_extracted')

    hide_cargo_type = fields.Boolean(string='Show Cargo Type', compute='_inverse_boolean_value', store=True)
    hide_volume = fields.Boolean(string='Show Volume', compute='_inverse_boolean_value', store=True)
    hide_bulk = fields.Boolean(string='Show Bulk', compute='_inverse_boolean_value', store=True)

    hide_opening_date = fields.Boolean(string='Show Opening Date', compute='_inverse_boolean_value', store=True)
    hide_arrival_date = fields.Boolean(string='Show Arrival Date', compute='_inverse_boolean_value', store=True)
    hide_release_date = fields.Boolean(string='Show Release Date', compute='_inverse_boolean_value', store=True)
    hide_extraction_date = fields.Boolean(string='Show Extraction Date', compute='_inverse_boolean_value', store=True)
    hide_return_date = fields.Boolean(string='Show Return Date', compute='_inverse_boolean_value', store=True)

    hide_shipping_company = fields.Boolean(string='Show Shipping Company', compute='_inverse_boolean_value', store=True)
    hide_airline = fields.Boolean(string='Show Airline', compute='_inverse_boolean_value', store=True)
    hide_transit_agency = fields.Boolean(string='Show Transit Agency', compute='_inverse_boolean_value', store=True)

    show_shipping_company = fields.Boolean(string='Mostrar Naviera', compute='_compute_show_transport', store=False)
    show_airline = fields.Boolean(string='Mostrar Aerolínea', compute='_compute_show_transport', store=False)
    show_transit_agency = fields.Boolean(string='Mostrar Transitoria', compute='_compute_show_transport', store=False)

    @api.depends('importation_id', 'importation_id.import_type_id')
    def _compute_show_transport(self):
        for record in self:
            import_type = record.importation_id.import_type_id
            record.show_shipping_company = import_type.show_shipping_company if import_type else False
            record.show_airline = import_type.show_airline if import_type else False
            record.show_transit_agency = import_type.show_transit_agency if import_type else False

    @api.onchange('importation_id')
    def _onchange_importation_id(self):
        self._inverse_boolean_value()
        self._compute_show_transport()

    @api.depends('import_type_id', 'importation_id', 'importation_id.import_type_id')
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
            import_type = record.import_type_id or record.importation_id.import_type_id
            if import_type:
                record.hide_cargo_type = not import_type.show_cargo_type
                record.hide_volume = not import_type.show_volume
                record.hide_bulk = not import_type.show_bulk
                record.hide_opening_date = not import_type.show_opening_date
                record.hide_arrival_date = not import_type.show_arrival_date
                record.hide_release_date = not import_type.show_release_date
                record.hide_extraction_date = not import_type.show_extraction_date
                record.hide_return_date = not import_type.show_return_date
                record.hide_shipping_company = not import_type.show_shipping_company
                record.hide_airline = not import_type.show_airline
                record.hide_transit_agency = not import_type.show_transit_agency


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
    shipping_company = fields.Char(string='Naviera')
    airline = fields.Char(string='Aerolínea')
    transit_agency = fields.Char(string='Transitoria')

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
    cargo_line_count = fields.Integer(string='Líneas de productos', compute='_compute_cargo_line_count')
    total_cargo_line = fields.Float(string='Amount of line', compute='_compute_total_cargo_line')

    @api.depends('cargo_line_ids')
    def _compute_cargo_line_count(self):
        for rec in self:
            rec.cargo_line_count = len(rec.cargo_line_ids)

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True,
        readonly=False,
    )

    # BL / AWB real del contenedor. Si el contenedor tiene línea(s) de OC
    # vinculada(s), se toma de ahí (purchase_order.bl_number). Si no tiene
    # proceso/OC vinculado (contenedor creado directo desde la Terminal, ver
    # wizard_import_tcm.py), se conserva el valor puesto manualmente/por el wizard.
    bl_number = fields.Char(string='BL / AWB', compute='_compute_bl_number', store=True, readonly=False)

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

    @api.depends('cargo_line_ids.purchase_order_line_id.order_id.bl_number')
    def _compute_bl_number(self):
        for record in self:
            po_bls = [b for b in record.cargo_line_ids.mapped('purchase_order_line_id.order_id.bl_number') if b]
            if po_bls:
                record.bl_number = po_bls[0]
            # si no hay OC vinculada, no se toca: puede haber sido puesto
            # manualmente o por el wizard de importación de la Terminal

    provider_ids = fields.Many2many(
        'res.partner', string='Proveedores', compute='_compute_provider_ids',
        store=True, readonly=False,
        help="Se completa solo desde las líneas de compra vinculadas cuando "
             "existen. Si el contenedor todavía no tiene proceso vinculado "
             "(se cargó sin operación), se puede dejar un proveedor probable "
             "a mano; en cuanto se suba la importación real, este campo se "
             "sobrescribe con el proveedor oficial de esa operación.")
    customer_id = fields.Many2one(
        'res.partner', string='Cliente', compute='_compute_customer_id',
        store=True, readonly=False,
        help="Se completa solo desde el proceso de importación cuando existe. "
             "Si el contenedor todavía no tiene proceso vinculado (se cargó "
             "sin operación), se puede dejar un cliente probable a mano; en "
             "cuanto se suba la importación real, este campo se sobrescribe "
             "con el cliente oficial de esa operación.")
    carrier = fields.Char(
        string='Naviera/Transitoria/Aerolínea', compute='_compute_carrier')

    @api.depends('importation_id.customer_id')
    def _compute_customer_id(self):
        for record in self:
            if record.importation_id.customer_id:
                record.customer_id = record.importation_id.customer_id

    @api.depends('cargo_line_ids.purchase_order_line_id.order_id.partner_id')
    def _compute_provider_ids(self):
        for record in self:
            partners = record.cargo_line_ids.mapped('purchase_order_line_id.order_id.partner_id')
            if partners:
                record.provider_ids = partners

    @api.depends('shipping_company', 'transit_agency', 'airline')
    def _compute_carrier(self):
        for record in self:
            record.carrier = record.shipping_company or record.transit_agency or record.airline or False

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

    @api.model
    def get_dashboard_data(self):
        today = fields.Date.today()
        from datetime import timedelta

        d4 = today - timedelta(days=4)
        d9 = today - timedelta(days=9)
        d10 = today - timedelta(days=10)
        d19 = today - timedelta(days=19)
        d20 = today - timedelta(days=20)
        d29 = today - timedelta(days=29)
        d30 = today - timedelta(days=30)
        d15 = today - timedelta(days=15)
        d3 = today + timedelta(days=3)

        in_port = [('extraction_date', '=', False), ('arrival_date', '!=', False)]

        kpis = {
            'en_mariel': self.search_count(in_port),
            'habilitados': self.search_count(
                in_port + [('pre_appointment_date', '!=', False)]
            ),
            'extraidos_hoy': self.search_count([('extraction_date', '=', today)]),
            'sin_habilitar': self.search_count(
                in_port + [('pre_appointment_date', '=', False)]
            ),
            'plan_hoy': self.search_count([('appointment_date', '=', today), ('extraction_date', '=', False)]),
        }

        aging = {
            'de_0_4': self.search_count(in_port + [('arrival_date', '>=', d4)]),
            'de_5_9': self.search_count(in_port + [('arrival_date', '>=', d9), ('arrival_date', '<', d4)]),
            'de_10_19': self.search_count(in_port + [('arrival_date', '>=', d19), ('arrival_date', '<', d9)]),
            'de_20_29': self.search_count(in_port + [('arrival_date', '>=', d29), ('arrival_date', '<', d19)]),
            'de_30_mas': self.search_count(in_port + [('arrival_date', '<', d29)]),
        }
        aging['total'] = sum(aging.values()) or 1

        plan_records = self.search_read(
            [('appointment_date', '>=', today), ('appointment_date', '<', d3), ('extraction_date', '=', False)],
            ['name', 'appointment_date', 'importation_id', 'cargo_type', 'transit_agency', 'days_in_tcm'],
            order='appointment_date asc',
            limit=50,
        )
        for r in plan_records:
            if r.get('importation_id'):
                proc = self.env['importation.process'].browse(r['importation_id'][0])
                r['customer'] = proc.customer_id.name or ''
            else:
                r['customer'] = ''
            r['appointment_date'] = str(r['appointment_date'])

        alertas = {
            'precita_vencida': self.search_count(
                [('appointment_date', '<', today), ('appointment_date', '!=', False), ('extraction_date', '=', False)]
            ),
            'sin_identificar': self.search_count(
                [('arrival_date', '!=', False), ('transit_agency', '=', False), ('extraction_date', '=', False)]
            ),
            'envejecidos': self.search_count(in_port + [('arrival_date', '<', d30)]),
            'sin_habilitar': self.search_count(in_port + [('pre_appointment_date', '=', False)]),
        }

        del_dia_hab = self.search_read(
            [('release_date', '=', today)],
            ['name', 'importation_id', 'cargo_type'],
            limit=100,
        )
        del_dia_ext = self.search_read(
            [('extraction_date', '=', today)],
            ['name', 'importation_id', 'cargo_type'],
            limit=100,
        )

        def summarize_del_dia(records):
            counts = {'DIESEL': 0, 'GASOLINA': 0, 'GLP': 0, 'OTRO': 0}
            for r in records:
                ct = (r.get('cargo_type') or '').upper()
                if ct in counts:
                    counts[ct] += 1
                else:
                    counts['OTRO'] += 1
            counts['total'] = sum(counts.values())
            return counts

        # Histórico: extraídos y retornados por mes (últimos 12 meses)
        self.env.cr.execute("""
            SELECT
                TO_CHAR(extraction_date, 'YYYY-MM') AS mes,
                TO_CHAR(extraction_date, 'Mon YYYY') AS mes_label,
                COUNT(*) AS extraidos,
                COUNT(*) FILTER (WHERE return_date IS NOT NULL) AS retornados,
                ROUND(AVG(extraction_date - arrival_date)) AS dias_prom
            FROM importation_load
            WHERE extraction_date >= (CURRENT_DATE - INTERVAL '12 months')
              AND extraction_date IS NOT NULL
            GROUP BY mes, mes_label
            ORDER BY mes ASC
        """)
        historico_rows = self.env.cr.dictfetchall()
        historico = [
            {
                'mes': r['mes'],
                'label': r['mes_label'],
                'extraidos': r['extraidos'],
                'retornados': r['retornados'],
                'sin_retorno': r['extraidos'] - r['retornados'],
                'dias_prom': int(r['dias_prom'] or 0),
            }
            for r in historico_rows
        ]

        ext = self._get_dashboard_extension(today)

        return {
            'kpis': kpis,
            'aging': aging,
            'plan': plan_records,
            'alertas': alertas,
            'del_dia_hab': summarize_del_dia(del_dia_hab),
            'del_dia_ext': summarize_del_dia(del_dia_ext),
            'historico': historico,
            **ext,
        }

    @api.model
    def _fuel_group(self, name):
        n = (name or '').lower().replace('-', ' ').replace('_', ' ')
        if 'gasolina' in n and '91' in n:
            return 'Gasolina 91'
        if 'gasolina' in n and '83' in n:
            return 'Gasolina 83'
        if 'gasolina' in n:
            return 'Gasolina'
        if 'diesel' in n or 'diés' in n:
            return 'Diésel'
        if 'jet' in n:
            return 'Jet A-1'
        if 'fuel' in n:
            return 'Fuel oíl'
        if 'glp' in n or 'lpg' in n:
            return 'GLP'
        return None

    @api.model
    def _get_dashboard_extension(self, today):
        """Bloques del tablero pedidos por Operaciones (docx TABLERO 02/06/2026).
        Se calcula con datos ya existentes; los bloques que dependen de
        estructura por crear (trámite documentario, refacturación, categorías
        de serviciador) devuelven 0 hasta la Fase 2."""
        cr = self.env.cr

        # ---- Avance de reconciliación: contenedores sin datos comerciales ----
        # Util para medir el avance dia a dia mientras se cargan operaciones
        # sin proceso (contenedores huerfanos importados desde reportes de
        # la Terminal).
        avance_reconciliacion = {
            'total': self.search_count([]),
            'sin_importacion': self.search_count([('importation_id', '=', False)]),
            'sin_proveedor': self.search_count([('provider_ids', '=', False)]),
            'sin_cliente': self.search_count([('customer_id', '=', False)]),
            'sin_cliente_ni_proveedor': self.search_count([
                ('customer_id', '=', False), ('provider_ids', '=', False),
            ]),
        }

        # ---- Totales del docx (P3 · P4 · P5) ----
        totales = {
            'importados': self.search_count([('state', '=', 'returned')])
                        + self.search_count([('state', 'in', ('to_extract', 'to_return')), ('extraction_date', '!=', False)]),
            'en_transito': self.search_count([('state', '=', 'to_arrive')]),
            'por_devolver': self.search_count([
                '|',
                '&', '&', ('state', 'in', ('to_extract', 'to_return')), ('return_date', '=', False), ('extraction_date', '!=', False),
                ('state', '=', 'to_return'),
            ]),
        }

        # ---- Producto × estado (P6 · P9): conteo y volumen (litros) ----
        cr.execute("""
            SELECT pt.name->>'en_US' AS prod_name,
                   il.state,
                   COUNT(DISTINCT il.id) AS n_containers,
                   COALESCE(SUM(ill.quantity), 0) AS vol
            FROM importation_load il
            JOIN importation_load_line ill ON ill.cargo_id = il.id
            JOIN purchase_order_line pol ON pol.id = ill.purchase_order_line_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            GROUP BY 1, 2
        """)
        conteo = {}   # grupo -> {estado: n}
        volumen = {}  # grupo -> {estado: L}
        for r in cr.dictfetchall():
            grupo = self._fuel_group(r['prod_name'])
            if not grupo:
                continue
            # 'ready_extract' (habilitado, aún sin extraer) se agrupa con
            # 'to_extract' — ambos significan "todavía en el Terminal".
            estado = 'to_extract' if r['state'] == 'ready_extract' else r['state']
            conteo.setdefault(grupo, {}).setdefault(estado, 0)
            conteo[grupo][estado] += int(r['n_containers'])
            volumen.setdefault(grupo, {}).setdefault(estado, 0.0)
            volumen[grupo][estado] += float(r['vol'] or 0)

        prod_orden = ['Diésel', 'Gasolina 91', 'Gasolina 83', 'Gasolina', 'Jet A-1', 'Fuel oíl', 'GLP']
        estados_orden = ['to_arrive', 'to_extract', 'returned', 'to_return']
        estado_lbl = {'to_arrive': 'Por llegar', 'to_extract': 'En Terminal', 'returned': 'Extraído', 'to_return': 'Por devolver'}

        def _fila(grupo, source):
            row = {'producto': grupo}
            total = 0
            for st in estados_orden:
                v = source.get(grupo, {}).get(st, 0)
                row[estado_lbl[st]] = v
                total += v
            row['Total'] = total
            return row

        producto_estado_conteo = [_fila(g, conteo) for g in prod_orden if g in conteo]
        producto_estado_volumen = [_fila(g, volumen) for g in prod_orden if g in volumen]

        # ---- Precios promedio por producto (P10) ----
        cr.execute("""
            SELECT pt.name->>'en_US' AS prod_name,
                   SUM(pol.price_unit * pol.product_qty) / NULLIF(SUM(pol.product_qty), 0) AS precio_prom,
                   SUM(pol.product_qty) AS qty_total,
                   COUNT(DISTINCT ill.cargo_id) AS n_containers
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            LEFT JOIN importation_load_line ill ON ill.purchase_order_line_id = pol.id
            WHERE po.state != 'cancel'
            GROUP BY 1
        """)
        precios_raw = {}
        for r in cr.dictfetchall():
            g = self._fuel_group(r['prod_name'])
            if not g:
                continue
            precios_raw.setdefault(g, {'precio_sum': 0.0, 'qty': 0.0, 'n': 0})
            precios_raw[g]['precio_sum'] += float(r['precio_prom'] or 0) * float(r['qty_total'] or 0)
            precios_raw[g]['qty'] += float(r['qty_total'] or 0)
            precios_raw[g]['n'] += int(r['n_containers'] or 0)
        precios_promedio = []
        for g in prod_orden:
            if g not in precios_raw:
                continue
            d = precios_raw[g]
            precio = (d['precio_sum'] / d['qty']) if d['qty'] else 0.0
            precios_promedio.append({
                'producto': g,
                'precio_prom': round(precio, 4),
                'litros_total': round(d['qty'], 0),
                'contenedores': d['n'],
            })

        # ---- Rankings (P11 · P12 · P13) ----
        # Proveedores × producto × país
        cr.execute("""
            SELECT rp.name AS proveedor,
                   pt.name->>'en_US' AS prod_name,
                   rc.name->>'en_US' AS pais,
                   COUNT(DISTINCT il.id) AS n
            FROM importation_load il
            JOIN importation_process ip ON ip.id = il.importation_id
            JOIN res_partner rp ON rp.id = ip.provider_id
            LEFT JOIN res_country rc ON rc.id = ip.country_origin_id
            JOIN importation_load_line ill ON ill.cargo_id = il.id
            JOIN purchase_order_line pol ON pol.id = ill.purchase_order_line_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            GROUP BY 1, 2, 3
            ORDER BY 4 DESC
            LIMIT 30
        """)
        ranking_proveedores = []
        for r in cr.dictfetchall():
            g = self._fuel_group(r['prod_name'])
            if not g:
                continue
            ranking_proveedores.append({
                'label': f"{r['proveedor']} · {g} · {r['pais'] or '—'}",
                'cantidad': int(r['n']),
            })
        ranking_proveedores = ranking_proveedores[:5]

        # Clientes × producto × provincia
        cr.execute("""
            SELECT rp.name AS cliente,
                   pt.name->>'en_US' AS prod_name,
                   rcs.name AS provincia,
                   COUNT(DISTINCT il.id) AS n
            FROM importation_load il
            JOIN importation_process ip ON ip.id = il.importation_id
            JOIN res_partner rp ON rp.id = ip.customer_id
            LEFT JOIN res_country_state rcs ON rcs.id = rp.state_id
            JOIN importation_load_line ill ON ill.cargo_id = il.id
            JOIN purchase_order_line pol ON pol.id = ill.purchase_order_line_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE ip.customer_id IS NOT NULL
            GROUP BY 1, 2, 3
            ORDER BY 4 DESC
            LIMIT 30
        """)
        ranking_clientes = []
        for r in cr.dictfetchall():
            g = self._fuel_group(r['prod_name'])
            if not g:
                continue
            ranking_clientes.append({
                'label': f"{r['cliente']} · {g} · {r['provincia'] or '—'}",
                'cantidad': int(r['n']),
            })
        ranking_clientes = ranking_clientes[:5]

        # Navieras × producto × país × puerto  (shipping_company es Char)
        cr.execute("""
            SELECT UPPER(TRIM(il.shipping_company)) AS naviera,
                   pt.name->>'en_US' AS prod_name,
                   rc.name->>'en_US' AS pais,
                   th.name AS puerto,
                   COUNT(DISTINCT il.id) AS n
            FROM importation_load il
            JOIN importation_process ip ON ip.id = il.importation_id
            LEFT JOIN res_country rc ON rc.id = ip.country_origin_id
            LEFT JOIN transport_hub th ON th.id = ip.port
            JOIN importation_load_line ill ON ill.cargo_id = il.id
            JOIN purchase_order_line pol ON pol.id = ill.purchase_order_line_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE il.shipping_company IS NOT NULL AND il.shipping_company != ''
            GROUP BY 1, 2, 3, 4
            ORDER BY 5 DESC
            LIMIT 30
        """)
        ranking_navieras = []
        for r in cr.dictfetchall():
            g = self._fuel_group(r['prod_name'])
            if not g:
                continue
            ranking_navieras.append({
                'label': f"{r['naviera']} · {g} · {r['pais'] or '—'} · {r['puerto'] or '—'}",
                'cantidad': int(r['n']),
            })
        ranking_navieras = ranking_navieras[:5]

        # ---- Inteligencia comercial (P15-P20) ----
        # La acreditación REAL vive en res.partner.is_accredited (marcado por
        # la carga masiva y el wizard de acreditación). El stage del lead se
        # usa solo para separar "en aprobación" vs "potencial" entre los
        # leads cuyo partner todavía NO está acreditado.
        cr.execute("SELECT id, COALESCE(sequence, 0) AS seq FROM crm_stage")
        seq_by_stage = {r['id']: r['seq'] for r in cr.dictfetchall()}
        stages_en_aprobacion = [sid for sid, s in seq_by_stage.items() if s >= 2]
        stages_potenciales = [sid for sid, s in seq_by_stage.items() if s < 2]

        cr.execute("""
            SELECT l.en_party_role,
                   COALESCE(rp.is_accredited, false) AS is_accred,
                   l.stage_id,
                   COUNT(*) AS n
            FROM crm_lead l
            LEFT JOIN res_partner rp ON rp.id = l.partner_id
            WHERE l.active = true AND l.en_party_role IN ('client', 'supplier')
            GROUP BY 1, 2, 3
        """)
        buckets = {'client': {'acreditados': 0, 'en_aprobacion': 0, 'potenciales': 0},
                   'supplier': {'acreditados': 0, 'en_aprobacion': 0, 'potenciales': 0}}
        for r in cr.dictfetchall():
            role = r['en_party_role']
            n = int(r['n'])
            if r['is_accred']:
                buckets[role]['acreditados'] += n
            elif seq_by_stage.get(r['stage_id'], 0) >= 2:
                buckets[role]['en_aprobacion'] += n
            else:
                buckets[role]['potenciales'] += n

        def _pack(role_bucket, role_key):
            return {
                'acreditados': role_bucket['acreditados'],
                'en_aprobacion': role_bucket['en_aprobacion'],
                'potenciales': role_bucket['potenciales'],
                'role': role_key,
                'stages_en_aprobacion': stages_en_aprobacion,
                'stages_potenciales': stages_potenciales,
            }
        comercial = {
            'clientes': _pack(buckets['client'], 'client'),
            'proveedores': _pack(buckets['supplier'], 'supplier'),
        }

        # ---- Serviciadores: Aduana (P22) ----
        cr.execute("""
            SELECT COALESCE(SUM(dm_arancel_total), 0) AS aranceles_usd,
                   COALESCE(SUM(dm_servicio_aduana), 0) AS servicio_mn
            FROM pyxel_import_document
            WHERE dm_confirmed = true
        """)
        row = cr.dictfetchone() or {}
        aduana = {
            'aranceles_usd': float(row.get('aranceles_usd') or 0),
            'servicio_mn': float(row.get('servicio_mn') or 0),
        }

        # ---- Serviciadores: Navieras (P23) — solo lo derivable hoy ----
        # "No devuelto" = ya se extrajo el contenedor pero no se ha devuelto el
        # casco vacío a la naviera. state='to_extract' NO cuenta: ese estado es
        # "aún en el puerto, sin extraer" (otra cosa, ya cubierta en kpis.en_mariel).
        cr.execute("""
            SELECT UPPER(TRIM(shipping_company)) AS naviera, COUNT(*) AS n
            FROM importation_load
            WHERE shipping_company IS NOT NULL AND shipping_company != ''
              AND state = 'to_return'
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 20
        """)
        no_devueltos_por_naviera = [
            {'naviera': r['naviera'], 'no_devueltos': int(r['n']),
             'tramite_doc_usd': 0.0, 'no_devueltos_costo_usd': 0.0}
            for r in cr.dictfetchall()
        ]
        navieras_total = {
            'tramite_doc_usd': 0.0,
            'no_devueltos_count': sum(x['no_devueltos'] for x in no_devueltos_por_naviera),
            'no_devueltos_costo_usd': 0.0,
        }

        # ---- Serviciadores: Terminal de Contenedores (P24) ----
        # Mismo criterio que kpis.en_mariel: en puerto = llegó y no se ha
        # extraído, sin importar si ya está habilitado (ready_extract) o no.
        terminal_activos = self.search_count([('extraction_date', '=', False), ('arrival_date', '!=', False)])
        cr.execute("""
            SELECT COALESCE(AVG(days_in_tcm), 0) AS prom
            FROM (
                SELECT (extraction_date - arrival_date) AS days_in_tcm
                FROM importation_load
                WHERE arrival_date IS NOT NULL AND extraction_date IS NOT NULL
                  AND extraction_date >= (CURRENT_DATE - INTERVAL '12 months')
            ) t
        """)
        row = cr.dictfetchone() or {}
        terminal = {
            'estadia_facturada_mn': 0.0,
            'contenedores_activos': terminal_activos,
            'dias_promedio': round(float(row.get('prom') or 0), 1),
        }

        # ---- Ventas (P26 · P27) ----
        first_of_month = today.replace(day=1)
        first_of_year = today.replace(month=1, day=1)
        cr.execute("""
            SELECT
              COALESCE(SUM(amount_total) FILTER (WHERE invoice_date >= %s), 0) AS mes,
              COALESCE(SUM(amount_total) FILTER (WHERE invoice_date >= %s), 0) AS ytd
            FROM account_move
            WHERE state = 'posted' AND move_type = 'out_invoice'
              AND invoice_date >= %s
        """, (first_of_month, first_of_year, first_of_year))
        row = cr.dictfetchone() or {}
        ventas = {
            'facturado_mes': float(row.get('mes') or 0),
            'facturado_ytd': float(row.get('ytd') or 0),
            'refacturado_mes': 0.0,
        }

        # ---- CxC (P29) ----
        cr.execute("""
            SELECT rp.name AS cliente,
                   COALESCE(SUM(am.amount_residual), 0) AS saldo,
                   COALESCE(MAX(CURRENT_DATE - am.invoice_date_due), 0) AS dias
            FROM account_move am
            JOIN res_partner rp ON rp.id = am.partner_id
            WHERE am.state = 'posted' AND am.move_type = 'out_invoice'
              AND am.amount_residual > 0
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 10
        """)
        cxc = [{'cliente': r['cliente'], 'saldo': float(r['saldo']), 'dias': int(r['dias'])}
               for r in cr.dictfetchall()]

        # ---- CxP (P28) — sin agrupar por serviciador hasta Fase 2 ----
        cr.execute("""
            SELECT rp.name AS proveedor,
                   COALESCE(SUM(am.amount_residual), 0) AS saldo,
                   COALESCE(MAX(CURRENT_DATE - am.invoice_date_due), 0) AS dias
            FROM account_move am
            JOIN res_partner rp ON rp.id = am.partner_id
            WHERE am.state = 'posted' AND am.move_type = 'in_invoice'
              AND am.amount_residual > 0
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 10
        """)
        cxp = [{'proveedor': r['proveedor'], 'saldo': float(r['saldo']), 'dias': int(r['dias'])}
               for r in cr.dictfetchall()]

        return {
            'avance_reconciliacion': avance_reconciliacion,
            'totales': totales,
            'producto_estado_conteo': producto_estado_conteo,
            'producto_estado_volumen': producto_estado_volumen,
            'precios_promedio': precios_promedio,
            'ranking_proveedores': ranking_proveedores,
            'ranking_clientes': ranking_clientes,
            'ranking_navieras': ranking_navieras,
            'comercial': comercial,
            'aduana': aduana,
            'navieras_total': navieras_total,
            'no_devueltos_por_naviera': no_devueltos_por_naviera,
            'terminal': terminal,
            'ventas': ventas,
            'cxc': cxc,
            'cxp': cxp,
        }

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

    @api.constrains('name', 'bl_number')
    def _check_unique_container_per_bl(self):
        """Regla real de negocio: el número de contenedor SÍ puede repetirse
        (se reutiliza en distintos embarques), pero nunca dos veces con el
        mismo BL (mismo contenedor + mismo embarque)."""
        for record in self:
            if not record.name or not record.bl_number:
                continue

            duplicate = self.search([
                ('name', '=', record.name),
                ('bl_number', '=', record.bl_number),
                ('id', '!=', record.id)
            ], limit=1)

            if duplicate:
                raise ValidationError(
                    f"El contenedor '{record.name}' con BL '{record.bl_number}' ya existe."
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
