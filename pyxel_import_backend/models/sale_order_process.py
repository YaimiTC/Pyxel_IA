from odoo import models, fields, api, _


class SaleOrderProcess(models.Model):
    _name = "sale.order.process"
    _description = "Proceso de órdenes de venta"
    _order = "name desc"

    name = fields.Char(string="Referencia", required=True, copy=False, readonly=True, default="Nuevo")
    state = fields.Selection([
        ('open', 'Abierto'),
        ('closed', 'Cerrado'),
    ], string="Estado", default='open', tracking=True)

    sale_order_ids = fields.One2many('sale.order', 'process_id', string="Órdenes de venta relacionadas")

    importation_id = fields.Many2one('importation.process', string="Importación Cerrada", readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nuevo') == 'Nuevo':
            user = self.env.user
            province_code = user.partner_id.state_id.code or "XX"
            year = fields.Date.today().year
            sequence = self.env['ir.sequence'].next_by_code('sale.order.process.seq') or '0000'
            vals['name'] = f"{sequence}-{year}-{province_code}"
        return super().create(vals)
