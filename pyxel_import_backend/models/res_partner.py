from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    import_mgmt_type = fields.Selection([
        ('pyme', 'SME'),
        ('extranjero', 'Foreign'),
        ('otra', 'Other'),
    ], string="Non-State Management Type")

    legal_document = fields.Binary(string="Legal Document")
    legal_document_filename = fields.Char(string="Document Name")

    count_imports = fields.Integer(string="Count Imports")
    # count_imports = fields.Integer(string="Count Imports", compute="_compute_count_imports")
    license_holder = fields.Char(string="Mincex")
    activity_number = fields.Char(string="Activity Number")
    hiring_number = fields.Char(string="Hiring Number")

    legal_activity_ids = fields.One2many('res.partner.legal.activity', 'partner_id', string="Activities")
    contract_import_ids = fields.One2many('res.partner.contract.import', 'partner_id', string="Contracts")

    @api.constrains('vat')
    def _check_vat_length(self):
        for record in self:
            if record.vat:
                if not record.vat.isdigit():
                    raise ValidationError(_("The NIT must contain only digits."))
                if len(record.vat) != 11:  # Set your desired limit
                    raise ValidationError(_("The NIT must be exactly 11 digits long."))

    contact_type_id = fields.Many2one(
        'res.partner.contact.type',
        string='Type of contact',
        required=True,
        help="Custom contact classification"
    )

    # @api.depends('contact_type_id')
    # def _compute_count_imports(self):
    #     for record in self:
    #         record['count_imports'] = 0
    #         if record.contact_type_id == "Customer":
    #             count = self.env['x_import'].search_count([("purchase_ids.client", "=", record.id)])
    #             record['count_imports'] = count
    #         elif record.contact_type_id == "Supplier":
    #             count = self.env['x_import'].search_count([("supplier", "=", record.id)])
    #             record['count_imports'] = count


class ResPartnerLegalActivity(models.Model):
    _name = 'res.partner.legal.activity'
    _description = 'Company Activity'

    partner_id = fields.Many2one('res.partner', string="Contact", ondelete='cascade')
    name = fields.Char(string="Activity Name", required=True)
    license_number = fields.Char(string="License Number")


class ResPartnerContractImport(models.Model):
    _name = 'res.partner.contract.import'
    _description = 'Contract Associated with Importation'

    partner_id = fields.Many2one('res.partner', string="Contact", ondelete='cascade')
    contract_number = fields.Char(string="Contract Number", required=True)
    activity_number = fields.Char(string="Activity Number")
    hiring_number = fields.Char(string="Hiring Number")

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    active_contract = fields.Boolean(string="Active", compute="_compute_active_contract", store=True)

    parent_contract_id = fields.Many2one('res.partner.contract.import', string="Parent Contract")
    contract_file = fields.Binary(string="Contract File")
    contract_file_filename = fields.Char(string="File Name")

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.end_date < record.start_date:
                raise ValidationError(_("The end date cannot be earlier than the start date."))

    @api.depends('start_date', 'end_date')
    def _compute_active_contract(self):
        today = date.today()
        for record in self:
            record.active_contract = bool(
                record.start_date and record.end_date and record.start_date <= today <= record.end_date)


class ResPartnerContactType(models.Model):
    _name = 'res.partner.contact.type'
    _description = 'Type of contact'

    name = fields.Char(string='Type of name', required=True)
    code = fields.Char(string='Code')  # opcional
    description = fields.Text(string='Description')  # opcional

    type_of_contact = fields.Selection(
        [
            ("Supplier", "Supplier"),
            ("Client", "Client"),
        ],
        string="Type Of Contact"
    )
