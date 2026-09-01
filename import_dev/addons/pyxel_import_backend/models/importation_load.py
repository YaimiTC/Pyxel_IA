import base64
import csv
import datetime
import io
import json
import re
import zipfile
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

# Desde cuándo cuentan los desgloses MENSUALES del tablero: huérfanos,
# extraídos y pendientes de extraer (pedido de Operaciones, ago-2026). Lo
# anterior a esta fecha es backlog histórico que ya no se reconcilia; aparecía
# mes a mes y solo servía para empujar hacia abajo los meses que sí se trabajan.
#
# NO afecta al bloque «Histórico de contenedores devueltos por mes», que sigue
# con su ventana de 12 meses móviles: ahí la pregunta es otra (cuántos se
# devolvieron de lo que se extrajo) y recortarlo dejaría el histórico manco.
#
# Va como literal en el SQL y no como parámetro a propósito: esas consultas
# interpolan `venta_sql_il_noparam`, que lleva un `%` suelto en el ILIKE, y en
# cuanto se les pasa un parámetro psycopg2 intenta interpolarlo y revienta. De
# ahí el sufijo `_noparam` de esa variable.
DESGLOSE_DESDE = '2026-02-01'


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

    active = fields.Boolean(default=True)
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
    packaging_type_id = fields.Many2one('importation.packaging.type', string='Tipo de envase')
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
    mbl_release_partner = fields.Char(
        string='Consignatario liberación Master BL',
        help="Columna H del reporte de la Terminal: a nombre de quién figura "
             "la liberación del Master BL. Puede ser un tercero (EMSERPET, "
             "PALCO, EXPEDIMAR...) sin que el contenedor deje de ser nuestro.")

    # Marca interna: el reporte de la Terminal ha reconocido este contenedor
    # como nuestro. Una vez encendida NO se apaga porque una corrida traiga el
    # contenedor a nombre de un tercero: la pertenencia la decide que el
    # embarque esté cargado en el sistema, no el nombre de la columna H o J.
    belongs_to_us = fields.Boolean(
        string='Reconocido como nuestro en el reporte', default=False, copy=False)
    created_by_terminal_report = fields.Boolean(
        string='Creado por la sincronización', default=False, copy=False,
        help="El contenedor lo creó una corrida del reporte de la Terminal, no "
             "la carga de importaciones. Sirve para saber de dónde salió cada "
             "contenedor sin tener que rastrear los reportes antiguos.")
    terminal_last_seen = fields.Date(
        string='Visto en el reporte por última vez', copy=False,
        help="Fecha de la última corrida en que el reporte de la Terminal "
             "trajo este contenedor. El reporte es una ventana, no un censo: "
             "purga filas sin avisar. Con esta fecha se distingue 'nunca "
             "estuvo en el reporte' de 'estuvo y dejó de venir'.")
    handled_by_third_party = fields.Boolean(
        string='Tramitado por un tercero', default=False, copy=False,
        help="La última corrida trajo este contenedor con otra empresa en las "
             "columnas H/J del reporte de la Terminal. Sigue siendo nuestro y "
             "se sincroniza igual; sirve para saber por qué vía se despachó.")

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
    is_ventanilla = fields.Boolean(string='Se tramita por Ventanilla')
    ventanilla_date = fields.Date(string='Fecha de Ventanilla')

    @api.constrains('is_ventanilla', 'ventanilla_date')
    def _check_ventanilla_date(self):
        today = fields.Date.context_today(self)
        for record in self:
            if not record.is_ventanilla:
                continue
            if not record.ventanilla_date:
                raise ValidationError("Falta la fecha de Ventanilla.")
            if record.ventanilla_date < today:
                raise ValidationError("La fecha de Ventanilla no puede ser anterior a hoy.")

    @api.constrains('packaging_type_id', 'cargo_line_ids', 'cargo_line_ids.product_id')
    def _check_packaging_type_product(self):
        for record in self:
            envase = record.packaging_type_id
            if not envase or not envase.allowed_product_ids:
                continue  # sin tabla configurada para este envase = sin restriccion
            for linea in record.cargo_line_ids:
                producto = linea.product_id
                if not producto or producto.detailed_type == 'service':
                    continue  # servicios no tienen restricción de tipo de envase
                if producto not in envase.allowed_product_ids:
                    raise ValidationError(
                        f"El envase '{envase.name}' no admite el producto '{producto.name}'. "
                        f"Productos permitidos: {', '.join(envase.allowed_product_ids.mapped('name'))}.")

    transport_company = fields.Char(string='Transport Company')
    province = fields.Char(string='Province')
    province_norm = fields.Char(
        string='Provincia (normalizada)', compute='_compute_province_norm', store=True,
        help="'province' tal como llega de la Terminal, en mayúsculas, sin "
             "acentos y sin el municipio cuando viene como 'MUNICIPIO(PROVINCIA)'. "
             "Se usa para casar con la provincia de los destinos.")
    truck_plate = fields.Char(string='Truck')
    destination_domain = fields.Char(compute='_compute_destination_domain')
    destination_id = fields.Many2one(
        'importation.destination', string='Destino', domain="destination_domain")
    destination_is_own = fields.Boolean(related='destination_id.is_own_destination', string='Es destino propio')
    destination_own_text = fields.Char(
        string='Destino propio (detalle)',
        help="Cuando el destino elegido es 'Propio', aquí comercial describe "
             "el destino propio del cliente.")
    driver = fields.Char(string='Driver')

    @api.depends('province')
    def _compute_province_norm(self):
        import unicodedata
        for record in self:
            v = (record.province or '').strip().upper()
            if '(' in v and ')' in v:
                v = v[v.index('(') + 1:v.index(')')].strip()
            v = ''.join(c for c in unicodedata.normalize('NFKD', v) if not unicodedata.combining(c))
            if v == 'HABANA':
                v = 'LA HABANA'
            record.province_norm = v or False

    @api.depends('province_norm')
    def _compute_destination_domain(self):
        for record in self:
            if record.province_norm:
                record.destination_domain = json.dumps(
                    ['|', ('province', '=', False), ('province', '=', record.province_norm)])
            else:
                record.destination_domain = json.dumps([])

    @api.onchange('destination_id')
    def _onchange_destination_id(self):
        if not self.destination_id.is_own_destination:
            self.destination_own_text = False

    @api.constrains('destination_id', 'destination_own_text')
    def _check_destination_own_text(self):
        for record in self:
            if record.destination_id.is_own_destination and not record.destination_own_text:
                raise ValidationError(
                    "El destino 'Propio' necesita el detalle en 'Destino propio'.")

    # Datos del depósito de recepción. Por ahora se llenan a mano; está
    # pendiente sincronizarlos desde un fichero (BL + contenedor), igual que
    # el reporte de la Terminal, cuando exista un fichero de muestra real.
    deposit_code = fields.Char(
        string='Código de depósito', size=7,
        help="Consecutivo de la operación de recepción: 2 dígitos de código "
             "de destino + 5 dígitos de consecutivo (7 dígitos en total).")
    deposit_quantity_received = fields.Float(string='Cantidad real recibida (L)')
    deposit_reception_datetime = fields.Datetime(string='Fecha y hora de recepción en depósito')
    deposit_unload_start_datetime = fields.Datetime(string='Fecha y hora de inicio de descarga')
    deposit_unload_end_datetime = fields.Datetime(string='Fecha y hora de fin de descarga')
    deposit_observations = fields.Text(string='Observaciones del depósito')
    deposit_quality_certificate_number = fields.Char(string='N.° certificado de calidad en destino')

    @api.constrains('deposit_code')
    def _check_deposit_code(self):
        for record in self:
            if record.deposit_code and not re.fullmatch(r'\d{7}', record.deposit_code):
                raise ValidationError(
                    "El código de depósito debe tener 7 dígitos "
                    "(2 del destino + 5 del consecutivo).")

    # Líneas de producto asignadas a la carga (fracción de ordenes de compra)
    cargo_line_ids = fields.One2many('importation.load.line', 'cargo_id', string='Products transported')
    cargo_line_count = fields.Integer(string='Líneas de productos', compute='_compute_cargo_line_count')
    total_cargo_line = fields.Float(string='Amount of line', compute='_compute_total_cargo_line')
    product_names = fields.Char(string='Producto(s)', compute='_compute_product_names', store=True)

    @api.depends('cargo_line_ids')
    def _compute_cargo_line_count(self):
        for rec in self:
            rec.cargo_line_count = len(rec.cargo_line_ids)

    @api.depends('cargo_line_ids.product_id')
    def _compute_product_names(self):
        for rec in self:
            nombres = sorted(set(rec.cargo_line_ids.mapped('product_id.name')))
            rec.product_names = ', '.join(nombres) if nombres else False

    expected_quantity = fields.Float(
        string='Cantidad según factura (L)', compute='_compute_expected_quantity', store=True,
        help="Suma de las lineas de carga (lo esperado segun la OC/factura). "
             "No confundir con deposit_quantity_received, que es lo que el "
             "deposito confirma que llego de verdad.")

    @api.depends('cargo_line_ids.quantity')
    def _compute_expected_quantity(self):
        for rec in self:
            rec.expected_quantity = sum(rec.cargo_line_ids.mapped('quantity'))

    pending_alloc_warning = fields.Char(
        string='Alerta de asignación',
        compute='_compute_pending_alloc_warning',
        store=False,
    )

    @api.depends(
        'importation_id',
        'importation_id.purchase_order_ids.order_line.product_uom_qty',
        'importation_id.purchase_order_ids.order_line.quantity_allocated',
    )
    def _compute_pending_alloc_warning(self):
        for rec in self:
            if not rec.importation_id:
                rec.pending_alloc_warning = False
                continue
            pendientes = []
            for po in rec.importation_id.purchase_order_ids:
                for line in po.order_line:
                    if line.display_type:
                        continue
                    remaining = (line.product_uom_qty or 0.0) - (line.quantity_allocated or 0.0)
                    if remaining > 0.001:
                        uom = line.product_uom.name or ''
                        pendientes.append(
                            f"{po.name} / {line.product_id.display_name}: "
                            f"{remaining:,.2f} {uom} sin contenedor"
                        )
            rec.pending_alloc_warning = ' | '.join(pendientes) if pendientes else False

    customer_pyxel_code = fields.Integer(related='customer_id.id', string='Código del propietario (Pyxel)')

    readiness_date = fields.Date(
        string='Fecha probable de extracción', compute='_compute_readiness', store=True,
        help="La mas próxima entre precita, cita y ventanilla. Vacío si "
             "todavía no tiene ninguna (llegó pero no está habilitado).")
    readiness_source = fields.Char(
        string='Origen de la fecha', compute='_compute_readiness', store=True,
        help="Precita, Cita o Ventanilla: de cual de los tres campos sale readiness_date.")

    @api.depends('pre_appointment_date', 'appointment_date', 'is_ventanilla', 'ventanilla_date')
    def _compute_readiness(self):
        for rec in self:
            candidatas = []
            if rec.pre_appointment_date:
                candidatas.append(('Precita', rec.pre_appointment_date))
            if rec.appointment_date:
                candidatas.append(('Cita', rec.appointment_date))
            if rec.is_ventanilla and rec.ventanilla_date:
                candidatas.append(('Ventanilla', rec.ventanilla_date))
            candidatas.sort(key=lambda x: x[1])
            if candidatas:
                rec.readiness_source, rec.readiness_date = candidatas[0]
            else:
                rec.readiness_source, rec.readiness_date = False, False

    # Columnas del CSV de ida y vuelta con el deposito: las primeras 12 las
    # llena Pyxel (listado de salida), las ultimas 7 quedan vacias para que
    # el deposito las llene y nos devuelva el MISMO fichero -- asi no hace
    # falta que el deposito nos defina un formato propio, el cruce de vuelta
    # (import_deposit_from_file) lee estas mismas columnas.
    DEPOSIT_CSV_COLUMNAS_SALIDA = [
        'contenedor', 'bl', 'tipo_envase', 'codigo_propietario', 'nit_cliente',
        'cliente', 'producto', 'cantidad_factura', 'fecha_llegada',
        'tipo_habilitacion', 'fecha_habilitacion', 'estado',
    ]
    DEPOSIT_CSV_COLUMNAS_RETORNO = [
        'codigo_deposito', 'cantidad_recibida', 'fecha_recepcion',
        'fecha_inicio_descarga', 'fecha_fin_descarga', 'observaciones',
        'certificado_calidad',
    ]

    def action_export_deposit_package(self):
        """Genera el CSV para el deposito (columnas de salida llenas, las de
        retorno vacias) + el certificado de calidad de cada contenedor si
        existe como adjunto, todo en un zip para descarga manual. Ver
        seccion 2.4 y 5 (Etapa 1) de la Contrapropuesta Tecnica SIOC."""
        if not self:
            raise UserError("Selecciona los contenedores a exportar primero.")

        buf_csv = io.StringIO()
        writer = csv.writer(buf_csv, delimiter=';')
        writer.writerow(self.DEPOSIT_CSV_COLUMNAS_SALIDA + self.DEPOSIT_CSV_COLUMNAS_RETORNO)
        for rec in self:
            writer.writerow([
                rec.name or '',
                rec.bl_number or '',
                rec.packaging_type_id.name or '',
                rec.customer_pyxel_code or '',
                rec.customer_vat or '',
                rec.customer_id.name or '',
                rec.product_names or '',
                rec.expected_quantity or '',
                rec.arrival_date or '',
                rec.readiness_source or '',
                rec.readiness_date or '',
                rec.state or '',
            ] + [''] * len(self.DEPOSIT_CSV_COLUMNAS_RETORNO))

        buf_zip = io.BytesIO()
        with zipfile.ZipFile(buf_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('reporte_depositos.csv', buf_csv.getvalue().encode('utf-8-sig'))
            Attachment = self.env['ir.attachment']
            for rec in self:
                adjuntos = Attachment.search([
                    ('res_model', '=', 'importation.load'), ('res_id', '=', rec.id)])
                if rec.importation_id:
                    adjuntos |= Attachment.search([
                        ('res_model', '=', 'purchase.order'),
                        ('res_id', 'in', rec.importation_id.purchase_order_ids.ids)])
                for att in adjuntos:
                    if att.mimetype != 'application/pdf':
                        continue
                    nombre = f"certificados/{rec.name}_{att.name}"
                    zf.writestr(nombre, base64.b64decode(att.datas))

        adjunto = self.env['ir.attachment'].create({
            'name': 'reporte_depositos.zip',
            'type': 'binary',
            'datas': base64.b64encode(buf_zip.getvalue()),
            'mimetype': 'application/zip',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{adjunto.id}?download=true',
            'target': 'self',
        }

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
    customer_vat = fields.Char(related='customer_id.vat', string='NIT del cliente')
    carrier = fields.Char(
        string='Naviera/Transitoria/Aerolínea', compute='_compute_carrier')

    buyer_ids = fields.Many2many(
        'res.users', string='Comercial(es)', compute='_compute_buyer_ids',
        store=True, readonly=False,
        help="Comprador de la(s) OC realmente vinculada(s) a este contenedor "
             "a través de sus líneas de carga -- no todas las OC del proceso, "
             "solo las que tienen mercancía en este contenedor. Puede haber "
             "más de un comercial si el contenedor trae carga de varias OC.")

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

    @api.depends('cargo_line_ids.purchase_order_line_id.order_id.user_id')
    def _compute_buyer_ids(self):
        for record in self:
            buyers = record.cargo_line_ids.mapped('purchase_order_line_id.order_id.user_id')
            if buyers:
                record.buyer_ids = buyers

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
        # Si ya existe un contenedor huerfano (creado por la sincronizacion
        # TCM, sin importation_id) con el mismo name+bl_number, no crear un
        # duplicado -- eso siempre chocaria con _check_unique_container_per_bl.
        # Se adopta ese registro: se le escriben los datos que llegan aqui
        # (incluido importation_id) en vez de crear uno nuevo. Si el huerfano
        # ya tiene importation_id, se deja seguir a create() normal, que
        # fallara con el mensaje de _check_unique_container_per_bl indicando
        # a que importacion pertenece.
        name = vals.get('name')
        bl_number = vals.get('bl_number')
        res = None
        if name and bl_number:
            huerfano = self.search([
                ('name', '=', name),
                ('bl_number', '=', bl_number),
                ('importation_id', '=', False),
            ], limit=1)
            if huerfano:
                huerfano.write(vals)
                res = huerfano

        if res is None:
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
    def get_dashboard_data(self, venta_enetec_only=False):
        from odoo.osv import expression
        today = fields.Date.today()
        from datetime import timedelta

        # Filtro reutilizable "Tablero Venta ENETEC": mismo criterio que los
        # bloques venta_enetec_* de _get_dashboard_extension (customer_id.name
        # empieza por "VENTA ENETEC"), aplicado aqui a TODO el tablero cuando
        # se pide el modo venta_enetec_only=True. Con el flag en False (modo
        # normal, default) todos estos fragmentos quedan vacios y no cambian
        # ni un numero del tablero actual.
        # Dos variantes del fragmento SQL porque psycopg2 hace su propia
        # sustitucion %-style cuando cr.execute() recibe parametros (ahi hace
        # falta escapar el % como %%); en las consultas que NO pasan
        # parametros a cr.execute(), el % debe ir simple o Postgres lo
        # tomaria literal (dos "%" en vez de un comodin de LIKE).
        if venta_enetec_only:
            _g = ("il.importation_id IN (SELECT id FROM importation_process"
                  " WHERE comercial_id IN (SELECT ru.id FROM res_users ru"
                  " JOIN res_partner rp_g ON rp_g.id = ru.partner_id"
                  " WHERE rp_g.name ILIKE '%%Gabriela%%'))")
            _g_np = ("il.importation_id IN (SELECT id FROM importation_process"
                     " WHERE comercial_id IN (SELECT ru.id FROM res_users ru"
                     " JOIN res_partner rp_g ON rp_g.id = ru.partner_id"
                     " WHERE rp_g.name ILIKE '%Gabriela%'))")
            venta_domain = ['|',
                ('customer_id.name', 'like', 'VENTA ENETEC%'),
                ('importation_id.comercial_id.name', 'ilike', 'Gabriela')]
            venta_sql_il = (
                "AND (EXISTS (SELECT 1 FROM res_partner rp WHERE rp.id = il.customer_id"
                f" AND rp.name ILIKE 'VENTA ENETEC%%') OR {_g})")
            venta_sql_il_noparam = (
                "AND (EXISTS (SELECT 1 FROM res_partner rp WHERE rp.id = il.customer_id"
                f" AND rp.name ILIKE 'VENTA ENETEC%') OR {_g_np})")
        else:
            venta_domain = []
            venta_sql_il = ""
            venta_sql_il_noparam = ""

        def ultima_fecha(campo):
            """El fichero de la Terminal sincroniza una vez, a medianoche:
            nunca trae el dia de hoy, solo hasta la ultima corrida. Comparar
            estos campos contra `today` da siempre cero. Se usa en su lugar
            la fecha mas reciente que de verdad trae ese campo — el "hoy" de
            los datos, no el del calendario.

            Adrede SIN venta_domain aunque venta_enetec_only=True: esta fecha
            representa cuándo corrió la última sincronización de TODA la
            Terminal (un hecho del sistema, no de un cliente puntual). Si se
            filtrara por VENTA ENETEC, un día sin extracciones de ese cliente
            en particular haría parecer que la sincronización está atrasada
            cuando en realidad no lo está -- desalinearía 'hoy_operativo' y
            'extraidos_hoy'/'plan_hoy' entre los dos tableros sin necesidad.
            """
            r = self.search_read([(campo, '!=', False)], [campo],
                                  order='%s desc' % campo, limit=1)
            return r[0][campo] if r else today

        fecha_extraccion = ultima_fecha('extraction_date')
        fecha_cita = ultima_fecha('appointment_date')
        fecha_precita = ultima_fecha('pre_appointment_date')
        fecha_habilitacion = ultima_fecha('release_date')

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

        # Plan: pendientes con cita o ventanilla (sin precita), sin limite de fecha pasada.
        # Se usan dos busquedas separadas para evitar expression.OR con sub-dominios
        # multiples, que genera una lista plana incorrecta al concatenar.
        d3_plan = today + timedelta(days=3)
        _appt_dom = expression.AND([[
            ('extraction_date', '=', False),
            ('appointment_date', '!=', False),
            ('appointment_date', '<', d3_plan),
        ], venta_domain])
        _vent_dom = expression.AND([[
            ('extraction_date', '=', False),
            ('is_ventanilla', '=', True),
            ('ventanilla_date', '!=', False),
            ('ventanilla_date', '<', d3_plan),
        ], venta_domain])
        plan_ids = list(set(self.search(_appt_dom).ids) | set(self.search(_vent_dom).ids))

        kpis = {
            'en_mariel': self.search_count(expression.AND([in_port, venta_domain])),
            'habilitados': self.search_count(expression.AND([
                in_port, [('pre_appointment_date', '!=', False)], venta_domain,
            ])),
            'extraidos_hoy': self.search_count(expression.AND([
                [('extraction_date', '=', fecha_extraccion)], venta_domain,
            ])),
            'sin_habilitar': self.search_count(expression.AND([
                in_port, [('pre_appointment_date', '=', False)], venta_domain,
            ])),
            'plan_hoy': len(plan_ids),
        }

        aging = {
            'de_0_4': self.search_count(expression.AND([in_port, [('arrival_date', '>=', d4)], venta_domain])),
            'de_5_9': self.search_count(expression.AND([
                in_port, [('arrival_date', '>=', d9), ('arrival_date', '<', d4)], venta_domain,
            ])),
            'de_10_19': self.search_count(expression.AND([
                in_port, [('arrival_date', '>=', d19), ('arrival_date', '<', d9)], venta_domain,
            ])),
            'de_20_29': self.search_count(expression.AND([
                in_port, [('arrival_date', '>=', d29), ('arrival_date', '<', d19)], venta_domain,
            ])),
            'de_30_mas': self.search_count(expression.AND([in_port, [('arrival_date', '<', d29)], venta_domain])),
        }
        aging['total'] = sum(aging.values()) or 1

        plan_records = self.search_read(
            [('id', 'in', plan_ids)],
            ['name', 'bl_number', 'provider_ids', 'product_names',
             'pre_appointment_date', 'appointment_date', 'is_ventanilla', 'ventanilla_date',
             'importation_id', 'destination_id', 'transport_company', 'days_in_tcm'],
        )
        provider_ids_all = {pid for r in plan_records for pid in r.get('provider_ids') or []}
        provider_names = {
            p['id']: p['name']
            for p in self.env['res.partner'].search_read([('id', 'in', list(provider_ids_all))], ['name'])
        }
        for r in plan_records:
            if r.get('importation_id'):
                proc = self.env['importation.process'].browse(r['importation_id'][0])
                r['customer'] = proc.customer_id.name or ''
            else:
                r['customer'] = ''
            r['destination'] = r['destination_id'][1] if r.get('destination_id') else ''
            r['providers'] = ', '.join(
                provider_names[pid] for pid in (r.get('provider_ids') or []) if pid in provider_names
            )
            # De las tres fechas, la que cae dentro de la ventana hoy..+3 dias
            # es la que se muestra; si mas de una cae dentro, se prioriza la
            # mas próxima.
            candidatas = []
            if r['appointment_date']:
                candidatas.append(('Cita', r['appointment_date']))
            if r['is_ventanilla'] and r['ventanilla_date']:
                candidatas.append(('Ventanilla', r['ventanilla_date']))

            candidatas.sort(key=lambda x: x[1])
            fuente, fecha_plan = candidatas[0] if candidatas else ('', None)
            r['plan_fuente'] = fuente
            r['plan_fecha'] = str(fecha_plan) if fecha_plan else ''
            r['appointment_date'] = str(r['appointment_date']) if r['appointment_date'] else ''
            r['pre_appointment_date'] = str(r['pre_appointment_date']) if r['pre_appointment_date'] else ''
            r['ventanilla_date'] = str(r['ventanilla_date']) if r['ventanilla_date'] else ''
        # Por dia (fecha del plan) y, dentro del mismo dia, por dias en el
        # Terminal de mayor a menor -- el que lleva mas tiempo esperando va
        # primero. Antes solo ordenaba por fecha: los contenedores del mismo
        # dia quedaban en el orden que devolviera la busqueda (por id), sin
        # relacion con cuanto tiempo llevaban en el puerto.
        plan_records.sort(key=lambda r: (r['plan_fecha'] or '9999', -(r['days_in_tcm'] or 0)))

        alertas = {
            'precita_vencida': self.search_count(expression.AND([
                [('appointment_date', '<', today), ('appointment_date', '!=', False), ('extraction_date', '=', False)],
                venta_domain,
            ])),
            'sin_identificar': self.search_count(expression.AND([
                [('arrival_date', '!=', False), ('transit_agency', '=', False), ('extraction_date', '=', False)],
                venta_domain,
            ])),
            'envejecidos': self.search_count(expression.AND([in_port, [('arrival_date', '<', d30)], venta_domain])),
            'sin_habilitar': self.search_count(expression.AND([in_port, [('pre_appointment_date', '=', False)], venta_domain])),
        }

        def _del_dia(campo_fecha, fecha):
            # cargo_type NO es el producto (solo guarda 'dry'/'reefer', el
            # tipo de contenedor): el producto real esta en la linea de
            # carga -> linea de OC -> producto. Se toma la primera linea de
            # cada contenedor, igual que en el resto del tablero.
            assert campo_fecha in ("release_date", "extraction_date")
            # f-string en vez de "% campo_fecha": asi el %% de venta_sql_il
            # (pensado para que psycopg2 lo colapse a % al sustituir el %s de
            # abajo) no se procesa dos veces -- el f-string no toca los
            # caracteres %, solo {campo_fecha}/{venta_sql_il}.
            self.env.cr.execute(f"""
                SELECT il.id,
                       (SELECT pt.name->>'en_US'
                          FROM importation_load_line ill
                          JOIN purchase_order_line pol
                               ON pol.id = ill.purchase_order_line_id
                          JOIN product_product pp ON pp.id = pol.product_id
                          JOIN product_template pt ON pt.id = pp.product_tmpl_id
                         WHERE ill.cargo_id = il.id
                         ORDER BY ill.id LIMIT 1) AS prod_name
                  FROM importation_load il
                 WHERE il.{campo_fecha} = %s
                 {venta_sql_il}
            """, (fecha,))
            return self.env.cr.dictfetchall()

        del_dia_hab = _del_dia("release_date", fecha_habilitacion)
        del_dia_ext = _del_dia("extraction_date", fecha_extraccion)

        def summarize_del_dia(records):
            """Cuenta por combustible y guarda QUÉ contenedores son cada cifra.

            Los ids viajan al cliente para que al pinchar una celda se abra
            exactamente ese conjunto. La alternativa —rehacer el filtro como
            dominio de Odoo— no es viable: el reparto por combustible no sale
            de un campo, lo decide `_fuel_group` mirando el nombre del producto
            ('gasolina' + '91', 'diesel', 'jet'...) a través de línea de carga →
            línea de OC → producto. Un dominio que imitara eso sería una
            segunda implementación de la misma heurística, y el día que una
            cambiara la tabla y la lista dirían cosas distintas.
            """
            cubos = {'DIESEL': [], 'GASOLINA': [], 'GLP': [], 'OTRO': []}
            for r in records:
                grupo = self._fuel_group(r.get('prod_name'))
                if grupo == 'Diésel':
                    cubos['DIESEL'].append(r['id'])
                elif grupo in ('Gasolina', 'Gasolina 91', 'Gasolina 83'):
                    cubos['GASOLINA'].append(r['id'])
                elif grupo == 'GLP':
                    cubos['GLP'].append(r['id'])
                else:
                    cubos['OTRO'].append(r['id'])
            counts = {k: len(v) for k, v in cubos.items()}
            counts['total'] = sum(counts.values())
            counts['ids'] = {k: v for k, v in cubos.items()}
            counts['ids']['total'] = [i for v in cubos.values() for i in v]
            return counts

        # Histórico: extraídos y retornados por mes (últimos 12 meses)
        self.env.cr.execute(f"""
            SELECT
                TO_CHAR(il.extraction_date, 'YYYY-MM') AS mes,
                TO_CHAR(il.extraction_date, 'Mon YYYY') AS mes_label,
                COUNT(*) AS extraidos,
                COUNT(*) FILTER (WHERE il.return_date IS NOT NULL) AS retornados,
                ROUND(AVG(il.extraction_date - il.arrival_date)) AS dias_prom
            FROM importation_load il
            WHERE il.extraction_date >= (CURRENT_DATE - INTERVAL '12 months')
              AND il.extraction_date IS NOT NULL
              {venta_sql_il_noparam}
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

        ext = self._get_dashboard_extension(today, venta_enetec_only=venta_enetec_only)

        return {
            'venta_enetec_only': venta_enetec_only,
            'kpis': kpis,
            'aging': aging,
            'plan': plan_records,
            'alertas': alertas,
            'del_dia_hab': summarize_del_dia(del_dia_hab),
            'del_dia_ext': summarize_del_dia(del_dia_ext),
            'historico': historico,
            # La Terminal sincroniza una vez al dia: estas son las fechas
            # reales que usan 'extraidos_hoy', 'plan_hoy', del_dia_hab y
            # del_dia_ext, no necesariamente el dia de hoy del calendario.
            'fecha_extraccion': str(fecha_extraccion),
            'fecha_cita': str(fecha_cita),
            'fecha_precita': str(fecha_precita),
            'fecha_habilitacion': str(fecha_habilitacion),
            'view_extraidos_id': self.env.ref('pyxel_import_backend.view_importation_load_tree_extraidos').id,
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
    def _get_dashboard_extension(self, today, venta_enetec_only=False):
        """Bloques del tablero pedidos por Operaciones (docx TABLERO 02/06/2026).
        Se calcula con datos ya existentes; los bloques que dependen de
        estructura por crear (trámite documentario, refacturación, categorías
        de serviciador) devuelven 0 hasta la Fase 2."""
        from odoo.osv import expression
        cr = self.env.cr

        # Mismo filtro reutilizable "Tablero Venta ENETEC" que get_dashboard_data
        # (ver comentario allá para el porqué de las variantes %/%%). Se repite
        # aquí porque este método corre en su propio scope.
        if venta_enetec_only:
            _g = ("il.importation_id IN (SELECT id FROM importation_process"
                  " WHERE comercial_id IN (SELECT ru.id FROM res_users ru"
                  " JOIN res_partner rp_g ON rp_g.id = ru.partner_id"
                  " WHERE rp_g.name ILIKE '%%Gabriela%%'))")
            _g_np = ("il.importation_id IN (SELECT id FROM importation_process"
                     " WHERE comercial_id IN (SELECT ru.id FROM res_users ru"
                     " JOIN res_partner rp_g ON rp_g.id = ru.partner_id"
                     " WHERE rp_g.name ILIKE '%Gabriela%'))")
            venta_domain = ['|',
                ('customer_id.name', 'like', 'VENTA ENETEC%'),
                ('importation_id.comercial_id.name', 'ilike', 'Gabriela')]
            venta_sql_il = (
                "AND (EXISTS (SELECT 1 FROM res_partner rp WHERE rp.id = il.customer_id"
                f" AND rp.name ILIKE 'VENTA ENETEC%%') OR {_g})")
            venta_sql_il_noparam = (
                "AND (EXISTS (SELECT 1 FROM res_partner rp WHERE rp.id = il.customer_id"
                f" AND rp.name ILIKE 'VENTA ENETEC%') OR {_g_np})")
        else:
            venta_domain = []
            venta_sql_il = ""
            venta_sql_il_noparam = ""
        # Variantes para las consultas sobre account_move que ya hacen JOIN a
        # res_partner (rp): mismo criterio, sin el EXISTS/customer_id porque
        # aquí el vínculo con el cliente ya viene dado por am.partner_id.
        venta_sql_am = "AND rp.name ILIKE 'VENTA ENETEC%%'" if venta_enetec_only else ""
        venta_sql_am_noparam = "AND rp.name ILIKE 'VENTA ENETEC%'" if venta_enetec_only else ""

        # ---- Avance de reconciliación: contenedores sin datos comerciales ----
        # Util para medir el avance dia a dia mientras se cargan operaciones
        # sin proceso (contenedores huerfanos importados desde reportes de
        # la Terminal).
        avance_reconciliacion = {
            'total': self.search_count(venta_domain),
            'sin_importacion': self.search_count(expression.AND([
                [('importation_id', '=', False)], venta_domain,
            ])),
            'sin_proveedor': self.search_count(expression.AND([
                [('provider_ids', '=', False)], venta_domain,
            ])),
            # Nota: con venta_enetec_only=True esto siempre da 0 (un registro
            # no puede a la vez no tener cliente y tener cliente "VENTA
            # ENETEC%") -- es el comportamiento correcto para ese modo, no un bug.
            'sin_cliente': self.search_count(expression.AND([
                [('customer_id', '=', False)], venta_domain,
            ])),
            'sin_cliente_ni_proveedor': self.search_count(expression.AND([
                [('customer_id', '=', False), ('provider_ids', '=', False)], venta_domain,
            ])),
        }

        # ---- Huérfanos por mes (pedido por Operaciones) ----
        # Se agrupa por el mes de llegada (arrival_date), no por la fecha en
        # que se cargó el registro: lo que le interesa a Operaciones es de
        # qué mes de arribo es el backlog pendiente, no cuándo se sincronizó.
        # Desde DESGLOSE_DESDE: lo anterior es backlog histórico cerrado.
        cr.execute(f"""
            SELECT TO_CHAR(il.arrival_date, 'YYYY-MM') AS mes,
                   TO_CHAR(il.arrival_date, 'Mon YYYY') AS mes_label,
                   COUNT(*) AS n
            FROM importation_load il
            WHERE il.importation_id IS NULL AND il.arrival_date IS NOT NULL
              AND il.arrival_date >= DATE '{DESGLOSE_DESDE}'
            {venta_sql_il_noparam}
            GROUP BY 1, 2
            ORDER BY 1
        """)
        huerfanos_por_mes = [
            {'mes': r['mes'], 'label': r['mes_label'], 'n': r['n']}
            for r in cr.dictfetchall()
        ]
        # El total de la tarjeta cuenta TODOS los huérfanos y la lista solo los
        # de DESGLOSE_DESDE en adelante: sin decirlo, el usuario ve un número
        # que no cuadra con la suma de abajo y no sabe por qué. Se manda el
        # recorte al cliente para que lo escriba en la propia tarjeta.
        huerfanos_en_lista = sum(r['n'] for r in huerfanos_por_mes)

        # ---- Extraídos y pendientes de extraer, por mes ----
        # Cada uno se agrupa por la fecha que le da sentido, y NO son la misma:
        #   extraído  -> por extraction_date, el mes en que salió del puerto
        #   pendiente -> por arrival_date, porque no tiene fecha de extracción;
        #                lo que interesa es desde qué mes lleva esperando
        # Agruparlos los dos por arrival_date pondría los extraídos en el mes
        # en que llegaron y no en el que se movieron, que es lo que se mide.
        def _por_mes(campo_fecha, extra_where):
            cr.execute(f"""
                SELECT TO_CHAR(il.{campo_fecha}, 'YYYY-MM') AS mes,
                       TO_CHAR(il.{campo_fecha}, 'Mon YYYY') AS mes_label,
                       COUNT(*) AS n
                FROM importation_load il
                WHERE il.{campo_fecha} IS NOT NULL
                  AND il.{campo_fecha} >= DATE '{DESGLOSE_DESDE}'
                  {extra_where}
                {venta_sql_il_noparam}
                GROUP BY 1, 2
                ORDER BY 1
            """)
            return [{'mes': r['mes'], 'label': r['mes_label'], 'n': r['n']}
                    for r in cr.dictfetchall()]

        extraidos_por_mes = _por_mes('extraction_date', '')
        pendientes_por_mes = _por_mes(
            'arrival_date', 'AND il.extraction_date IS NULL')

        # ---- VENTA (customer_id.name empieza por "VENTA ENETEC") extraídos
        # y pendientes de extraer, por provincia y por transportista
        # (pedido por Operaciones para el PDF del tablero) ----
        # Estos 4 sub-bloques YA filtran siempre por "VENTA ENETEC", sin
        # depender de venta_enetec_only -- no se tocan al agregar el Tablero
        # Venta ENETEC (aplicarles venta_sql_il encima seria filtrar dos
        # veces por la misma condición, redundante pero no incorrecto; se
        # deja tal cual para no complicar sin necesidad).
        venta_enetec_cliente = """
            EXISTS (
                SELECT 1 FROM res_partner rp
                WHERE rp.id = il.customer_id AND rp.name ILIKE 'VENTA ENETEC%%'
            )
        """

        def _venta_enetec_por(campo, default_label, extraido):
            filtro_extraccion = "il.extraction_date IS NOT NULL" if extraido else \
                "il.extraction_date IS NULL AND il.arrival_date IS NOT NULL"
            cr.execute(f"""
                SELECT COALESCE(il.{campo}, %s) AS etiqueta, COUNT(*) AS n
                FROM importation_load il
                WHERE {filtro_extraccion} AND {venta_enetec_cliente}
                GROUP BY 1 ORDER BY 2 DESC
            """, (default_label,))
            return [{'label': r['etiqueta'], 'n': r['n']} for r in cr.dictfetchall()]

        venta_enetec_extraidos_por_provincia = _venta_enetec_por('province', 'Sin provincia', extraido=True)
        venta_enetec_extraidos_por_transportista = _venta_enetec_por('transport_company', 'Sin transportista', extraido=True)
        venta_enetec_pendientes_por_provincia = _venta_enetec_por('province', 'Sin provincia', extraido=False)
        venta_enetec_pendientes_por_transportista = _venta_enetec_por('transport_company', 'Sin transportista', extraido=False)

        # ---- Totales del docx (P3 · P4 · P5) ----
        # Cuatro categorias EXCLUYENTES que cubren el total del sistema, para
        # que las tarjetas sumen visualmente el total (antes 'importados' y
        # 'por_devolver' se solapaban — devolver es un subconjunto de
        # importados, no una categoria aparte — y faltaba 'en puerto', que
        # vivia en otro bloque del tablero).
        # state='to_extract' con extraction_date puesta es una combinacion
        # que _compute_state nunca produce (si hay extraction_date, el
        # estado ya es 'to_return'): esa parte de la formula vieja siempre
        # sumaba cero, se quita por claridad, no cambia el resultado.
        totales = {
            'importados': self.search_count(expression.AND([
                [('extraction_date', '!=', False)], venta_domain,
            ])),
            'en_transito': self.search_count(expression.AND([
                [('state', '=', 'to_arrive')], venta_domain,
            ])),
            'en_puerto': self.search_count(expression.AND([
                [('extraction_date', '=', False), ('arrival_date', '!=', False)], venta_domain,
            ])),
            'por_devolver': self.search_count(expression.AND([
                [('state', '=', 'to_return')], venta_domain,
            ])),
        }

        # ---- Producto × estado (P6 · P9): conteo y volumen (litros) ----
        # La linea de carga no lleva unidad propia: hereda la de su linea de OC,
        # que se pone segun venga el documento del proveedor (hay lineas en
        # litros y lineas en gal (US), ambas de categoria Volumen). Para dar
        # estadistica hay que convertirlo todo a litros: `uom_uom.factor` es
        # relativo a la unidad de referencia de la categoria, que en Volumen es
        # el litro, asi que litros = cantidad / factor (gal US -> /0,264172).
        # Las lineas cuya UdM NO es de categoria Volumen ("Units", herencia de
        # la carga vieja de CUBAMAX/Air Cargo) no se pueden convertir: se
        # siguen sumando tal cual, pero se acumulan aparte para avisarlo bajo
        # la tabla en vez de darlas por litros sin serlo.
        vol_categ = self.env.ref('uom.product_uom_categ_vol').id
        cr.execute(f"""
            SELECT pt.name->>'en_US' AS prod_name,
                   il.state,
                   COUNT(DISTINCT il.id) AS n_containers,
                   COALESCE(SUM(CASE WHEN u.category_id = %s
                                     THEN ill.quantity / NULLIF(u.factor, 0)
                                     ELSE ill.quantity END), 0) AS vol,
                   COALESCE(SUM(CASE WHEN u.category_id = %s
                                     THEN 0 ELSE ill.quantity END), 0) AS vol_sin_uom
            FROM importation_load il
            JOIN importation_load_line ill ON ill.cargo_id = il.id
            JOIN purchase_order_line pol ON pol.id = ill.purchase_order_line_id
            JOIN uom_uom u ON u.id = pol.product_uom
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE TRUE {venta_sql_il}
            GROUP BY 1, 2
        """, (vol_categ, vol_categ))
        conteo = {}   # grupo -> {estado: n}
        volumen = {}  # grupo -> {estado: L}
        volumen_sin_uom = 0.0   # parte del total que no viene en unidad de volumen
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
            volumen_sin_uom += float(r['vol_sin_uom'] or 0)

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
        # Importe y litros salen de las lineas de OC SIN cruzar con las lineas
        # de carga: ese LEFT JOIN repetia cada linea de OC una vez por
        # contenedor y multiplicaba la cantidad (daba 17,0 M de litros de
        # diesel contra los 4,9 M de la tabla de volumen). Los contenedores se
        # cuentan aparte, en su propia consulta.
        # El precio unitario esta expresado en la unidad de SU linea, asi que
        # price_unit * product_qty es el importe correcto en cualquier caso;
        # el precio por litro sale de dividir ese importe entre los litros.
        # TODO revisar filtro VENTA ENETEC: esta consulta (y la que cuenta
        # contenedores debajo) NO se filtran por cliente ni con
        # venta_enetec_only=True. price_unit/product_qty son de la linea de
        # OC, que puede repartirse entre varios contenedores de distintos
        # clientes (no es 1 a 1 con importation_load) -- filtrar solo el
        # conteo de contenedores y dejar importe/qty sin filtrar daria un
        # "precio promedio" internamente inconsistente. Se deja igual para
        # ambos modos hasta decidir si vale la pena prorratear por contenedor.
        cr.execute("""
            SELECT pt.name->>'en_US' AS prod_name,
                   SUM(pol.price_unit * pol.product_qty) AS importe_total,
                   SUM(CASE WHEN u.category_id = %s
                            THEN pol.product_qty / NULLIF(u.factor, 0)
                            ELSE pol.product_qty END) AS qty_total
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            JOIN uom_uom u ON u.id = pol.product_uom
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE po.state != 'cancel'
            GROUP BY 1
        """, (vol_categ,))
        precios_raw = {}
        for r in cr.dictfetchall():
            g = self._fuel_group(r['prod_name'])
            if not g:
                continue
            precios_raw.setdefault(g, {'importe': 0.0, 'qty': 0.0, 'n': 0})
            precios_raw[g]['importe'] += float(r['importe_total'] or 0)
            precios_raw[g]['qty'] += float(r['qty_total'] or 0)

        cr.execute("""
            SELECT pt.name->>'en_US' AS prod_name,
                   COUNT(DISTINCT ill.cargo_id) AS n_containers
            FROM importation_load_line ill
            JOIN purchase_order_line pol ON pol.id = ill.purchase_order_line_id
            JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE po.state != 'cancel'
            GROUP BY 1
        """)
        for r in cr.dictfetchall():
            g = self._fuel_group(r['prod_name'])
            if g in precios_raw:
                precios_raw[g]['n'] += int(r['n_containers'] or 0)

        precios_promedio = []
        for g in prod_orden:
            if g not in precios_raw:
                continue
            d = precios_raw[g]
            precio = (d['importe'] / d['qty']) if d['qty'] else 0.0
            precios_promedio.append({
                'producto': g,
                'precio_prom': round(precio, 4),
                'litros_total': round(d['qty'], 0),
                'contenedores': d['n'],
            })

        # ---- Flete y seguro (totales y promedio por OC) ----
        cr.execute("""
            SELECT LOWER(pt.name->>'en_US') AS tipo,
                   SUM(pol.price_unit * pol.product_qty) AS importe,
                   COUNT(DISTINCT po.id) AS n_po
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE po.state != 'cancel' AND pt.type = 'service'
            GROUP BY 1
        """)
        flete_total = 0.0
        seguro_total = 0.0
        flete_n = 0
        seguro_n = 0
        for r in cr.dictfetchall():
            t = r['tipo'] or ''
            if 'flete' in t:
                flete_total += float(r['importe'] or 0)
                flete_n += int(r['n_po'] or 0)
            elif 'seguro' in t:
                seguro_total += float(r['importe'] or 0)
                seguro_n += int(r['n_po'] or 0)
        flete_seguro = {
            'flete_total': round(flete_total, 2),
            'flete_prom': round(flete_total / flete_n, 2) if flete_n else 0.0,
            'flete_n': flete_n,
            'seguro_total': round(seguro_total, 2),
            'seguro_prom': round(seguro_total / seguro_n, 2) if seguro_n else 0.0,
            'seguro_n': seguro_n,
        }

        # ---- Rankings (P11 · P12 · P13) ----
        # Proveedores × producto × país
        cr.execute(f"""
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
            WHERE TRUE {venta_sql_il_noparam}
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
        cr.execute(f"""
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
            WHERE ip.customer_id IS NOT NULL {venta_sql_il_noparam}
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

        # Destino × producto  (destination_id vive directo en importation_load,
        # no hace falta pasar por importation_process)
        cr.execute(f"""
            SELECT idest.name AS destino,
                   pt.name->>'en_US' AS prod_name,
                   COUNT(DISTINCT il.id) AS n
            FROM importation_load il
            JOIN importation_destination idest ON idest.id = il.destination_id
            JOIN importation_load_line ill ON ill.cargo_id = il.id
            JOIN purchase_order_line pol ON pol.id = ill.purchase_order_line_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE TRUE {venta_sql_il_noparam}
            GROUP BY 1, 2
            ORDER BY 3 DESC
            LIMIT 30
        """)
        ranking_destinos = []
        for r in cr.dictfetchall():
            g = self._fuel_group(r['prod_name'])
            if not g:
                continue
            ranking_destinos.append({
                'label': f"{r['destino']} · {g}",
                'cantidad': int(r['n']),
            })
        ranking_destinos = ranking_destinos[:5]

        # Navieras × producto × país × puerto  (shipping_company es Char)
        cr.execute(f"""
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
              {venta_sql_il_noparam}
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
        # Sin filtro VENTA ENETEC: esto es el embudo de acreditación de leads
        # (clientes/proveedores potenciales que TODAVIA no tienen contenedores),
        # no tiene relación con importation_load ni con un cliente ya acreditado
        # en particular -- se deja igual en ambos modos.
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
        # TODO revisar filtro VENTA ENETEC: pyxel_import_document.customer_id
        # es un campo computado SIN store=True (no existe como columna en la
        # tabla pyxel_import_document), y ademas sale de importation_id.customer_id
        # (el cliente del PROCESO), no del contenedor -- no es exactamente la
        # misma granularidad que importation_load.customer_id que usa el resto
        # del tablero. Se deja sin filtrar en ambos modos hasta decidir el
        # criterio correcto (via JOIN a importation_process, o agregando store
        # al campo).
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
        cr.execute(f"""
            SELECT UPPER(TRIM(il.shipping_company)) AS naviera, COUNT(*) AS n
            FROM importation_load il
            WHERE il.shipping_company IS NOT NULL AND il.shipping_company != ''
              AND il.state = 'to_return'
              {venta_sql_il_noparam}
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
        terminal_activos = self.search_count(expression.AND([
            [('extraction_date', '=', False), ('arrival_date', '!=', False)], venta_domain,
        ]))
        cr.execute(f"""
            SELECT COALESCE(AVG(days_in_tcm), 0) AS prom
            FROM (
                SELECT (il.extraction_date - il.arrival_date) AS days_in_tcm
                FROM importation_load il
                WHERE il.arrival_date IS NOT NULL AND il.extraction_date IS NOT NULL
                  AND il.extraction_date >= (CURRENT_DATE - INTERVAL '12 months')
                  {venta_sql_il_noparam}
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
        # LEFT JOIN a res_partner agregado para poder filtrar por VENTA ENETEC
        # (la query original no lo tenia). Se usa LEFT, no JOIN normal, para
        # que una factura posteada con partner_id nulo/huerfano (si la
        # hubiera) se siga sumando igual que antes en modo normal -- con
        # venta_enetec_only=True esas filas quedan excluidas de todos modos
        # porque rp.name sale NULL y no matchea el ILIKE.
        cr.execute(f"""
            SELECT
              COALESCE(SUM(am.amount_total) FILTER (WHERE am.invoice_date >= %s), 0) AS mes,
              COALESCE(SUM(am.amount_total) FILTER (WHERE am.invoice_date >= %s), 0) AS ytd
            FROM account_move am
            LEFT JOIN res_partner rp ON rp.id = am.partner_id
            WHERE am.state = 'posted' AND am.move_type = 'out_invoice'
              AND am.invoice_date >= %s
              {venta_sql_am}
        """, (first_of_month, first_of_year, first_of_year))
        row = cr.dictfetchone() or {}
        ventas = {
            'facturado_mes': float(row.get('mes') or 0),
            'facturado_ytd': float(row.get('ytd') or 0),
            'refacturado_mes': 0.0,
        }

        # ---- CxC (P29) ----
        cr.execute(f"""
            SELECT rp.name AS cliente,
                   COALESCE(SUM(am.amount_residual), 0) AS saldo,
                   COALESCE(MAX(CURRENT_DATE - am.invoice_date_due), 0) AS dias
            FROM account_move am
            JOIN res_partner rp ON rp.id = am.partner_id
            WHERE am.state = 'posted' AND am.move_type = 'out_invoice'
              AND am.amount_residual > 0
              {venta_sql_am_noparam}
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 10
        """)
        cxc = [{'cliente': r['cliente'], 'saldo': float(r['saldo']), 'dias': int(r['dias'])}
               for r in cr.dictfetchall()]

        # ---- CxP (P28) — sin agrupar por serviciador hasta Fase 2 ----
        # "VENTA ENETEC" es un CLIENTE (nos compra a nosotros); no tiene
        # relación con las cuentas por pagar A PROVEEDORES (in_invoice). En
        # modo venta_enetec_only no tiene sentido mostrar esta sección para un
        # cliente específico, así que se devuelve vacía directamente sin
        # ejecutar la consulta.
        if venta_enetec_only:
            cxp = []
        else:
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
            'huerfanos_por_mes': huerfanos_por_mes,
            'huerfanos_en_lista': huerfanos_en_lista,
            'desglose_desde': DESGLOSE_DESDE,
            'extraidos_por_mes': extraidos_por_mes,
            'pendientes_por_mes': pendientes_por_mes,
            'venta_enetec_extraidos_por_provincia': venta_enetec_extraidos_por_provincia,
            'venta_enetec_extraidos_por_transportista': venta_enetec_extraidos_por_transportista,
            'venta_enetec_pendientes_por_provincia': venta_enetec_pendientes_por_provincia,
            'venta_enetec_pendientes_por_transportista': venta_enetec_pendientes_por_transportista,
            'totales': totales,
            'producto_estado_conteo': producto_estado_conteo,
            'producto_estado_volumen': producto_estado_volumen,
            'volumen_sin_uom': round(volumen_sin_uom, 0),
            'precios_promedio': precios_promedio,
            'flete_seguro': flete_seguro,
            'ranking_proveedores': ranking_proveedores,
            'ranking_clientes': ranking_clientes,
            'ranking_destinos': ranking_destinos,
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
                if duplicate.importation_id:
                    raise ValidationError(
                        f"El contenedor '{record.name}' con BL '{record.bl_number}' ya existe, "
                        f"asociado a la importación '{duplicate.importation_id.name}'."
                    )
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
    # A que OC pertenece realmente este contenedor. El many2many
    # importation.load.purchase_order_ids NO sirve para saberlo: en procesos con
    # varias OC apunta a todas ellas desde cada contenedor. El vinculo real es la
    # linea de compra asignada, y este campo la expone para poder verla y filtrar.
    purchase_order_id = fields.Many2one(related='purchase_order_line_id.order_id', string='OC',
                                        store=True, readonly=True)
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

    def unlink(self):
        # Al borrar líneas vía ORM, el @api.depends('container_fix_ids.quantity') en
        # purchase_order_line NO dispara la recomputa del campo almacenado
        # quantity_allocated. Se fuerza aquí para evitar valores fantasma.
        pol_to_recompute = self.mapped('purchase_order_line_id').exists()
        res = super().unlink()
        if pol_to_recompute:
            pol_to_recompute._compute_quantity_allocated()
        return res

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
