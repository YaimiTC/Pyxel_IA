import re
from odoo import models, fields, api, _


class SaleOrderProcess(models.Model):
    _name = "sale.order.process"
    _description = "Proceso de órdenes de venta"
    _order = "name desc"

    name = fields.Char(string="Referencia", required=True, copy=False, readonly=True, default="Nuevo")
    state = fields.Selection([('open', 'Abierto'), ('closed', 'Cerrado')], default='open', tracking=True)

    sale_order_ids = fields.One2many('sale.order', 'process_id', string="Órdenes de venta relacionadas")
    importation_id = fields.Many2one('importation.process', string="Importación Cerrada", readonly=True)

    year = fields.Integer(string="Año", compute="_compute_year", store=True, index=True)

    # ---------- helpers ----------
    def _extract_year_from_name(self, name):
        """Saca el año desde el name con formatos tipo:
           - SLI-0230-2025
           - SLI-0001-26-26   (año 26)
           - 0001-2026-HAV
        """
        name = (name or "").strip()

        # 1) Si hay año de 4 dígitos, ese manda
        m = re.search(r"(19|20)\d{2}", name)
        if m:
            return int(m.group(0))

        # 2) Si hay dos dígitos tipo -26-26 o -25-26, tomo el primero (25,26...)
        m = re.search(r"-(\d{2})-(\d{2})$", name)
        if m:
            yy = int(m.group(1))
            # Pivot dinámico para NO amarrarte a 2000 siempre:
            # - Si hoy es 2026 => yy=26 => 2026
            # - Si yy es "mayor" que el año actual % 100 + 1, lo interpreto como siglo anterior.
            current_year = fields.Date.today().year
            curr_yy = current_year % 100
            century = current_year - curr_yy  # 2000 si estamos 20xx
            if yy <= curr_yy + 1:
                return century + yy
            return (century - 100) + yy  # siglo anterior

        return fields.Date.today().year  # fallback razonable

    # ---------- compute ----------
    @api.depends("name")
    def _compute_year(self):
        for rec in self:
            # si ya tiene year válido, lo dejamos (no lo pisamos)
            if rec.year:
                continue
            rec.year = rec._extract_year_from_name(rec.name)

    # ---------- create ----------
    @api.model
    def create(self, vals):
        if vals.get('name', 'Nuevo') == 'Nuevo':
            user = self.env.user
            province_code = user.partner_id.state_id.code or "XX"
            today_year = fields.Date.today().year

            sequence = self.env['ir.sequence'].next_by_code('sale.order.process.seq') or '0000'
            vals['name'] = f"{sequence}-{today_year}-{province_code}"

            # year por defecto en create (sin compute raro)
            vals['year'] = today_year
        else:
            # Si creas con name explícito y no mandan year, lo inferimos
            if not vals.get('year') and vals.get('name'):
                vals['year'] = self._extract_year_from_name(vals['name'])

        return super().create(vals)
