from odoo import models, fields, api

class ImageMixin(models.AbstractModel):
    _inherit='image.mixin'
    
    image_48 = fields.Image(string="Image 48", related='image_1920', max_width=48, max_height=48, store=True)
