# models/import_container_billing_log.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ImportContainerBillingLog(models.Model):
    _name = 'import.container.billing.log'
    _description = 'Histórico de importación de facturas por Excel (contenedores)'
    _order = 'period_start desc, id desc'

    name = fields.Char(string="Referencia", compute='_compute_name', store=True)
    product_id = fields.Many2one('product.product', string="Servicio", required=True)
    period_start = fields.Date(string="Periodo desde", required=True)
    period_end = fields.Date(string="Periodo hasta", required=True)
    company_id = fields.Many2one('res.company', string="Compañía", required=True, default=lambda self: self.env.company)
    journal_id = fields.Many2one('account.journal', string="Diario")
    filename = fields.Char(string="Nombre de archivo")
    file_hash = fields.Char(string="Hash del archivo")
    imported_on = fields.Datetime(string="Fecha de importación", default=fields.Datetime.now)
    imported_by = fields.Many2one('res.users', string="Usuario", default=lambda self: self.env.user)
    invoices_count = fields.Integer(string="Facturas generadas", default=0)
    notes = fields.Text(string="Notas")

    _sql_constraints = [
        ('uniq_service_period_company',
         'unique(product_id, period_start, period_end, company_id)',
         'Este servicio ya fue importado para el mismo período y compañía.')
    ]

    @api.depends('product_id', 'period_start', 'period_end')
    def _compute_name(self):
        for rec in self:
            if rec.product_id and rec.period_start and rec.period_end:
                rec.name = "%s | %s - %s" % (
                    rec.product_id.display_name,
                    rec.period_start, rec.period_end
                )
            else:
                rec.name = _("Importación por Excel")
