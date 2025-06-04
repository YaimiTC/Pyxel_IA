from odoo import api, fields, models, _


class Product(models.Model):
    _inherit = "product.template"

    min_qty_sale = fields.Float("Cantidad mín.")
    approved_to_import = fields.Boolean(
        "Aprobado", help="El producto está listo para usar en importaciones y en la venta de la tienda mayorista"
    )
    product_origin = fields.Char("Origen del producto")

    de_importacion = fields.Boolean(string="De Importación", default=False)

    type_of_product = fields.Selection(
        selection=[('in-bond', 'In-bond'), ('nacionalizado', 'Nacionalizado'), ('consignado', 'Consignado'),
                   ('cfi', 'CFI')], string='Tipo de producto')

    product_type = fields.Selection(
        selection=[
            ('alimento', 'Nomenclador'),
            ('electronico', 'Homologados por la ONURE'),
            ('otros', 'Otros')  # Nueva opciónn 'otros'
        ],
        string='Tipo de mercancía',
        default='otros'  # Establece 'otros' como valor predeterminado
    )
