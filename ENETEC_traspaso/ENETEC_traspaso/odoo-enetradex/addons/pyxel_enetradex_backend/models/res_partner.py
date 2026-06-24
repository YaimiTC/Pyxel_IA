from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ENETRADEX: visibilidad de proveedor en el catálogo público (lo marca ENETRADEX).
    en_is_public_provider = fields.Boolean(
        string="Proveedor público",
        help="Visible en el catálogo público para que cualquier cliente lo elija. Lo marca ENETRADEX.")
    # ENETRADEX: el cliente acepta recibir ofertas de proveedores (difusión).
    en_accepts_offers = fields.Boolean(
        string="Acepta recibir ofertas",
        help="El cliente acepta que los proveedores le difundan ofertas.")

    # ENETRADEX: acreditación de proveedor extranjero.
    en_requiere_mincex = fields.Boolean(
        string="¿Requiere código MINCEX?",
        help="El proveedor declara que requiere/posee código MINCEX.")
    en_socio_cubano = fields.Boolean(
        string="¿Tiene socio de nacionalidad cubana?",
        help="El proveedor extranjero tiene un socio de nacionalidad cubana.")

    en_cuban_partner_ids = fields.One2many('en.cuban.partner', 'partner_id', string="Socios cubanos")

    en_supply_offer_ids = fields.One2many('en.supply.offer', 'supplier_id', string="Ofertas de suministro")
    en_relation_client_ids = fields.One2many('en.counterparty.relation', 'client_id', string="Mis proveedores")
    en_relation_supplier_ids = fields.One2many('en.counterparty.relation', 'supplier_id', string="Mis clientes")
