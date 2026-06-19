# controllers/portal_notifications.py
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class PortalNotifications(CustomerPortal):

    @http.route(['/my/notifications'], type='http', auth="user", website=True)
    def portal_notifications(self, **kw):
        # Example: fetch last 10 messages for this user
        partner = request.env.user.partner_id
        messages = request.env['mail.message'].sudo().search([
            ('partner_ids', 'in', partner.id)
        ], order='date desc', limit=10)

        values = {
            'page_name': 'notifications',
            'messages': messages,
        }
        return request.render('pyxel_enetradex_custom_web_theme.portal_notifications_template', values)
