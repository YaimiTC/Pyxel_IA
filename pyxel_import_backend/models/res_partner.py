from odoo import api, fields, models, _
from datetime import date
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    import_mgmt_type = fields.Selection([
        ('pyme', 'SME'),
        ('extranjero', 'Foreign'),
        ('otra', 'Other'),
    ], string="Non-State Management Type")

    legal_document = fields.Binary(string="Legal Document")
    legal_document_filename = fields.Char(string="Document Name")

    mincex_code = fields.Char(string="MINCEX Code")
    activity_number = fields.Char(string="Activity Number")
    hiring_number = fields.Char(string="Hiring Number")

    legal_activity_ids = fields.One2many('res.partner.legal.activity', 'partner_id', string="Activities")
    contract_import_ids = fields.One2many('res.partner.contract.import', 'partner_id', string="Contracts")


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
