from odoo import models, fields

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    product_onure = fields.Many2many(
        comodel_name='product.product',  # Relación con el modelo de productos
        relation='crm_lead_product_rel',  # Nombre de la tabla relacional
        column1='crm_lead_id',  # Columna para crm.lead
        column2='product_id',  # Columna para product.product
        string="Producto Onure",
        help="Este campo permite seleccionar varios productos relacionados con el lead.",
    )
    
    oferta_firmada = fields.Binary(
    string="Oferta Firmada (PDF)",
    help="Sube la oferta firmada en formato PDF.",
)
    oferta_firmada_filename = fields.Char(string="Nombre del Archivo")

    
