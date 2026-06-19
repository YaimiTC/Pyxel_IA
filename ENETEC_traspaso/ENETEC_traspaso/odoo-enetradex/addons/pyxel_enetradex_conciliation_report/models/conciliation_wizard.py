# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class PyxelEnetradexConciliationWizard(models.TransientModel):
    _name = "pyxel.enetradex.conciliation.wizard"
    _description = "Conciliación ENETEC (CE-PCT) - Excel"

    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)

    partner_id = fields.Many2one("res.partner", string="Cliente", domain=[
           ("contact_type_id.type_of_contact", "=", "Client"),
        ],)
    supplier_id = fields.Many2one('res.partner', string='Proveedor', domain=[
            ("contact_type_id.type_of_contact", "=", "Supplier"),
        ],)

    contract_to_third = fields.Selection(
        [("all", "Todos"), ("yes", "Sí"), ("no", "No")],
        default="all",
        required=True,
        string="Contrato a 3ro",
    )

    provider_import_name = fields.Char(string="Proveedor servicio importación", default="ENETEC")
    platform_name = fields.Char(string="Servicio plataforma", help="Se llena automático si eliges partner.",
                                default="PARQUE CIENTÍFICO TECNOLÓGICO DE LA HABANA")
    pyxel_name = fields.Char(string="Proveedor Pyxel", default="PYXEL SOLUTIONS SRL")

    def _build_payload(self):
        self.ensure_one()
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "partner_id": self.partner_id.id or False,
            "supplier_id": self.supplier_id.id or False,
            "platform_name": self.platform_name or (self.partner_id.name if self.partner_id else ""),
            "contract_to_third": self.contract_to_third,
            "provider_import_name": self.provider_import_name,
            "pyxel_name": self.pyxel_name,
        }

    def action_generate_excel(self):
        self.ensure_one()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise UserError(_("La fecha inicial no puede ser mayor que la fecha final."))
        payload = self._build_payload()
        lines = self.env["pyxel.enetradex.conciliation.service"].get_lines(payload)
        if not lines:
            raise UserError(_("No existen facturas en el período definido."))
        return self.env["pyxel.enetradex.conciliation.xls_exporter"].export_excel(lines, payload)

    @api.constrains("start_date", "end_date")
    def _check_date_range(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(_("La fecha inicial no puede ser mayor que la fecha final."))

    @api.constrains("start_date", "end_date")
    def _check_date_range(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(_("La fecha inicial no puede ser mayor que la fecha final."))
