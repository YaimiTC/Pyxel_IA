import uuid
from datetime import timedelta

from odoo import models, fields, api


class CounterpartyRelation(models.Model):
    _name = 'en.counterparty.relation'
    _description = 'Relación de contraparte (cliente ↔ proveedor)'

    name = fields.Char(compute='_compute_name', store=True)
    client_id = fields.Many2one('res.partner', string="Cliente", required=True, ondelete='cascade', index=True)
    supplier_id = fields.Many2one('res.partner', string="Proveedor", required=True, ondelete='cascade', index=True)
    state = fields.Selection([
        ('invited', 'Invitada'),
        ('draft', 'Borrador'),
        ('self_accrediting', 'Auto-acreditando'),
        ('pending', 'En validación'),
        ('active', 'Activa'),
        ('rejected', 'Rechazada'),
    ], default='draft', string="Estado", index=True)
    initiated_by = fields.Selection([('client', 'Cliente'), ('supplier', 'Proveedor')], string="Iniciada por")
    source = fields.Selection([('panel', 'Panel'), ('request', 'Solicitud')], default='request', string="Origen")
    process_id = fields.Many2one('importation.process', string="Operación")
    invitation_ids = fields.One2many('en.accreditation.invitation', 'relation_id', string="Invitaciones")

    _sql_constraints = [
        ('uniq_client_supplier', 'unique(client_id, supplier_id)',
         'Ya existe una relación entre este cliente y proveedor.'),
    ]

    @api.depends('client_id', 'supplier_id')
    def _compute_name(self):
        for r in self:
            r.name = '%s ↔ %s' % (r.client_id.name or '?', r.supplier_id.name or '?')


class AccreditationInvitation(models.Model):
    _name = 'en.accreditation.invitation'
    _description = 'Invitación de acreditación de contraparte'

    def _default_expiry(self):
        return fields.Date.today() + timedelta(days=30)

    name = fields.Char(compute='_compute_name', store=True)
    email = fields.Char(string="Correo", required=True)
    expected_role = fields.Selection([('client', 'Cliente'), ('supplier', 'Proveedor')],
                                     required=True, string="Rol esperado")
    expected_management_type_id = fields.Many2one('res.partner.management.type',
                                                  string="Tipo (si es cliente)")
    inviter_partner_id = fields.Many2one('res.partner', string="Invitador")
    relation_id = fields.Many2one('en.counterparty.relation', string="Relación", ondelete='cascade')
    token = fields.Char(string="Token", index=True, copy=False,
                        default=lambda self: uuid.uuid4().hex)
    state = fields.Selection([
        ('sent', 'Enviada'), ('opened', 'Abierta'), ('accepted', 'Aceptada'),
        ('expired', 'Expirada'), ('cancelled', 'Cancelada'),
    ], default='sent', string="Estado", index=True)
    expiry = fields.Date(string="Caduca", default=_default_expiry)
    accepted_partner_id = fields.Many2one('res.partner', string="Empresa acreditada")
    accepted_lead_id = fields.Many2one('crm.lead', string="Lead generado")

    @api.depends('email', 'expected_role')
    def _compute_name(self):
        for inv in self:
            role = dict(self._fields['expected_role'].selection).get(inv.expected_role, '')
            inv.name = '%s (%s)' % (inv.email or '?', role)
