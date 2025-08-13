from odoo import models, fields, api, _


class IncotermImportType(models.Model):
    _name = 'incoterm.import.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Incoterm - Import Type Relation'

    incoterm_id = fields.Many2one('account.incoterms', string='Incoterm', required=True, ondelete='cascade')
    import_type_id = fields.Many2one('import.type', string='Import Type', required=True, ondelete='cascade')
    active = fields.Boolean(string='Active', default=True)

    # Documentation block
    has_bl = fields.Boolean(string='BL')
    has_awb = fields.Boolean(string='AWB')
    has_packing_list = fields.Boolean(string='Packing List')
    has_commercial_invoice = fields.Boolean(string='Commercial Invoice')
    has_signed_offer = fields.Boolean(string='Signed Offer')
    has_quality_certificate = fields.Boolean(string='Quality Certificate')
    has_export_certificate = fields.Boolean(string='Export Certificate')
    has_origin_certificate = fields.Boolean(string='Origin Certificate')
    has_supplier_payment_certificate = fields.Boolean(string='Supplier Payment Certificate')
    port_or_airport = fields.Boolean(string='Port/Airport?')

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

    _sql_constraints = [
        ('unique_combination', 'unique(incoterm_id, import_type_id)', 'This combination already exists.')
    ]
