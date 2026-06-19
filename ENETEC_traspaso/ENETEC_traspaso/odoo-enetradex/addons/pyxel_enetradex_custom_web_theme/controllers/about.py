from odoo import http
from odoo.http import request


class AgrimpexAboutController(http.Controller):

    @http.route(["/about"], type="http", auth="public", website=True, sitemap=True)
    def about(self, **kwargs):
        values = {
            "company_logo": "/pyxel_enetradex_custom_web_theme/static/src/img/logo_about.png",
        }
        return request.render("pyxel_enetradex_custom_web_theme.page_about", values)

    @http.route(["/my/about"], type="http", auth="user", website=True, sitemap=True)
    def about_internal(self, **kwargs):
        values = {
            "company_logo": "/pyxel_enetradex_custom_web_theme/static/src/img/logo_about.png",
        }
        return request.render("pyxel_enetradex_custom_web_theme.page_about", values)
