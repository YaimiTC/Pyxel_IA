# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64, io, re
import logging

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except Exception:
    openpyxl = None


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


def _to_float(v):
    """Convierte strings tipo '$1,234.56' o '1.234,56' a float robustamente."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    # quitar símbolo moneda y espacios
    s = re.sub(r'[^\d,.\-]', '', s)
    # si hay coma y punto, decidir separador decimal
    if s.count(',') and s.count('.'):
        # asumir que el último separador es decimal
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    else:
        # si solo hay coma, usarla como decimal
        if s.count(',') and not s.count('.'):
            s = s.replace(',', '.')
        else:
            s = s
    try:
        return float(s)
    except Exception:
        raise UserError(_("No se pudo convertir a número: %s") % v)


class POLineImportWizard(models.TransientModel):
    _name = 'po.line.import.wizard'
    _description = 'Importar líneas a Orden de Compra desde Excel'

    # Contexto: abrir desde una Purchase Order
    purchase_id = fields.Many2one('purchase.order', string="Orden de Compra", required=True)

    # Archivo
    file_data = fields.Binary(string="Archivo Excel (.xlsx)", required=True)
    file_name = fields.Char(string="Nombre de archivo")

    # Hoja/encabezado
    sheet_index = fields.Integer(string="Hoja (0=primera)", default=0)
    header_row = fields.Integer(string="Fila encabezado", default=1)

    # Mapeo de columnas
    col_product = fields.Char(string="Columna Producto", required=True, help="Ej: A o 1")
    col_uom = fields.Char(string="Columna UoM", required=True, help="Ej: B o 2 (nombre/abreviatura Unidad)")
    col_qty = fields.Char(string="Columna Cantidad", required=True, help="Ej: C o 3")
    col_price = fields.Char(string="Columna Precio Unitario", required=True, help="Ej: D o 4")

    # Opciones
    create_missing_products = fields.Boolean(string="Crear productos inexistentes", default=True)
    default_product_type = fields.Selection([
        ('product', 'Almacenable'),
        ('consu', 'Consumible'),
        ('service', 'Servicio'),
    ], string="Tipo por defecto al crear", default='product')
    default_uom_id = fields.Many2one('uom.uom', string="UoM por defecto al crear")

    clear_existing_lines = fields.Boolean(string="Reemplazar líneas existentes", default=False)

    # Servicios especiales a mapear
    product_freight_id = fields.Many2one('product.product', string="Producto Servicio Flete",
                                         domain=[('detailed_type', '=', 'service')])
    product_insurance_id = fields.Many2one('product.product', string="Producto Servicio Seguro",
                                           domain=[('detailed_type', '=', 'service')])
    product_other_id = fields.Many2one('product.product', string="Producto Servicio Otros gastos",
                                       domain=[('detailed_type', '=', 'service')])
    product_fob_id = fields.Many2one('product.product', string="Producto Servicio Gasto FOB",
                                     domain=[('detailed_type', '=', 'service')])

    note = fields.Text(readonly=True)

    # ===== Helpers Excel =====
    def _get_ws(self, wb):
        idx = self.sheet_index or 0
        sheets = wb.worksheets
        if idx < 0 or idx >= len(sheets):
            raise UserError(_("Índice de hoja fuera de rango. El archivo tiene %s hoja(s).") % len(sheets))
        return sheets[idx]

    def _parse_table_lines(self, ws):
        """
        Devuelve lista de líneas de productos:
        [{'name': str, 'uom': str, 'qty': float, 'price': float}, ...]
        """
        c_prod = _col_to_idx(self.col_product)
        c_uom = _col_to_idx(self.col_uom)
        c_qty = _col_to_idx(self.col_qty)
        c_price = _col_to_idx(self.col_price)

        start_row = max(self.header_row or 1, 1) + 1
        lines = []
        for r in range(start_row, ws.max_row + 1):
            getv = lambda ci: ws.cell(row=r, column=ci + 1).value if ci is not None else None
            name = (getv(c_prod) or '').strip() if isinstance(getv(c_prod), str) else getv(c_prod)
            if not name:
                # si no hay producto, no procesar fila
                continue
            uom = (getv(c_uom) or '').strip() if isinstance(getv(c_uom), str) else getv(c_uom)
            qty = _to_float(getv(c_qty))
            price = _to_float(getv(c_price))
            lines.append({'name': str(name), 'uom': str(uom or ''), 'qty': qty, 'price': price})
        return lines

    def _parse_surcharges(self, ws):
        """
        Busca en toda la hoja etiquetas conocidas y toma el valor en la celda adyacente derecha.
        Retorna dict con posibles llaves: exworks, fob, freight, insurance, others
        """
        labels = {
            'IMPORTE EXWORK': 'exworks',
            'GASTO FOB': 'fob',
            'FLETE': 'freight',
            'SEGURO': 'insurance',
            'OTROS GASTOS': 'others',
        }
        found = {}
        for row in ws.iter_rows():
            for cell in row:
                val = cell.value
                if not val or not isinstance(val, str):
                    continue
                key_txt = val.strip().upper()
                for k, code in labels.items():
                    if key_txt.startswith(k):
                        # tomar celda a la derecha
                        right_col = cell.column + 1
                        v = cell.parent.cell(row=cell.row, column=right_col).value
                        found[code] = _to_float(v)
        return found

    # ===== Helpers de datos =====
    def _find_uom(self, name):
        if not name:
            return self.default_uom_id
        UoM = self.env['uom.uom'].sudo()
        uom = UoM.search([('name', '=ilike', name)], limit=1)
        if not uom:
            # probar por abreviatura
            uom = UoM.search([('uom_type', 'in', ['bigger','reference','smaller']), ('name', 'ilike', name)], limit=1)
        return uom or self.default_uom_id

    def _get_or_create_product(self, name, uom):
        Product = self.env['product.product'].sudo()
        prod = Product.search([('name', '=ilike', name)], limit=1)
        if prod:
            return prod
        if not self.create_missing_products:
            raise UserError(_("El producto '%s' no existe y la opción de crear está desactivada.") % name)
        # Crear
        vals_tmpl = {
            'name': name,
            'type': self.default_product_type,
            'uom_id': uom.id if uom else False,
            'uom_po_id': uom.id if uom else False,
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        }
        # crear por product.template (product.product create hace template+variant)
        tmpl = self.env['product.template'].sudo().create(vals_tmpl)
        return tmpl.product_variant_id

    # ===== Proceso principal =====
    def action_import(self):
        if not self.purchase_id:
            raise UserError(_("Debes indicar la Orden de Compra."))
        if not self.file_data:
            raise UserError(_("Adjunta el archivo Excel."))
        if openpyxl is None:
            raise UserError(_("Falta la librería 'openpyxl'."))

        try:
            data = base64.b64decode(self.file_data)
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        except Exception as e:
            raise UserError(_("No se pudo leer el Excel: %s") % e)

        ws = self._get_ws(wb)
        product_lines = self._parse_table_lines(ws)
        surcharges = self._parse_surcharges(ws)

        if not product_lines:
            raise UserError(_("No se detectaron líneas de productos en el Excel."))

        PO = self.purchase_id.sudo()

        # limpiar líneas si corresponde
        if self.clear_existing_lines and PO.order_line:
            PO.order_line.unlink()

        # insertar líneas de productos
        created_count = 0
        amount_exworks_calc = 0.0

        for l in product_lines:
            uom = self._find_uom(l['uom'])
            prod = self._get_or_create_product(l['name'], uom)
            vals = {
                'order_id': PO.id,
                'product_id': prod.id,
                'name': l['name'],
                'product_qty': l['qty'],
                'price_unit': l['price'],
                'product_uom': (uom.id if uom else prod.uom_po_id.id),
                # impuestos: Odoo recalcula en confirmación; aquí no forzamos supplier_taxes_id
            }
            self.env['purchase.order.line'].sudo().create(vals)
            created_count += 1
            amount_exworks_calc += (l['qty'] * l['price'])

        # verificar IMPORTE EXWORK vs calculado (si vino)
        notes = []
        if 'exworks' in surcharges:
            if round(surcharges['exworks'], 2) != round(amount_exworks_calc, 2):
                notes.append(_("Aviso: IMPORTE EXWORK del Excel (%s) difiere del calculado (%s).") %
                             (surcharges['exworks'], amount_exworks_calc))

        # insertar servicios (1 unidad c/u)
        def _create_service_line(prod_field, amount, label_fallback):
            prod = getattr(self, prod_field)
            if amount is None:
                return
            if amount == 0:
                return
            if not prod:
                raise UserError(_("Falta configurar el %s para registrar el valor %s.")
                                % (label_fallback, amount))
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

        msg = _("Se importaron %s líneas de productos en la OC %s.") % (created_count, PO.name)
        if notes:
            msg += "\n" + "\n".join(notes)
        self.note = msg

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Importación completada'), 'message': msg, 'sticky': False}
        }
