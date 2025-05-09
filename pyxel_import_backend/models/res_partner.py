
from odoo import api, fields, models, _
from datetime import date
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    import_mgmt_type = fields.Selection([
        ('pyme', 'PYME'),
        ('extranjero', 'Extranjero'),
        ('otra', 'Otra'),
    ], string="Tipo de gestión no estatal")

    legal_document = fields.Binary(string="Documento Legal")
    legal_document_filename = fields.Char(string="Nombre del documento")

    mincex_code = fields.Char(string="Código MINCEX")
    activity_number = fields.Char(string="Número de Actividad")
    hiring_number = fields.Char(string="Número de Contratación")

    legal_activity_ids = fields.One2many('res.partner.legal.activity', 'partner_id', string="Actividades")
    contract_import_ids = fields.One2many('res.partner.contract.import', 'partner_id', string="Contratos")


class ResPartnerLegalActivity(models.Model):
    _name = 'res.partner.legal.activity'
    _description = 'Actividad de la empresa'

    partner_id = fields.Many2one('res.partner', string="Contacto", ondelete='cascade')
    name = fields.Char(string="Nombre de la Actividad", required=True)
    license_number = fields.Char(string="No. Licencia")


class ResPartnerContractImport(models.Model):
    _name = 'res.partner.contract.import'
    _description = 'Contrato asociado por la importación'

    partner_id = fields.Many2one('res.partner', string="Contacto", ondelete='cascade')
    contract_number = fields.Char(string="No. Contrato", required=True)
    activity_number = fields.Char(string="No. de Actividad")
    hiring_number = fields.Char(string="No. de Contratación")

    start_date = fields.Date(string="Fecha de Inicio")
    end_date = fields.Date(string="Fecha de Fin")
    active_contract = fields.Boolean(string="Activo", compute="_compute_active_contract", store=True)

    parent_contract_id = fields.Many2one('res.partner.contract.import', string="Contrato Padre")
    contract_file = fields.Binary(string="Archivo del Contrato")
    contract_file_filename = fields.Char(string="Nombre del Archivo")

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.end_date < record.start_date:
                raise ValidationError(_("La fecha de fin no puede ser anterior a la fecha de inicio."))

    @api.depends('start_date', 'end_date')
    def _compute_active_contract(self):
        today = date.today()
        for record in self:
            record.active_contract = bool(
                record.start_date and record.end_date and record.start_date <= today <= record.end_date)


