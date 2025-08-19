import binascii
import logging
import base64

from datetime import datetime

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
        is_internal_user = user.has_group('base.group_user')

        first_stage = request.env['importation.stage'].sudo().search([], order='sequence asc', limit=1)
        _logger.info(f"La primera etapa de CRM es: {first_stage.name} (ID: {first_stage.id})")

        # Inicializa contadores
        new_quotations_count = 0  # representa a los purchase.order
        new_orders_count = 0  # representa a los sale.order
        new_invoices_count = 0  # representa a los invoices
        new_importaciones_count = 0  # representa a las importaciones

        if is_internal_user:
            _logger.info("Usuario interno: se cuentan todos los documentos.")
            new_quotations_count = request.env['purchase.order'].sudo().search_count([('state', '=', 'draft')])
            new_orders_count = request.env['sale.order'].sudo().search_count([('state', '=', 'draft')])
            new_invoices_count = request.env['account.move'].sudo().search_count([
                ('state', '=', 'draft'),
                ('move_type', '=', 'out_invoice')
            ])
            new_importaciones_count = request.env['importation.process'].sudo().search_count([
                ('stage_id', '=', first_stage.id)
            ])

        elif contact_type.type_of_contact == 'Client':
            _logger.info("Usuario cliente: se cuentan solo ventas e importaciones como cliente.")
            new_orders_count = request.env['sale.order'].sudo().search_count([
                ('state', '=', 'draft'),
                ('partner_id', '=', business_partner_id)
            ])

            new_invoices_count = request.env['account.move'].sudo().search_count([
                ('state', '=', 'draft'),
                ('move_type', '=', 'out_invoice'),
                ('partner_id', '=', business_partner_id)
            ])
            new_importaciones_count = request.env['importation.process'].sudo().search_count([
                ('stage_id', '=', first_stage.id),
                ('customer_id', '=', business_partner_id)
            ])

        elif contact_type.type_of_contact == 'Supplier':
            _logger.info("Usuario proveedor: se cuentan solo compras e importaciones como proveedor.")
            new_quotations_count = request.env['purchase.order'].sudo().search_count([
                ('state', '=', 'draft'),
                ('partner_id', '=', business_partner_id)
            ])
            new_invoices_count = request.env['account.move'].sudo().search_count([
                ('state', '=', 'draft'),
                ('move_type', '=', 'out_invoice'),
                ('partner_id', '=', business_partner_id)
            ])
            new_importaciones_count = request.env['importation.process'].sudo().search_count([
                ('stage_id', '=', first_stage.id),
                ('provider_id', '=', business_partner_id)
            ])
            # Las órdenes de venta quedan en cero

        _logger.info(
            f"Contadores calculados: Quotations: {new_quotations_count}, Orders: {new_orders_count}, "
            f"Invoices: {new_invoices_count}, Imports: {new_importaciones_count}"
        )

        # === Estado del contrato ===
        contract_status = False
        days_in_process = 'False'

        if contact_type.type_of_contact in ['Client', 'Supplier']:
            lead = request.env['crm.lead'].sudo().search(
                [('partner_id', '=', business_partner_id)],
                order='create_date desc',
                limit=1
            )

            if lead:
                contract_status = lead.stage_id.name
                if contact_type.type_of_contact == 'Client':
                    is_accredited = request.env["res.partner.contract.import"].sudo().search([
                        ("partner_id", "=", business_partner_id),
                        ("active_contract", "=", True)
                    ], limit=1)
                elif contact_type.type_of_contact == 'Supplier':
                    is_accredited = lead.stage_id.id == request.env.ref('crm.stage_lead3').sudo().id

                if not is_accredited:
                    days_in_process = (datetime.now() - lead.create_date).days

        _logger.info(f"Estado del contrato: {contract_status}, Días en proceso: {days_in_process}")

        # Actualiza valores del portal
        values.update({
            'new_quotations_count': new_quotations_count,
            'new_orders_count': new_orders_count,
            'new_invoices_count': new_invoices_count,
            'new_importaciones_count': new_importaciones_count,
            'contract_status': contract_status,
            'days_in_process': days_in_process,
        })

        return values
