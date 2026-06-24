from odoo import http
from odoo.http import request


class SuppliersController(http.Controller):

    @http.route(["/proveedores"], type="http", auth="public", website=True, sitemap=True)
    def suppliers(self, q=None, product=None, **kwargs):
        Partner = request.env["res.partner"].sudo()
        domain = [("en_is_public_provider", "=", True), ("supplier_rank", ">", 0)]
        partners = Partner.search(domain, order="name asc")

        # Filtrar por texto
        if q:
            partners = partners.filtered(
                lambda p: q.lower() in (p.name or "").lower()
                or any(q.lower() in (l.product_id.name or "").lower()
                       for o in p.en_supply_offer_ids.filtered(lambda o: o.state == "published")
                       for l in o.line_ids)
            )

        # Filtrar por tipo de producto
        if product:
            partners = partners.filtered(
                lambda p: any(
                    product.lower() in (l.product_id.name or "").lower()
                    for o in p.en_supply_offer_ids.filtered(lambda o: o.state == "published")
                    for l in o.line_ids
                )
            )

        countries = partners.mapped("country_id")
        total_products = sum(
            len(o.line_ids)
            for p in partners
            for o in p.en_supply_offer_ids.filtered(lambda o: o.state == "published")
        )

        values = {
            "suppliers": partners,
            "q": q or "",
            "active_product": product or "",
            "stat_suppliers": len(partners),
            "stat_products": total_products,
            "stat_countries": len(countries),
        }
        return request.render("pyxel_enetradex_custom_web_theme.page_suppliers", values)
