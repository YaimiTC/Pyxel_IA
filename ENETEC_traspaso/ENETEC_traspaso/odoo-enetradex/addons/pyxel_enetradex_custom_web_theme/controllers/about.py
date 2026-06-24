from odoo import http
from odoo.http import request


class AgrimpexAboutController(http.Controller):

    _VALID_TABS = {"who", "services", "vision", "policy", "faqs"}

    @http.route(["/about"], type="http", auth="public", website=True, sitemap=True)
    def about(self, tab=None, **kwargs):
        active_tab = tab if tab in self._VALID_TABS else "who"
        values = {
            "company_logo": "/pyxel_enetradex_custom_web_theme/static/src/img/logo_about.png",
            "active_tab": active_tab,
        }
        return request.render("pyxel_enetradex_custom_web_theme.page_about", values)

    @http.route(["/my/about"], type="http", auth="user", website=True, sitemap=True)
    def about_internal(self, tab=None, **kwargs):
        active_tab = tab if tab in self._VALID_TABS else "who"
        values = {
            "company_logo": "/pyxel_enetradex_custom_web_theme/static/src/img/logo_about.png",
            "active_tab": active_tab,
        }
        return request.render("pyxel_enetradex_custom_web_theme.page_about", values)
