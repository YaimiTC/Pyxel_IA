from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
import werkzeug
import logging

_logger = logging.getLogger(__name__)


class BaseController(http.Controller):

    def _prepare_page_values(self, page_name=None):
        user = request.env.user
        partner = user.partner_id.sudo()  # Acceso seguro al partner
        # Check if user is internal (admin) or portal
        is_admin = not user.share  # Internal users have share=False
        is_portal = user.has_group('base.group_portal')

        # New logic for dealer checks
        # is_dealer = bool(partner.is_dealer)
        # has_dealer_boss = bool(partner.dealer_boss_id)

        values = {
            'page_name': page_name,
            'user': user,
            'is_logged_in': not user._is_public(),
            'is_portal': is_portal,
            'is_admin': is_admin,
            # 'is_dealer': is_dealer,
            # 'has_dealer_boss': has_dealer_boss,
        }
        _logger.info("Valores pasados a la plantilla: %s", values)
        return values

    @http.route('/api/user-data', type='json', auth='user', website=True)
    def get_user_data(self, **kwargs):
        try:
            user = request.env.user
            partner = user.partner_id.sudo()

            user_data = {
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'login': user.login,
                    'email': user.email,
                    'partner_id': user.partner_id.id,
                    'is_internal': not user.share,
                    'is_portal': user.has_group('base.group_portal'),
                    'profile_image': user.image_128.decode('utf-8') if user.image_128 else None,
                },
                'company': None,
                'contacts': [],
                'addresses': []
            }

            # Manejo seguro de company
            if partner.parent_id:
                company = partner.parent_id.sudo()
                user_data['company'] = {
                    'id': company.id,
                    'name': company.name,
                    'email': company.email,
                    # Campos opcionales con operador ternario
                    'country': company.country_id.name if company.country_id else None,
                    'state': company.state_id.name if company.state_id else None,
                }

            # Lectura segura de direcciones
            addresses = partner.sudo().search_read(
                [('id', 'child_of', partner.id)],
                ['street', 'street2', 'city', 'zip', 'country_id', 'state_id']
            )

            for address in addresses:
                # Convertir tuplas a objetos
                address['country'] = address['country_id'][1] if address.get('country_id') else None
                address['state'] = address['state_id'][1] if address.get('state_id') else None
                del address['country_id']
                del address['state_id']

            user_data['addresses'] = addresses

            return {'status': 200, 'data': user_data}

        except Exception as e:
            _logger.error("Error detallado: %s", str(e), exc_info=True)  # <--- LOG MEJORADO
            return {'status': 500, 'error': _("Error retrieving user data")}
