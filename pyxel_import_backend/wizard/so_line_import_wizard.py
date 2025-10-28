# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import re
import logging

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except Exception:
    openpyxl = None


# -------------------- utilidades genéricas --------------------

def _col_to_idx(col_ref):
    """Convierte 'A'/'B'/'AA' o '1'/'2' a índice 0-based."""
    if isinstance(col_ref, int):
        return max(col_ref - 1, 0)
    s = (col_ref or '').strip()
    if not s:
        raise UserError(_("Las referencias de columna no pueden estar vacías."))
    if s.isdigit():
        return max(int(s) - 1, 0)
    s = s.upper()
    if not re.fullmatch(r'[A-Z]+', s):
        raise UserError(_("Columna inválida: %s (usa A,B,AA o 1,2,3)") % s)
    n = 0
    for ch in s:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _clean_numeric_text(v):
    """Quita símbolos comunes de moneda, separadores de miles, etc."""
    if v is None:
        return ''
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).strip()
    # quita todo excepto dígitos, coma, punto y signo -
    s = re.sub(r'[^\d,.\-]', '', s)
    return s


def _to_float(v):
    """
    Convierte strings tipo '$1,234.56' o '1.234,56' a float robustamente.
    Lanza UserError si no se puede.
    """
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)

    s = _clean_numeric_text(v)
    if not s:
        return 0.0

    # Si hay coma y punto, asumimos que el separador decimal es el último que aparece.
    if s.count(',') and s.count('.'):
        if s.rfind(',') > s.rfind('.'):
            # coma es decimal -> quitar puntos (miles)
            s = s.replace('.', '').replace(',', '.')
        else:
            # punto es decimal -> quitar comas (miles)
            s = s.replace(',', '')
    else:
        # Solo coma -> úsala como decimal
        if s.count(',') and not s.count('.'):
            s = s.replace(',', '.')

    try:
        return float(s)
    except Exception:
        raise UserError(_("No se pudo convertir a número: %s") % v)


def _to_float_safe(v):
    """
    Retorna (float_value, ok_bool) sin lanzar error.
    """
    try:
        fv = _to_float(v)
        return fv, True
    except Exception:
        return 0.0, False


# -------------------- Wizard --------------------

