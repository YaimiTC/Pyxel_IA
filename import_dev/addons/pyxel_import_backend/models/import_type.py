from odoo import models, fields


class ImportType(models.Model):
    _name = 'import.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Import Type'

    name = fields.Char(string='Name')

    # Documentation block
    has_bl = fields.Boolean(string='BL')
    has_awb = fields.Boolean(string='AWB')
    has_packing_list = fields.Boolean(string='Packing List')
    has_quality_certificate = fields.Boolean(string='Quality Certificate')
    has_export_certificate = fields.Boolean(string='Export Certificate')
    has_origin_certificate = fields.Boolean(string='Origin Certificate')
    use_port = fields.Boolean(string='Port?')
    use_airport = fields.Boolean(string='Airport?')

    # Load block
    show_cargo_type = fields.Boolean(string='Show Cargo Type')
    show_volume = fields.Boolean(string='Show Volume')
    show_bulk = fields.Boolean(string='Show Bulk')

    show_opening_date = fields.Boolean(string='Show Opening Date')
    show_arrival_date = fields.Boolean(string='Show Arrival Date')
    show_release_date = fields.Boolean(string='Show Release Date')
    show_extraction_date = fields.Boolean(string='Show Extraction Date')
    show_return_date = fields.Boolean(string='Show Return Date')

    show_shipping_company = fields.Boolean(string='Show Shipping Company')
    show_airline = fields.Boolean(string='Show Airline')
    show_transit_agency = fields.Boolean(string='Show Transit Agency')

    no_container = fields.Boolean(string='No Container', default=True,
                                  help='Indica si este tipo de importación no requiere contenedor (ej: En plaza)')
