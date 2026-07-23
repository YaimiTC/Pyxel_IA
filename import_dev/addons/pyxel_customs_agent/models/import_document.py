# -*- coding: utf-8 -*-
import base64 as _b64
import io
import json
import logging
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# field del DocValidator (res["fields"]) -> campo dm_* del documento
DM_FIELD_MAP = {
    'dm_number': 'dm_number',
    'dm_container': 'dm_container_number',
    'dm_cif': 'dm_cif_value',
    'dm_arancel': 'dm_arancel_total',
    'dm_impuesto_circulacion': 'dm_impuesto_circulacion',
    'dm_servicio_aduana': 'dm_servicio_aduana',
}
_NUMERIC = {'dm_cif_value', 'dm_arancel_total', 'dm_impuesto_circulacion', 'dm_servicio_aduana'}


class PyxelImportDocument(models.Model):
    _inherit = 'pyxel.import.document'

    # ----- Datos de la Declaración de Mercancía (DM) -----
    dm_number = fields.Char(string="Nº DM")
    dm_container_number = fields.Char(string="Contenedor")
    dm_currency_id = fields.Many2one(
        'res.currency', string="Moneda",
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))
    dm_cif_value = fields.Monetary(string="CIF (USD)", currency_field='dm_currency_id')
    dm_arancel_total = fields.Monetary(string="Aranceles (USD)", currency_field='dm_currency_id')
    dm_impuesto_circulacion = fields.Monetary(string="Imp. Circulación", currency_field='dm_currency_id')
    dm_servicio_aduana = fields.Monetary(string="Servicio de Aduana (MN)", currency_field='dm_currency_id')
    dm_arancel_notes = fields.Text(string="Notas arancelarias")
    dm_extraction_state = fields.Selection([
        ('pending', 'Sin DM'),
        ('extracted', 'Extraído por IA'),
        ('manual', 'Datos manuales'),
    ], default='pending', string="Extracción")
    dm_confirmed = fields.Boolean(string="Confirmado")

    def _extraer_texto_dm(self):
        """Extrae texto del PDF: primero intenta texto nativo, luego OCR.

        Usa modo "layout" (pypdf) cuando está disponible: en la DM cubana,
        el texto nativo sin layout separa cada palabra/número en su propia
        línea, sin relación entre una etiqueta de casilla y su valor — el
        modo layout preserva la alineación de columnas de la tabla, que es
        lo que permite anclar cada dato a su casilla real en
        _extraer_campos_dm() en vez de adivinar por cercanía de texto."""
        self.ensure_one()
        if not self.attachment_id:
            return ''
        try:
            import os
            try:
                from pypdf import PdfReader
                use_layout = True
            except ImportError:
                from PyPDF2 import PdfReader
                use_layout = False
            fname = self.attachment_id.store_fname
            if fname:
                fpath = os.path.join(self.env['ir.attachment']._filestore(), fname)
                with open(fpath, 'rb') as f:
                    raw = f.read()
            else:
                raw = _b64.b64decode(self.attachment_id.datas or '')

            reader = PdfReader(io.BytesIO(raw))
            text = ''
            for page in reader.pages:
                t = None
                if use_layout:
                    try:
                        t = page.extract_text(extraction_mode='layout')
                    except TypeError:
                        use_layout = False  # pypdf viejo sin ese parametro
                if t is None:
                    t = page.extract_text()
                text += (t or '')
            # Si el texto nativo es insuficiente, usar OCR
            if len(text.strip()) < 50:
                text = self._ocr_pdf(fpath if fname else None, raw if not fname else None)
            return text
        except Exception as e:
            _logger.warning("DM: no se pudo extraer texto: %s", e)
            return ''

    def _ocr_pdf(self, fpath=None, raw=None):
        """OCR sobre el PDF usando pdf2image + pytesseract."""
        try:
            from pdf2image import convert_from_path, convert_from_bytes
            import pytesseract
            if fpath:
                images = convert_from_path(fpath, dpi=250)
            else:
                images = convert_from_bytes(raw, dpi=250)
            text = ''
            for img in images:
                text += pytesseract.image_to_string(img, lang='spa+eng') + '\n'
            return text
        except Exception as e:
            _logger.warning("DM OCR falló: %s", e)
            return ''

    def _extraer_campos_dm(self, text):
        """Extrae Nº DM, CIF, Contenedor, Aranceles y Servicio de Aduana del
        texto de la DM cubana (Aduana General de la República de Cuba),
        anclando cada valor a su casilla real del formulario.

        No se puede usar "buscar la palabra clave más cercana": en este
        formulario "CIF" también aparece como incoterm (casilla 23), "DM"
        aparece en "No. int. DM" (casilla 66, un número de trámite interno
        distinto del Nº de declaración) y "Arancel"/"Servicio" tienen varias
        columnas numéricas en la misma fila (Base imponible, Tarifa,
        Importe a pagar MN/USD, Sacrificio fiscal MN/USD) — agarrar "el
        primer número después de la palabra" saca el dato equivocado con
        bastante frecuencia. En vez de eso, se localiza la etiqueta de cada
        casilla (ej. "54. Valor estadístico") y se lee el valor alineado
        debajo en la misma columna, usando el texto extraído en modo
        "layout" (ver _extraer_texto_dm) para que las columnas queden
        alineadas."""
        lines = text.split('\n')

        def por_casilla(label_pattern, lookahead=3, window=45, multi_token=False):
            for i, line in enumerate(lines):
                m = re.search(label_pattern, line, re.IGNORECASE)
                if not m:
                    continue
                col = m.start()
                for j in range(i + 1, min(i + 1 + lookahead, len(lines))):
                    seg = lines[j][max(0, col - 3):col + window]
                    if multi_token:
                        tok = re.search(r'\S.*?(?=  |$)', seg)
                    else:
                        tok = re.search(r'[\d][\d.,]{1,}|\S+', seg)
                    if tok:
                        return tok.group(0).strip()
            return None

        def importe_a_pagar_mn(row_label_pattern,
                                header_pattern=r'32\.\s*Importe\s+a\s+pagar'):
            """Valor en MN de la fila indicada, bajo la casilla 32 "Importe a
            pagar" — NO la 33 "Sacrificio fiscal" (el monto exonerado/
            informativo cuando hay estímulo fiscal, distinto de lo que
            realmente se paga)."""
            for i, line in enumerate(lines):
                if not re.search(header_pattern, line, re.IGNORECASE):
                    continue
                sub = lines[i + 1] if i + 1 < len(lines) else ''
                mm = re.search(r'\bMN\b', sub)
                if not mm:
                    continue
                mn_col = mm.start()
                for j in range(i + 1, len(lines)):
                    if re.search(row_label_pattern, lines[j], re.IGNORECASE):
                        seg = lines[j][max(0, mn_col - 5):mn_col + 15]
                        tok = re.search(r'[\d][\d.,]*', seg)
                        if tok:
                            return tok.group(0).strip()
                break
            return None

        vals = {}

        dm_number = por_casilla(r'2\.\s*No\.\s*de\s*declaraci[oó]n')
        if dm_number:
            vals['dm_number'] = dm_number[:64]

        cif = por_casilla(r'54\.\s*Valor\s+estad[ií]stico')
        if cif is not None:
            num = self._dm_to_float(cif)
            if num is not None:
                vals['dm_cif_value'] = num

        container = por_casilla(r'Contenedores\s+siglas', multi_token=True)
        if container:
            vals['dm_container_number'] = container.upper().replace(' ', '')[:32]

        arancel = importe_a_pagar_mn(r'Arancel\b')
        if arancel is not None:
            num = self._dm_to_float(arancel)
            if num is not None:
                vals['dm_arancel_total'] = num

        servicio = importe_a_pagar_mn(r'Servicio\s+de\s+aduana')
        if servicio is not None:
            num = self._dm_to_float(servicio)
            if num is not None:
                vals['dm_servicio_aduana'] = num

        # Respaldo mínimo si el layout no calzó (variante de formato
        # distinta a la esperada). No hay respaldo para Aranceles: la
        # heurística vieja (mayor número tras la palabra "Arancel") termina
        # leyendo la columna "Sacrificio fiscal" en vez de "Importe a
        # pagar" cuando hay exoneración — mejor dejarlo en blanco para
        # entrada manual que guardar un monto que no es el que se paga.
        if 'dm_number' not in vals:
            m = re.search(r'No\.\s+de\s+declaraci[oó]n[^\n]*\n\s*(\d{4,10})', text, re.IGNORECASE)
            if m:
                vals['dm_number'] = m.group(1).strip()[:64]
        if 'dm_cif_value' not in vals:
            m = re.search(r'Valor\s+estad[ií]stico[^\d]*([\d.,]+)', text, re.IGNORECASE)
            if m:
                num = self._dm_to_float(m.group(1))
                if num is not None:
                    vals['dm_cif_value'] = num

        return vals

    # Al correr la IA sobre una DM, además del veredicto, vuelca los campos extraídos.
    def _run_ai(self):
        super()._run_ai()
        for d in self:
            if d.document_key != 'dm':
                continue
            # El parser propio (_extraer_campos_dm) va PRIMERO: está anclado
            # a las casillas reales del formulario cubano. DocValidator es
            # un validador genérico multi-documento (BL, factura, lista de
            # empaque...) sin ese conocimiento específico de la DM cubana,
            # así que sus campos solo se usan para completar lo que el
            # parser propio no encontró — antes era al revés (todo-o-nada:
            # si DocValidator devolvía CUALQUIER campo, aunque viniera mal,
            # el parser propio ni se ejecutaba).
            vals = {}
            text = d._extraer_texto_dm()
            if text:
                vals = d._extraer_campos_dm(text)
            try:
                data = json.loads(d.ai_extracted_data or '{}')
            except Exception:
                data = {}
            if isinstance(data, dict):
                for src, dst in DM_FIELD_MAP.items():
                    if dst in vals:
                        continue
                    raw = data.get(src)
                    if not raw:
                        continue
                    if dst in _NUMERIC:
                        num = self._dm_to_float(raw)
                        if num is not None:
                            vals[dst] = num
                    elif dst == 'dm_container_number':
                        vals[dst] = str(raw).upper().replace(' ', '')[:32]
                    else:
                        vals[dst] = str(raw)[:64]
            vals['dm_extraction_state'] = 'extracted' if vals else 'manual'
            d.with_context(skip_ai=True).write(vals)

    @staticmethod
    def _dm_to_float(raw):
        s = str(raw).strip().replace(' ', '')
        if not s:
            return None
        if ',' in s and '.' in s:
            s = s.replace(',', '')          # coma = separador de miles
        elif ',' in s:
            s = s.replace(',', '.')          # coma decimal
        try:
            return float(s)
        except ValueError:
            return None

    # ----- Validación de la DM contra los datos del proceso -----
    def _validar_dm(self):
        """Valida que el PDF DM coincida con los datos del proceso.

        Devuelve {'graves': [...], 'informativas': [...]} (alertas en HTML) y
        publica el detalle en el chatter del proceso.

        'graves' = indicios de que la DM subida NO corresponde a esta
        operación (cliente/proveedor/BL/contenedor no coinciden con el
        texto de la DM) — action_dm_confirm() bloquea la confirmación si
        hay alguna. 'informativas' = avisos que no bloquean (apoderado no
        mencionado, líneas de costo faltantes, o datos de la propia
        importación incompletos y por tanto no verificables)."""
        self.ensure_one()
        imp = self.importation_id
        graves = []
        informativas = []

        text = self._extraer_texto_dm()
        _logger.info("DM _validar_dm: texto extraído %d chars | primeros 500: %s", len(text), text[:500])

        if not text:
            msg = 'No se pudo leer el texto del PDF. Verifique manualmente.'
            imp.message_post(
                body='<b>&#9888; DM:</b> ' + msg,
                subtype_xmlid='mail.mt_note')
            return {'graves': [], 'informativas': ['<b>&#9888; DM:</b> ' + msg]}

        # 1. Cliente — esta DM pertenece a UNA orden de compra (self.purchase_order_id);
        # en un proceso multi-cliente cada OC tiene su propio cliente (casilla 13
        # "comprador" de esta DM en particular), así que se valida contra el
        # cliente de la OC, no contra todos los clientes del proceso — si no,
        # un proceso con 2 clientes marcaría "no encontrado" al cliente ajeno
        # a esta DM en cada una de las dos.
        po_customer = self.purchase_order_id.customer_id if 'customer_id' in self.purchase_order_id._fields else False
        cliente = po_customer or imp.customer_id
        if cliente:
            name = cliente.name or ''
            vat = cliente.vat or ''
            if name and name not in text and (not vat or vat not in text):
                graves.append('Cliente <b>%s</b> no encontrado en la DM.' % name)

        # 2. Proveedor
        if imp.provider_id:
            name = imp.provider_id.name or ''
            vat = imp.provider_id.vat or ''
            if name and name not in text and (not vat or vat not in text):
                graves.append('Proveedor <b>%s</b> no encontrado en la DM.' % name)

        # 3. Apoderado (usuario del sistema) — no bloquea: puede aparecer con
        # otro nombre (declarante distinto del apoderado asignado en Odoo)
        # sin que la DM sea de otra operación.
        agent = imp.en_customs_agent_id if hasattr(imp, 'en_customs_agent_id') else False
        if agent and agent.name and agent.name not in text:
            informativas.append('Apoderado <b>%s</b> no encontrado en la DM.' % agent.name)

        # 4. BL / referencia
        bl = imp.purchase_condition_number or ''
        if not bl:
            informativas.append('No hay número de BL/referencia registrado en la importación.')
        elif bl not in text:
            graves.append('BL/referencia <b>%s</b> no encontrado en la DM.' % bl)

        # 5. Contenedor — el BL y la DM suelen formatear el mismo contenedor
        # distinto (ej. "CXTU1086819" en el BL vs "CXTU 108681-9" en la DM),
        # así que se compara solo por caracteres alfanuméricos.
        loads = self.env['importation.load'].search([('importation_id', '=', imp.id)])
        containers = [l.name for l in loads if l.name]
        text_alnum = re.sub(r'[^A-Za-z0-9]', '', text).upper()
        if not containers:
            informativas.append('No hay contenedores registrados en la importación.')
        elif not any(re.sub(r'[^A-Za-z0-9]', '', c).upper() in text_alnum for c in containers):
            graves.append('Ningún contenedor (%s) encontrado en la DM.' % ', '.join(containers))

        # 6. Líneas de costo: Arancel y Servicio de Aduana (no bloquea: es un
        # dato de la importación, no una señal de que la DM esté cambiada)
        cost_lines = imp.cost_line_ids if hasattr(imp, 'cost_line_ids') else []
        has_arancel = any('arancel' in (l.product_id.name or '').lower() for l in cost_lines)
        has_servicio = any('aduana' in (l.product_id.name or '').lower() for l in cost_lines)
        if not has_arancel:
            informativas.append('No existe línea de costo <b>Arancel</b> en la importación.')
        if not has_servicio:
            informativas.append('No existe línea de costo <b>Servicio de Aduana</b> en la importación.')

        _logger.info("DM _validar_dm: %d graves, %d informativas: %s | %s",
                     len(graves), len(informativas), graves, informativas)
        todas = graves + informativas
        if todas:
            body = '<b>Alertas al confirmar DM:</b><ul>' + \
                   ''.join('<li>%s</li>' % w for w in todas) + '</ul>'
            imp.message_post(body=body, subtype_xmlid='mail.mt_note')
        return {'graves': graves, 'informativas': informativas}

    # ----- Acciones del apoderado -----
    @staticmethod
    def _plain(html_list):
        return [w.replace('<b>', '').replace('</b>', '').replace('<br/>', ' ') for w in html_list]

    def action_dm_confirm(self):
        # Se valida TODO antes de escribir nada: si alguna DM tiene
        # discrepancias graves (cliente/proveedor/BL/contenedor no
        # coinciden — indicio de que es la DM de OTRA operación), se
        # bloquea la confirmación de esa DM sin marcar dm_confirmed.
        resultados = []
        for d in self:
            if d.document_key != 'dm':
                continue
            if not d.attachment_id:
                raise UserError(_("Sube el PDF de la DM antes de confirmarla."))
            resultados.append((d, d._validar_dm()))

        bloqueadas = [(d, r) for d, r in resultados if r['graves']]
        if bloqueadas:
            detalle = '\n\n'.join(
                '%s:\n%s' % (
                    d.purchase_order_id.display_name or d.document_label,
                    '\n'.join('- ' + w for w in self._plain(r['graves'])))
                for d, r in bloqueadas)
            raise UserError(_(
                "No se puede confirmar: esta DM no parece corresponder a esta "
                "operación.\n\n%s\n\nVerifique que subió el PDF correcto — si "
                "es el equivocado, use «Reemplazar» y suba el que corresponde."
            ) % detalle)

        all_informativas = []
        for d, r in resultados:
            d.write({'dm_confirmed': True})
            all_informativas.extend(r['informativas'])
        if all_informativas:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Avisos en la DM',
                    'message': '\n'.join(self._plain(all_informativas)),
                    'type': 'warning',
                    'sticky': True,
                },
            }
        return True

    def action_dm_replace(self):
        """Limpia el PDF y todos los datos extraídos para subir uno nuevo."""
        self.write({
            'attachment_id': False,
            'ai_state': 'pending',
            'commercial_state': 'blocked',
            'dm_extraction_state': 'pending',
            'dm_number': False,
            'dm_cif_value': 0.0,
            'dm_arancel_total': 0.0,
            'dm_servicio_aduana': 0.0,
            'dm_confirmed': False,
        })
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_dm_reopen(self):
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Solo un administrador puede revertir una DM confirmada."))
        self.write({'dm_confirmed': False})