class SOLineImportWizard(models.TransientModel):
    _name = 'so.line.import.wizard'
    _description = 'Importar líneas a Pedido de Venta desde Excel'

    # Contexto: se abre desde la venta
    sale_id = fields.Many2one(
        'sale.order',
        string="Pedido de Venta",
        required=True,
        help="Venta destino donde se insertarán las líneas."
    )

    # Archivo
    file_data = fields.Binary(
        string="Archivo Excel (.xlsx)",
        required=True
    )
    file_name = fields.Char(string="Nombre de archivo")

    # Hoja / encabezado
    sheet_index = fields.Integer(
        string="Hoja (0=primera)",
        default=0
    )
    header_row_products = fields.Integer(
        string="Fila encabezado productos",
        default=1,
        help="Fila donde están los títulos No./Producto/Código/... (la siguiente es la primera de datos)"
    )
    header_row_services = fields.Integer(
        string="Fila encabezado servicios",
        default=1,
        help="Fila donde están los títulos Servicio / Importe (la siguiente es la primera de datos)"
    )

    # ===== Mapeo columnas para PRODUCTOS =====
    col_prod_name = fields.Char(
        string="Columna Producto",
        default='B',
        required=True,
        help="Columna donde está el nombre/descripcion del producto. Ej: B"
    )
    col_prod_code = fields.Char(
        string="Columna Código",
        default='C',
        required=False,
        help="Referencia interna / código. Ej: C"
    )
    col_prod_uom = fields.Char(
        string="Columna U/M",
        default='D',
        required=True,
        help="Columna U/M. Ej: D"
    )
    col_prod_qty = fields.Char(
        string="Columna Cantidad",
        default='E',
        required=True,
        help="Columna Cantidad. Ej: E"
    )
    col_prod_price = fields.Char(
        string="Columna Precio Unitario",
        default='F',
        required=True,
        help="Columna Precio Unitario. Ej: F"
    )

    # ===== Mapeo columnas para SERVICIOS =====
    col_srv_name = fields.Char(
        string="Columna Servicio",
        default='J',
        required=True,
        help="Nombre del servicio. Ej: J"
    )
    col_srv_amount = fields.Char(
        string="Columna Importe Servicio",
        default='K',
        required=True,
        help="Importe del servicio. Ej: K"
    )

    # ===== Opciones de lectura (productos) =====
    max_product_rows = fields.Integer(
        string="Máx. filas productos",
        help="Si se define (>0), corta la lectura de productos a tantas filas."
    )
    empty_product_break = fields.Integer(
        string="Corte por filas vacías (productos)",
        default=2,
        help="Si se encuentran esta cantidad de filas consecutivas sin producto, se asume fin de la tabla."
    )
    strict_numeric_products = fields.Boolean(
        string="Modo estricto numérico (productos)",
        default=False,
        help="Si está activo, una Cantidad/Precio no numérica en productos genera error. "
             "Si está desactivado, esa fila se omite."
    )

    # ===== Opciones de lectura (servicios) =====
    max_service_rows = fields.Integer(
        string="Máx. filas servicios",
        help="Si se define (>0), corta la lectura de servicios a tantas filas."
    )
    empty_service_break = fields.Integer(
        string="Corte por filas vacías (servicios)",
        default=2,
        help="Si se encuentran esta cantidad de filas consecutivas sin servicio, se asume fin de la tabla."
    )
    strict_numeric_services = fields.Boolean(
        string="Modo estricto numérico (servicios)",
        default=False,
        help="Si está activo, un Importe no numérico en servicios genera error. "
             "Si está desactivado, esa fila se omite."
    )

    # ===== Creación de productos =====
    create_missing_products = fields.Boolean(
        string="Crear productos inexistentes",
        default=True,
        help="Si no se encuentra un producto en Odoo, se creará automáticamente."
    )
    default_product_type = fields.Selection([
        ('product', 'Almacenable'),
        ('consu', 'Consumible'),
        ('service', 'Servicio'),
    ], string="Tipo de producto por defecto", default='product')

    default_uom_id = fields.Many2one(
        'uom.uom',
        string="U/M por defecto",
        help="Si no encontramos la unidad del Excel en Odoo, usamos esta."
    )

    clear_existing_lines = fields.Boolean(
        string="Reemplazar líneas existentes",
        default=False,
        help="Si está activo, borra las líneas actuales del pedido de venta antes de importar."
    )

    # Nota (resultado)
    note = fields.Text(readonly=True)

    # ================= Helpers Excel =================

    def _get_ws(self, wb):
        idx = self.sheet_index or 0
        sheets = wb.worksheets
        if idx < 0 or idx >= len(sheets):
            raise UserError(_("Índice de hoja fuera de rango. El archivo tiene %s hoja(s).") % len(sheets))
        return sheets[idx]

    # --------- parsing tabla PRODUCTOS ----------

    def _parse_product_lines(self, ws):
        """
        Lee las filas de productos debajo de header_row_products.
        Devuelve (product_lines, notes)
        product_lines: [ {name, code, uom, qty, price}, ...]
        """
        start_row = max(self.header_row_products or 1, 1) + 1
        end_row = ws.max_row

        product_lines = []
        notes = []
        empty_streak = 0
        rows_read = 0

        c_name = _col_to_idx(self.col_prod_name)
        c_code = _col_to_idx(self.col_prod_code) if self.col_prod_code else None
        c_uom = _col_to_idx(self.col_prod_uom)
        c_qty = _col_to_idx(self.col_prod_qty)
        c_price = _col_to_idx(self.col_prod_price)

        for r in range(start_row, end_row + 1):
            # Límite máximo de filas productos
            if self.max_product_rows and rows_read >= self.max_product_rows:
                break

            def getv(ci):
                return ws.cell(row=r, column=ci + 1).value if ci is not None else None

            raw_name = getv(c_name)
            name = (raw_name or '').strip() if isinstance(raw_name, str) else raw_name

            if not name:
                empty_streak += 1
                if self.empty_product_break and empty_streak >= self.empty_product_break:
                    break
                continue
            else:
                empty_streak = 0

            raw_code = getv(c_code) if c_code is not None else ''
            code = (raw_code or '').strip() if isinstance(raw_code, str) else raw_code or ''

            raw_uom = getv(c_uom)
            uom_txt = (raw_uom or '').strip() if isinstance(raw_uom, str) else raw_uom or ''

            raw_qty = getv(c_qty)
            raw_price = getv(c_price)

            qty_val, qty_ok = _to_float_safe(raw_qty)
            price_val, price_ok = _to_float_safe(raw_price)

            if self.strict_numeric_products and (not qty_ok or not price_ok):
                raise UserError(_("Fila %s (productos): valores numéricos inválidos. Cantidad=%s, Precio=%s")
                                % (r, raw_qty, raw_price))

            if not qty_ok or not price_ok:
                notes.append(_("Fila %s omitida en productos por datos no numéricos (Cantidad=%s, Precio=%s).")
                             % (r, raw_qty, raw_price))
                continue

            product_lines.append({
                'name': str(name),
                'code': str(code or ''),
                'uom': str(uom_txt),
                'qty': qty_val,
                'price': price_val,
            })
            rows_read += 1

        return product_lines, notes

    # --------- parsing tabla SERVICIOS ----------

    def _parse_service_lines(self, ws):
        """
        Lee las filas de servicios debajo de header_row_services.
        Devuelve (service_lines, notes)
        service_lines: [ {name, amount}, ...]
        """
        start_row = max(self.header_row_services or 1, 1) + 1
        end_row = ws.max_row

        service_lines = []
        notes = []
        empty_streak = 0
        rows_read = 0

        c_srv_name = _col_to_idx(self.col_srv_name)
        c_srv_amount = _col_to_idx(self.col_srv_amount)

        for r in range(start_row, end_row + 1):
            # Límite máximo de filas servicios
            if self.max_service_rows and rows_read >= self.max_service_rows:
                break

            def getv(ci):
                return ws.cell(row=r, column=ci + 1).value if ci is not None else None

            raw_sname = getv(c_srv_name)
            sname = (raw_sname or '').strip() if isinstance(raw_sname, str) else raw_sname

            raw_amt = getv(c_srv_amount)

            if not sname:
                empty_streak += 1
                if self.empty_service_break and empty_streak >= self.empty_service_break:
                    break
                continue
            else:
                empty_streak = 0

            amt_val, amt_ok = _to_float_safe(raw_amt)

            if self.strict_numeric_services and not amt_ok:
                raise UserError(_("Fila %s (servicios): importe no numérico (%s).") % (r, raw_amt))

            if not amt_ok:
                notes.append(_("Fila %s omitida en servicios por importe no numérico (%s).") % (r, raw_amt))
                continue

            service_lines.append({
                'name': str(sname),
                'amount': amt_val,
            })
            rows_read += 1

        return service_lines, notes

    # ================= Helpers de datos en Odoo =================

    def _find_uom(self, name):
        """
        Busca la UoM por nombre (ilike).
        Si no encuentra, usa default_uom_id.
        """
        if not name:
            return self.default_uom_id
        UoM = self.env['uom.uom'].sudo()
        u = UoM.search([('name', '=ilike', name)], limit=1)
        if not u:
            u = UoM.search([('name', 'ilike', name)], limit=1)
        return u or self.default_uom_id

    def _find_or_create_product(self, name, code, uom_rec):
        """
        Busca primero por código interno (default_code),
        luego por nombre. Si no existe y está permitido, crea.
        """
        Product = self.env['product.product'].sudo()

        prod = False
        if code:
            prod = Product.search([('default_code', '=ilike', code)], limit=1)
        if not prod:
            prod = Product.search([('name', '=ilike', name)], limit=1)

        if prod:
            return prod

        if not self.create_missing_products:
            raise UserError(_("El producto '%s' no existe y la opción de crear está desactivada.") % name)

        tmpl_vals = {
            'name': name,
            'default_code': code or False,
            'type': self.default_product_type,
            'uom_id': uom_rec.id if uom_rec else False,
            'uom_po_id': uom_rec.id if uom_rec else False,
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        }
        tmpl = self.env['product.template'].sudo().create(tmpl_vals)
        return tmpl.product_variant_id

    # ================= Acción principal =================

    def action_import(self):
        if not self.sale_id:
            raise UserError(_("Debes indicar el Pedido de Venta."))
        if not self.file_data:
            raise UserError(_("Adjunta el archivo Excel."))
        if openpyxl is None:
            raise UserError(_("Falta la librería 'openpyxl' en el servidor."))

        try:
            data = base64.b64decode(self.file_data)
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        except Exception as e:
            raise UserError(_("No se pudo leer el Excel: %s") % e)

        ws = self._get_ws(wb)

        # 1) parse productos
        product_lines, notes_products = self._parse_product_lines(ws)

        # 2) parse servicios
        service_lines, notes_services = self._parse_service_lines(ws)

        if not product_lines and not service_lines:
            raise UserError(_("No se detectaron líneas válidas ni de productos ni de servicios."))

        order = self.sale_id.sudo()

        # limpiar si corresponde
        if self.clear_existing_lines and order.order_line:
            order.order_line.unlink()

        created_prod = 0
        created_srv = 0

        # Insertar productos
        for pl in product_lines:
            uom_rec = self._find_uom(pl['uom'])
            prod_rec = self._find_or_create_product(pl['name'], pl['code'], uom_rec)

            self.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': prod_rec.id,
                'name': pl['name'],
                'product_uom': uom_rec.id if uom_rec else prod_rec.uom_id.id,
                'product_uom_qty': pl['qty'],
                'price_unit': pl['price'],
            })
            created_prod += 1

        # Insertar servicios
        for sl in service_lines:
            # Para servicios vamos a intentar buscar/crear por nombre como producto tipo service.
            uom_service = self.default_uom_id
            srv_prod = self._find_or_create_product(sl['name'], False, uom_service)

            # Forzar que ese producto sea tipo servicio si no lo era
            if srv_prod.product_tmpl_id.type != 'service':
                srv_prod.product_tmpl_id.write({'type': 'service'})

            self.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': srv_prod.id,
                'name': sl['name'],
                'product_uom': uom_service.id if uom_service else srv_prod.uom_id.id,
                'product_uom_qty': 1.0,
                'price_unit': sl['amount'],
            })
            created_srv += 1

        notes = []
        notes.extend(notes_products)
        notes.extend(notes_services)

        msg = _(
            "Se importaron %(p)s líneas de productos y %(s)s líneas de servicios en el Pedido de Venta %(so)s."
        ) % {
            'p': created_prod,
            's': created_srv,
            'so': order.name,
        }

        if notes:
            msg += "\n" + "\n".join(notes)

        self.note = msg

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Importación completada'),
                'message': msg,
                'sticky': False
            }
        }
