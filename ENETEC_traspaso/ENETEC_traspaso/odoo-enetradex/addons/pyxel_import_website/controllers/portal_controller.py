import binascii
import logging
import base64

from datetime import datetime, timedelta

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

    # ===================== DASHBOARD de Mi Cuenta =====================
    @http.route(['/my', '/my/home'], type='http', auth='user', website=True)
    def home(self, **kw):
        """Mi Cuenta como panel de control (dashboard) del cliente/proveedor."""
        values = self._prepare_portal_layout_values()
        try:
            values.update(self._en_dashboard_values())
            return request.render('pyxel_import_website.portal_my_dashboard', values)
        except Exception as e:  # pragma: no cover - si algo falla, no romper Mi Cuenta
            _logger.exception("Dashboard Mi Cuenta falló, usando home estándar: %s", e)
            return super().home(**kw)

    def _en_dashboard_values(self):
        env = request.env
        company = env.user.partner_id.commercial_partner_id or env.user.partner_id
        ctype = company.contact_type_id.type_of_contact
        role = 'supplier' if ctype == 'Supplier' else 'client'

        Process = env['importation.process'].sudo()
        Stage = env['importation.stage'].sudo()
        Move = env['account.move'].sudo()
        Event = env['en.tracking.event'].sudo()
        gate = env.ref('pyxel_enetradex_backend.en_stage_pending_accreditation',
                       raise_if_not_found=False)

        op_domain = [('provider_id', '=', company.id)] if role == 'supplier' \
            else [('customer_id', '=', company.id)]
        operations = Process.search(op_domain, order='id desc')

        op_stages = Stage.search([('sequence', '>', 0)], order='sequence')
        total_steps = len(op_stages) or 1
        today = fields.Date.today()

        ops = []
        next_arrival = False
        in_gate = 0
        for op in operations:
            seq = op.stage_id.sequence
            idx = len(op_stages.filtered(lambda s: s.sequence <= seq)) if seq > 0 else 0
            is_gate = bool(gate and op.stage_id.id == gate.id)
            if is_gate:
                in_gate += 1
            arr = False
            for c in op.load_tracking_ids:
                if c.arrival_date and (not arr or c.arrival_date < arr):
                    arr = c.arrival_date
            if arr and (not next_arrival or arr < next_arrival):
                next_arrival = arr
            ops.append({
                'id': op.id, 'name': op.name,
                'counterparty': (op.provider_id.name if role == 'client' else op.customer_id.name) or '—',
                'origin': op.country_origin_id.name or '',
                'stage': op.stage_id.name, 'is_gate': is_gate,
                'step': idx, 'total': total_steps,
                'pct': int(round(100.0 * idx / total_steps)),
                'arrival': arr,
            })

        # Facturas (solo clientes tienen facturas de venta).
        invoices = Move.search([
            ('partner_id', '=', company.id), ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted')], order='invoice_date_due asc, id desc', limit=6)
        inv_pending = invoices.filtered(lambda m: m.payment_state in ('not_paid', 'partial'))
        inv_pending_amount = sum(inv_pending.mapped('amount_residual'))
        currency = invoices[:1].currency_id or env.company.currency_id
        inv_list = [{
            'id': m.id, 'name': m.name, 'due': m.invoice_date_due,
            'amount': m.amount_total, 'residual': m.amount_residual,
            'state': m.payment_state,
            'overdue': bool(m.invoice_date_due and m.invoice_date_due < today
                            and m.payment_state in ('not_paid', 'partial')),
        } for m in invoices]

        # Actividad reciente (acreditación de la empresa + sus operaciones).
        activity = Event.search(
            ['|', ('partner_id', '=', company.id), ('operation_id', 'in', operations.ids)],
            order='date desc', limit=8)

        # Pendientes (Requiere tu atención).
        attention = []
        if not company.is_accredited:
            attention.append({'icon': 'fa-check-circle', 'kind': 'info',
                              'text': 'Completa tu proceso de acreditación',
                              'cta': 'Ver', 'url': '/my/acreditacion'})
        for m in inv_pending:
            if m.invoice_date_due and m.invoice_date_due <= today + timedelta(days=7):
                venc = 'vencida' if m.invoice_date_due < today else 'vence pronto'
                attention.append({'icon': 'fa-money', 'kind': 'warning',
                                  'text': 'Factura %s %s' % (m.name, venc),
                                  'cta': 'Pagar', 'url': '/my/invoices'})
        for op in operations:
            if gate and op.stage_id.id == gate.id and company.is_accredited:
                attention.append({'icon': 'fa-clock-o', 'kind': 'info',
                                  'text': 'La operación %s espera acreditación de la otra parte' % op.name,
                                  'cta': 'Ver', 'url': '/importations/view/%s' % op.id})

        # KPIs según rol.
        if role == 'supplier':
            Offer = env['en.supply.offer'].sudo()
            Rel = env['en.counterparty.relation'].sudo()
            Tender = env['en.tender'].sudo()
            kpis = [
                {'icon': 'fa-tag', 'color': 'blue', 'label': 'Ofertas publicadas',
                 'value': Offer.search_count([('supplier_id', '=', company.id), ('state', '=', 'published')])},
                {'icon': 'fa-ship', 'color': 'teal', 'label': 'Operaciones en curso', 'value': len(operations)},
                {'icon': 'fa-users', 'color': 'green', 'label': 'Clientes en cartera',
                 'value': Rel.search_count([('supplier_id', '=', company.id)])},
                {'icon': 'fa-file-text-o', 'color': 'amber', 'label': 'Solicitudes abiertas',
                 'value': Tender.search_count([('state', '=', 'open')])},
            ]
        else:
            kpis = [
                {'icon': 'fa-ship', 'color': 'blue', 'label': 'Operaciones activas', 'value': len(operations)},
                {'icon': 'fa-clock-o', 'color': 'amber', 'label': 'Por acreditar', 'value': in_gate},
                {'icon': 'fa-file-text-o', 'color': 'red', 'label': 'Facturas pendientes',
                 'value': len(inv_pending),
                 'sub': ('%s %s' % (currency.symbol or '', '{:,.2f}'.format(inv_pending_amount))) if inv_pending_amount else ''},
                {'icon': 'fa-calendar', 'color': 'teal', 'label': 'Próximo arribo',
                 'value': next_arrival.strftime('%d/%m') if next_arrival else '—'},
            ]

        return {
            'dash_company': company,
            'dash_role': role,
            'dash_is_accredited': company.is_accredited,
            'dash_kpis': kpis,
            'dash_attention': attention,
            'dash_operations': ops,
            'dash_activity': activity,
            'dash_invoices': inv_list,
            'dash_currency': currency,
            'dash_notif_count': len(attention),
            'page_name': 'dashboard',
        }

    @http.route(['/my/seguimiento'], type='http', auth='user', website=True)
    def portal_my_seguimiento(self, **kw):
        """Página de seguimiento a nivel de empresa: estado de acreditación,
        recorrido (acreditación) y lista de operaciones de importación."""
        partner = request.env.user.partner_id
        company = partner.commercial_partner_id or partner
        Event = request.env['en.tracking.event'].sudo()
        timeline = Event.search(
            [('partner_id', '=', company.id), ('phase', '=', 'accreditation')],
            order='date asc')
        operations = request.env['importation.process'].sudo().search(
            [('customer_id', '=', company.id)], order='id desc')
        gate = request.env.ref(
            'pyxel_enetradex_backend.en_stage_pending_accreditation', raise_if_not_found=False)
        values = self._prepare_portal_layout_values()
        values.update({
            'company': company,
            'is_accredited': company.is_accredited,
            'timeline': timeline,
            'operations': operations,
            'gate_stage_id': gate.id if gate else False,
            'page_name': 'seguimiento',
        })
        return request.render('pyxel_import_website.portal_my_seguimiento', values)

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
        is_accredited = request.env['res.partner'].sudo().browse(business_partner_id).is_accredited

        if contact_type.type_of_contact in ['Client', 'Supplier']:
            lead = request.env['crm.lead'].sudo().search(
                [('partner_id', '=', business_partner_id)],
                order='create_date desc',
                limit=1
            )

            if lead:
                contract_status = lead.stage_id.name
                # if contact_type.type_of_contact == 'Client':
                #     is_accredited = request.env["res.partner.contract.import"].sudo().search([
                #         ("partner_id", "=", business_partner_id),
                #         ("active_contract", "=", True)
                #     ], limit=1)
                # elif contact_type.type_of_contact == 'Supplier':
                is_accredited = lead.partner_id.is_accredited

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
            'is_accredited': is_accredited,
        })

        return values
