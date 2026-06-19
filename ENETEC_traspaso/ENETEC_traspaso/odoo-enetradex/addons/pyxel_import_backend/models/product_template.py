from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    required_document_ids = fields.Many2many(
        'product.required.document',
        string='Required Documents for Product Importation'
    )


class ProductRequiredDocument(models.Model):
    _name = 'product.required.document'
    _description = 'Required Documents for Product Importation'

    name = fields.Char(string='Document Name', required=True)
    code = fields.Char(string='Internal Code')
    description = fields.Text(string='Description')