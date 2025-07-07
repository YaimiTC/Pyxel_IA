import binascii
import logging
import base64

from odoo import fields
from odoo import http, _
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.exceptions import AccessError, UserError, MissingError
from odoo.http import request

_logger = logging.getLogger(__name__)


class Portal(CustomerPortal):
    def _prepare_portal_layout_values(self):
        values = super(Portal, self)._prepare_portal_layout_values()
        user = request.env.user
        business_partner_id = user.partner_id.parent_id.id if user.partner_id.parent_id else user.partner_id.id
        contact_type = user.partner_id.parent_id.contact_type_id if user.partner_id.parent_id else user.partner_id.contact_type_id
        first_stage = request.env['importation.stage'].sudo().search([], order='sequence asc', limit=1)
        _logger.info(f"La primera etapa de CRM es: {first_stage.name} (ID: {first_stage.id})")

        new_quotations_count = 0
        new_orders_count = 0
        new_invoices_count = 0
        new_importaciones_count = 0

        quotations_domain = [('state', '=', 'sent')]
        orders_domain = [('state', '=', 'sale')]
        invoices_domain = [('state', '=', 'posted'), ('move_type', '=', 'out_invoice')]
        imports_domain = [('stage_id', '=', first_stage.id)]

        if contact_type.type_of_contact == 'Client':
            quotations_domain.append(('partner_id', '=', business_partner_id))
            orders_domain.append(('partner_id', '=', business_partner_id))
            invoices_domain.append(('partner_id', '=', business_partner_id))
            imports_domain.append(('customer_id', '=', business_partner_id))
        if contact_type.type_of_contact == 'Supplier':
            quotations_domain.append(('supplier_id', '=', business_partner_id))
            orders_domain.append(('supplier_id', '=', business_partner_id))
            invoices_domain.append(('invoice_line_ids.product_id.seller_ids.partner_id', '=', business_partner_id))
            imports_domain.append(('provider_id', '=', business_partner_id))

        # Calcula los contadores solo si el usuario es valido
        if contact_type.type_of_contact or user.has_group('base.group_user'):
            _logger.info(f"El usuario es válido y debemos calcular cantidades")
            new_quotations_count = request.env['sale.order'].sudo().search_count(quotations_domain)
            new_orders_count = request.env['sale.order'].sudo().search_count(orders_domain)
            new_invoices_count = request.env['account.move'].sudo().search_count(invoices_domain)
            new_importaciones_count = request.env['importation.process'].sudo().search_count(imports_domain)
            _logger.info(f"Aplicando el dominio {imports_domain} el resultado es {new_importaciones_count}")
        _logger.info(
            "Quotations: " + str(new_quotations_count) + ", Orders: " + str(new_orders_count) + ", Invoices: " + str(
                new_invoices_count) + ", Imports: " + str(new_importaciones_count))

        # Estado del contrato:
        contract_status = False
        if contact_type.type_of_contact == 'Client' or contact_type.type_of_contact == 'Supplier':
            lead = request.env['crm.lead'].sudo().search([('partner_id', '=', business_partner_id)],
                                                                    order='create_date desc', limit=1)

            if bool(lead):
                contract_status = lead.stage_id.name
        _logger.info(f"El estado del contrato es: {contract_status}")
        # Añade los contadores a los valores
        values.update({
            'new_quotations_count': new_quotations_count,
            'new_orders_count': new_orders_count,
            'new_invoices_count': new_invoices_count,
            'new_importaciones_count': new_importaciones_count,
            'contract_status': contract_status
        })

        return values
