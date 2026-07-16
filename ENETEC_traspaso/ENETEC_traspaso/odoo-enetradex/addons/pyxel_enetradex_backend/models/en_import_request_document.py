# -*- coding: utf-8 -*-
from odoo import models, fields


class EnImportRequestDocument(models.Model):
    """Documento adjunto en una solicitud de cliente (oferta, factura, etc.)"""
    _name = 'en.import.request.document'
    _description = "Documento de solicitud de importación"
    _order = 'sequence, id'

    client_block_id = fields.Many2one(
        'en.import.request.client', string="Bloque cliente",
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    document_type = fields.Selection([
        ('oferta_firmada', 'Oferta firmada'),
        ('factura_comercial', 'Factura comercial'),
        ('permisos', 'Permisos por entidades regulatorias'),
        ('lista_empaque', 'Lista de empaque'),
        ('otro', 'Otro documento'),
    ], string="Tipo de documento", required=True)
    name = fields.Char(string="Nombre del documento")
    attachment = fields.Binary(string="Archivo", required=True)
    filename = fields.Char()

    def name_get(self):
        res = []
        for rec in self:
            label = f"{dict(rec._fields['document_type'].selection).get(rec.document_type, 'Doc')} — {rec.name or rec.filename or 'Sin nombre'}"
            res.append((rec.id, label))
        return res
