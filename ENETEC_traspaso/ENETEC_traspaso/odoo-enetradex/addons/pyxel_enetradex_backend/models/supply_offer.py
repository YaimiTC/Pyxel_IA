from odoo import models, fields, api


class SupplyOffer(models.Model):
    _name = 'en.supply.offer'
    _description = 'Oferta de suministro (cotización del proveedor)'

    name = fields.Char(string="Referencia", default='Nueva oferta')
    supplier_id = fields.Many2one('res.partner', string="Proveedor", required=True,
                                  ondelete='cascade', index=True)
    state = fields.Selection([('draft', 'Borrador'), ('published', 'Publicada'), ('expired', 'Vencida')],
                             default='draft', string="Estado", index=True)
    validity = fields.Selection([('1m', '1 mes'), ('3m', '3 meses'), ('6m', '6 meses'),
                                 ('1y', '1 año'), ('custom', 'Personalizada')],
                                default='3m', string="Vigencia")
    valid_until = fields.Date(string="Válida hasta")
    incoterm_id = fields.Many2one('account.incoterms', string="Incoterm")
    port = fields.Char(string="Puerto de origen")
    payment_term = fields.Char(string="Forma de pago")
    currency_id = fields.Many2one('res.currency', string="Moneda",
                                  default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))
    line_ids = fields.One2many('en.supply.offer.line', 'offer_id', string="Líneas")
    flete = fields.Monetary(string="Flete", currency_field='currency_id')
    seguro = fields.Monetary(string="Seguro", currency_field='currency_id')
    subtotal = fields.Monetary(compute='_compute_totals', store=True, currency_field='currency_id', string="Subtotal")
    total = fields.Monetary(compute='_compute_totals', store=True, currency_field='currency_id', string="Total")
    note = fields.Text(string="Observaciones")

    @api.depends('line_ids.amount', 'flete', 'seguro')
    def _compute_totals(self):
        for o in self:
            o.subtotal = sum(o.line_ids.mapped('amount'))
            o.total = o.subtotal + (o.flete or 0.0) + (o.seguro or 0.0)


class SupplyOfferLine(models.Model):
    _name = 'en.supply.offer.line'
    _description = 'Línea de oferta de suministro'

    offer_id = fields.Many2one('en.supply.offer', string="Oferta", ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string="Producto", required=True)
    packaging = fields.Selection([('isotanque', 'Isotanque'), ('isomodulo', 'Isomódulo')], string="Envase")
    qty = fields.Float(string="Cantidad")
    unit_price = fields.Monetary(string="Precio unit.", currency_field='currency_id')
    amount = fields.Monetary(compute='_compute_amount', store=True, currency_field='currency_id', string="Importe")
    currency_id = fields.Many2one(related='offer_id.currency_id', string="Moneda")

    @api.depends('qty', 'unit_price')
    def _compute_amount(self):
        for l in self:
            l.amount = (l.qty or 0.0) * (l.unit_price or 0.0)


class Tender(models.Model):
    _name = 'en.tender'
    _description = 'Pliego de concurrencia (ENETEC cotiza)'

    name = fields.Char(string="Referencia", default='Pliego de concurrencia')
    client_id = fields.Many2one('res.partner', string="Cliente", required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string="Producto")
    qty = fields.Float(string="Cantidad")
    process_id = fields.Many2one('importation.process', string="Operación")
    state = fields.Selection([('open', 'Abierto'), ('collecting', 'Recibiendo ofertas'),
                              ('awarded', 'Adjudicado'), ('closed', 'Cerrado')],
                             default='open', string="Estado", index=True)
    line_ids = fields.One2many('en.tender.line', 'tender_id', string="Ofertas recibidas")
    awarded_line_id = fields.Many2one('en.tender.line', string="Oferta adjudicada")
    note = fields.Text(string="Observaciones")


class TenderLine(models.Model):
    _name = 'en.tender.line'
    _description = 'Oferta recibida en un pliego'

    tender_id = fields.Many2one('en.tender', string="Pliego", ondelete='cascade')
    supplier_id = fields.Many2one('res.partner', string="Proveedor")
    offer_id = fields.Many2one('en.supply.offer', string="Oferta")
    price = fields.Float(string="Precio")
    note = fields.Char(string="Nota")
