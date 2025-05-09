
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    required_document_ids = fields.Many2many(
        'product.required.document',
        string='Documentos Requeridos para Importación de Producto'
    )


class ProductRequiredDocument(models.Model):
    _name = 'product.required.document'
    _description = 'Documentos Requeridos para Importación de Producto'

    name = fields.Char(string='Nombre del Documento', required=True)
    code = fields.Char(string='Código Interno')
    description = fields.Text(string='Descripción')
