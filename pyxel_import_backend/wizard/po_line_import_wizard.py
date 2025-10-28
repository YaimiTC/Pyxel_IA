# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _ as _tr
import base64
import io
import re
import logging

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except Exception:
    openpyxl = None


# -------------------- utilidades --------------------

def _col_to_idx(col_ref):
    """Convierte 'A'/'B'/'AA' o '1'/'2' a índice 0-based."""
    if isinstance(col_ref, int):
        return max(col_ref - 1, 0)
    s = (col_ref or '').strip()
    if not s:
        raise UserError(_tr("Las referencias de columna no pueden estar vacías."))
    if s.isdigit():
        return max(int(s) - 1, 0)
    s = s.upper()
    if not re.fullmatch(r'[A-Z]+', s):
        raise UserError(_tr("Columna inválida: %s (usa A,B,AA o 1,2,3)") % s)
    n = 0
    for ch in s:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _to_float(v):
    """Convierte strings tipo '$1,234.56' o '1.234,56' a float robustamente."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    s = re.sub(r'[^\d,.\-]', '', s)
    if s.count(',') and s.count('.'):
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    else:
        if s.count(',') and not s.count('.'):
            s = s.replace(',', '.')
    return float(s)


def _norm(txt):
    """Normaliza texto para comparar (mayúsculas y sin acentos sencillos)."""
    if not txt:
        return ''
    t = str(txt).upper()
    t = (t.replace('Á', 'A').replace('É', 'E').replace('Í', 'I')
           .replace('Ó', 'O').replace('Ú', 'U').replace('Ñ', 'N'))
    return t


# -------------------- wizard --------------------

class POLineImportWizard(models.TransientModel):
    _name = 'po.line.import.wizard'
    _description = 'Importar líneas a Orden de Compra desde Excel'

    # Contexto
    purchase_id = fields.Many2one('purchase.order', string="Orden de Compra", required=True)

    # Archivo
    file_data = fields.Binary(string="Archivo Excel (.xlsx)", required=True)
    file_name = fields.Char(string="Nombre de archivo")

    # Hoja/encabezado
    sheet_index = fields.Integer(string="Hoja (0=primera)", default=0)
    header_row = fields.Integer(string="Fila encabezado", default=1)

    # Mapeo de columnas (por defecto según tu layout: B,C,D,E)
    col_product = fields.Char(string="Columna Producto", required=True, default='B')
    col_uom = fields.Char(string="Columna U.M.", required=True, default='C')
    col_qty = fields.Char(string="Columna Cantidad", required=True, default='D')
    col_price = fields.Char(string="Columna Precio U.M.", required=True, default='E')

    # Opciones de control de lectura
    stop_at_first_label = fields.Boolean(
        string="Detener en primera etiqueta de recargos",
        default=True,
        help="La tabla de productos termina en la fila anterior a la primera etiqueta "
             "como IMPORTE EXWORK, GASTO FOB, FLETE, SEGURO u OTROS GASTOS."
    )
    max_data_rows = fields.Integer(
        string="Máx. filas de datos",
        help="Si se define, limita el número de filas leídas desde 'Fila encabezado'+1."
    )
    empty_product_break = fields.Integer(
        string="Corte por filas vacías",
        default=2,
        help="Si se encuentran esta cantidad de filas consecutivas sin Producto, se asume fin de tabla."
    )
    strict_numeric = fields.Boolean(
        string="Modo estricto numérico",
        default=False,
        help="Si está activo, una Cantidad/Precio no numérica detiene el proceso con error. "
             "Si está desactivado, la fila se omite y se agrega una nota."
    )

    # Opciones de creación
    create_missing_products = fields.Boolean(string="Crear productos inexistentes", default=True)
    default_product_type = fields.Selection([
        ('product', 'Almacenable'),
        ('consu', 'Consumible'),
        ('service', 'Servicio'),
    ], string="Tipo por defecto al crear", default='product')
    default_uom_id = fields.Many2one('uom.uom', string="UoM por defecto al crear")

    clear_existing_lines = fields.Boolean(string="Reemplazar líneas existentes", default=False)

    # Servicios (recargos)
    product_freight_id = fields.Many2one('product.product', string="Producto Servicio Flete",
                                         domain=[('detailed_type', '=', 'service')])
    product_insurance_id = fields.Many2one('product.product', string="Producto Servicio Seguro",
                                           domain=[('detailed_type', '=', 'service')])
    product_other_id = fields.Many2one('product.product', string="Producto Servicio Otros gastos",
                                       domain=[('detailed_type', '=', 'service')])
    product_fob_id = fields.Many2one('product.product', string="Producto Servicio Gasto FOB",
                                     domain=[('detailed_type', '=', 'service')])

    note = fields.Text(readonly=True)

    # ================= Helpers Excel =================

    def _get_ws(self, wb):
        idx = self.sheet_index or 0
        sheets = wb.worksheets
        if idx < 0 or idx >= len(sheets):
            raise UserError(_tr("Índice de hoja fuera de rango. El archivo tiene %s hoja(s).") % len(sheets))
        return sheets[idx]

    def _to_float_safe(self, v):
        """Devuelve (float, ok_bool) sin lanzar UserError."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return 0.0, False
        try:
            return _to_float(v), True
        except Exception:
            return 0.0, False

    def _parse_surcharges(self, ws, return_first_row=False):
        """
        Busca etiquetas de recargos en toda la hoja y toma el valor en la celda adyacente derecha.
        Retorna dict con llaves: exworks, fob, freight, insurance, others.
        Si return_first_row=True, también retorna la primera fila donde aparece alguna etiqueta.
        """
        labels = {
            'IMPORTE EXWORK': 'exworks',
            'GASTO FOB': 'fob',
            'FLETE': 'freight',
            'SEGURO': 'insurance',
            'OTROS GASTOS': 'others',
        }
        found = {}
        first_row = None
        for row in ws.iter_rows():
            for cell in row:
                val = cell.value
                if not val or not isinstance(val, str):
                    continue
                key_txt = _norm(val)
                for k, code in labels.items():
                    if key_txt.startswith(k):
                        # valor a la derecha (como en tu layout E->F)
                        right_col = cell.column + 1
                        v = cell.parent.cell(row=cell.row, column=right_col).value
                        v_float, ok = self._to_float_safe(v)
                        if ok:
                            found[code] = v_float
                        if return_first_row and first_row is None:
                            first_row = cell.row
        return (found, first_row) if return_first_row else found

    def _parse_table_lines(self, ws):
        """
        Devuelve (lines, notes):
          lines = [{'name': str, 'uom': str, 'qty': float, 'price': float}, ...]
          notes = [mensajes]
        Aplica reglas de corte según opciones del wizard.
        """
        c_prod = _col_to_idx(self.col_product)
        c_uom = _col_to_idx(self.col_uom)
        c_qty = _col_to_idx(self.col_qty)
        c_price = _col_to_idx(self.col_price)

        start_row = max(self.header_row or 1, 1) + 1
        end_row = ws.max_row

        if self.stop_at_first_label:
            _, first_label_row = self._parse_surcharges(ws, return_first_row=True)
            if first_label_row:
                end_row = min(end_row, first_label_row - 1)

        if self.max_data_rows and self.max_data_rows > 0:
            end_row = min(end_row, start_row + self.max_data_rows - 1)

        lines, notes = [], []
        empty_streak = 0

        for r in range(start_row, end_row + 1):
            def getv(ci):
                return ws.cell(row=r, column=ci + 1).value if ci is not None else None

            raw_name = getv(c_prod)
            name = (raw_name or '').strip() if isinstance(raw_name, str) else raw_name

            if not name:
                empty_streak += 1
                if self.empty_product_break and empty_streak >= self.empty_product_break:
                    break
                continue
            else:
                empty_streak = 0

            raw_uom = getv(c_uom)
            uom = (raw_uom or '').strip() if isinstance(raw_uom, str) else raw_uom

            qty_val, qty_ok = self._to_float_safe(getv(c_qty))
            price_val, price_ok = self._to_float_safe(getv(c_price))

            if self.strict_numeric and (not qty_ok or not price_ok):
                raise UserError(_tr("Fila %s: valores numéricos inválidos. Cantidad=%s, Precio=%s")
                                % (r, getv(c_qty), getv(c_price)))

            if not qty_ok or not price_ok:
                notes.append(_tr("Fila %s omitida por datos no numéricos (Cantidad=%s, Precio=%s).")
                             % (r, getv(c_qty), getv(c_price)))
                continue

            lines.append({
                'name': str(name),
                'uom': str(uom or ''),
                'qty': qty_val,
                'price': price_val,
            })

        return lines, notes

    # ================= Helpers de datos =================

    def _find_uom(self, name):
        if not name:
            return self.default_uom_id
        UoM = self.env['uom.uom'].sudo()
        uom = UoM.search([('name', '=ilike', name)], limit=1)
        if not uom:
            uom = UoM.search([('name', 'ilike', name)], limit=1)
        return uom or self.default_uom_id

    def _get_or_create_product(self, name, uom):
        Product = self.env['product.product'].sudo()
        prod = Product.search([('name', '=ilike', name)], limit=1)
        if prod:
            return prod
        if not self.create_missing_products:
            raise UserError(_tr("El producto '%s' no existe y la opción de crear está desactivada.") % name)

        # Fallback seguro de UoM si no viene
        if not uom:
            try:
                uom = self.default_uom_id or self.env.ref('uom.product_uom_unit')
            except Exception:
                uom = self.default_uom_id  # si no existe el ref, usa el default si está

        vals_tmpl = {
            'name': name,
            'type': self.default_product_type,
            'uom_id': uom.id if uom else False,
            'uom_po_id': uom.id if uom else False,
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        }
        tmpl = self.env['product.template'].sudo().create(vals_tmpl)
        return tmpl.product_variant_id

    # ================= Proceso principal =================

    def action_import(self):
        if not self.purchase_id:
            raise UserError(_tr("Debes indicar la Orden de Compra."))
        if not self.file_data:
            raise UserError(_tr("Adjunta el archivo Excel."))
        if openpyxl is None:
            raise UserError(_tr("Falta la librería 'openpyxl'."))

        try:
            data = base64.b64decode(self.file_data)
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        except Exception as e:
            raise UserError(_tr("No se pudo leer el Excel: %s") % e)

        ws = self._get_ws(wb)

        # 1) Recargos + detectar primera etiqueta (para el corte)
        surcharges, _ = self._parse_surcharges(ws, return_first_row=True)

        # 2) Líneas de productos (ya acotadas y tolerantes)
        product_lines, parse_notes = self._parse_table_lines(ws)

        PO = self.purchase_id.sudo()

        if self.clear_existing_lines and PO.order_line:
            PO.order_line.unlink()

        created_count = 0
        amount_exworks_calc = 0.0

        for l in product_lines:
            uom = self._find_uom(l['uom'])
            prod = self._get_or_create_product(l['name'], uom)
            self.env['purchase.order.line'].sudo().create({
                'order_id': PO.id,
                'product_id': prod.id,
                'name': l['name'],
                'product_qty': l['qty'],
                'price_unit': l['price'],
                'product_uom': (uom.id if uom else prod.uom_po_id.id),
            })
            created_count += 1
            amount_exworks_calc += (l['qty'] * l['price'])

        notes = list(parse_notes)

        # Compara IMPORTE EXWORK si vino y hay líneas
        if 'exworks' in surcharges and product_lines:
            if round(surcharges['exworks'], 2) != round(amount_exworks_calc, 2):
                notes.append(_tr("Aviso: IMPORTE EXWORK del Excel (%(x)s) difiere del calculado (%(y)s).") % {
                    'x': surcharges['exworks'],
                    'y': amount_exworks_calc,
                })

        # Crear líneas de servicios (1 unidad c/u)
        def _create_service_line(prod_field, amount, label_fallback):
            prod = getattr(self, prod_field)
            if amount in (None, 0):
                return
            if not prod:
                notes.append(_tr("Falta configurar el %s. Valor encontrado: %s") % (label_fallback, amount))
                return
            self.env['purchase.order.line'].sudo().create({
                'order_id': PO.id,
                'product_id': prod.id,
                'name': prod.display_name,
                'product_qty': 1.0,
                'price_unit': amount,
                'product_uom': prod.uom_po_id.id or prod.uom_id.id,
            })

        _create_service_line('product_fob_id', surcharges.get('fob'), "Producto Servicio Gasto FOB")
        _create_service_line('product_freight_id', surcharges.get('freight'), "Producto Servicio Flete")
        _create_service_line('product_insurance_id', surcharges.get('insurance'), "Producto Servicio Seguro")
        _create_service_line('product_other_id', surcharges.get('others'), "Producto Servicio Otros gastos")

        msg = _tr("Se importaron %(n)s líneas de productos en la OC %(po)s.") % {
            'n': created_count,
            'po': PO.name,
        }

        if notes:
            msg += "\n" + "\n".join(notes)
        self.note = msg

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _tr('Importación completada'), 'message': msg, 'sticky': False}
        }
