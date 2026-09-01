from odoo import models, fields


class ImportationPackagingType(models.Model):
    _name = 'importation.packaging.type'
    _description = 'Tipo de envase del contenedor'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    allowed_product_ids = fields.Many2many(
        'product.product', string='Productos permitidos',
        help="Con qué productos se puede usar este envase. Vacío = sin "
             "restricción (se permite cualquier producto).")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Este tipo de envase ya existe.'),
    ]
