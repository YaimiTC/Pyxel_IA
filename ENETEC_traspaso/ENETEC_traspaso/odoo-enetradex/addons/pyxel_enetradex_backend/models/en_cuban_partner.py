# -*- coding: utf-8 -*-
from odoo import models, fields


class EnCubanPartner(models.Model):
    _name = 'en.cuban.partner'
    _description = 'Socio cubano residente en el exterior (acreditación de proveedor)'

    partner_id = fields.Many2one(
        'res.partner', string="Empresa proveedora", ondelete='cascade', index=True)
    lead_id = fields.Many2one('crm.lead', string="Lead de acreditación", index=True)

    # DATOS A APORTAR PARA LOS CUBANOS RESIDENTES EN EL EXTERIOR
    name = fields.Char(string="Nombre y apellidos", required=True)
    passport_no = fields.Char(string="No. Pasaporte")
    foreign_passport_no = fields.Char(string="No. Pasaporte extranjero")
    birth_date = fields.Date(string="Fecha de nacimiento")
    birth_place = fields.Char(string="Lugar de nacimiento")
    father_info = fields.Char(string="Nombre, apellidos y fecha de nacimiento del padre")
    mother_info = fields.Char(string="Nombre, apellidos y fecha de nacimiento de la madre")
    current_address = fields.Char(string="Dirección de residencia actual")
    mobile = fields.Char(string="No. teléfono móvil")
    landline = fields.Char(string="No. teléfono fijo")
    email = fields.Char(string="Correo electrónico")
    exit_date = fields.Date(string="Fecha de salida de Cuba")
    last_address_cuba = fields.Char(string="Última dirección en Cuba")
    graduated_of = fields.Char(string="Graduado de")
    graduation_date = fields.Date(string="Fecha de graduado")
    work_in_cuba = fields.Char(string="Labor desempeñada en Cuba")
