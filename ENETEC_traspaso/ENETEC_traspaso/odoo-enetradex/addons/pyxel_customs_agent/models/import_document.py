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
        """Extrae texto del PDF: primero intenta texto nativo, luego OCR."""
        self.ensure_one()
        if not self.attachment_id:
            return ''
        try:
            import os, PyPDF2
            fname = self.attachment_id.store_fname
            if fname:
                fpath = os.path.join(self.env['ir.attachment']._filestore(), fname)
                with open(fpath, 'rb') as f:
                    raw = f.read()
            else:
                raw = _b64.b64decode(self.attachment_id.datas or '')

            # Intentar texto nativo
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(raw))
                pages = reader.pages
            except AttributeError:
                reader = PyPDF2.PdfFileReader(io.BytesIO(raw))
                pages = [reader.getPage(i) for i in range(reader.numPages)]
            text = ''
            for page in pages:
                try:
                    t = page.extract_text()
                except AttributeError:
                    t = page.extractText()
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
        """Extrae Nº DM, CIF, Aranceles y Servicio de Aduana del texto OCR del DM cubano."""
        vals = {}

        # Nº DM — escaque 2: número en la línea siguiente a "declaración" (o cerca)
        for pat in [
            r'No\.\s+de\s+declaraci[oó]n[^\n]*\n\s*(\d{4,10})',
            r'declaraci[oó]n[^\n]*\n\s*(\d{4,10})',
            r'No\.\s+de\s+declaraci[oó]n\s+(\d{4,10})',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                vals['dm_number'] = m.group(1).strip()[:64]
                break
        # Fallback: primer número de 5 dígitos en el primer cuarto del texto
        if 'dm_number' not in vals:
            m = re.search(r'\b(\d{5})\b', text[:max(1, len(text)//4)])
            if m:
                vals['dm_number'] = m.group(1)

        # CIF y Arancel — fila de cálculo:
        #   "Arancel [1|$|€] <CIF_USD> <tarifa%> [0.00] <arancel_MN> [0.00...]"
        # El OCR puede leer "Arancel" como "[arancel", "Arancel", etc.
        # Buscamos la fila con más números significativos para extraer CIF (menor) y Arancel (mayor).
        cif_found = arancel_found = False
        for m in re.finditer(r'\bArancel\b([^\n]*)', text, re.IGNORECASE):
            nums_raw = re.findall(
                r'[\d]{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?|[\d]{5,}', m.group(1))
            floats = sorted(
                [f for f in (self._dm_to_float(n) for n in nums_raw) if f and f > 100],
                reverse=True)
            if len(floats) >= 2:
                # mayor = arancel en MN, menor = CIF en USD
                vals.setdefault('dm_arancel_total', floats[0])
                vals.setdefault('dm_cif_value', floats[-1])
                arancel_found = cif_found = True
                break

        # Arancel fallback (línea tipo "Aranceles 135,840.00")
        if not arancel_found:
            for pat in [r'[Aa]rancel(?:es)?[:\s]+([\d.,]+)',
                        r'Derechos\s+arancelarios[:\s]*([\d.,]+)']:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    num = self._dm_to_float(m.group(1))
                    if num and num > 100:
                        vals['dm_arancel_total'] = num
                        break

        # CIF fallback
        if not cif_found:
            for pat in [r'54\.\s*Valor\s+en\s+aduana[^\d]*([\d.,]+)',
                        r'Valor\s+en\s+aduana[^\d]*([\d.,]+)',
                        r'Valor\s+CIF[^\d]*([\d.,]+)']:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    num = self._dm_to_float(m.group(1))
                    if num:
                        vals['dm_cif_value'] = num
                        break

        # Servicio de Aduana — fila: "Servicio ... <importe> 0.00"
        m = re.search(r'[Ss]ervicio[^\n]{0,80}([\d.,]{4,})\s+0[.,]0', text)
        if not m:
            m = re.search(r'[Ss]ervicio[^\n]*\n[^\n]*([\d.,]{4,})\s+0[.,]0', text)
        if m:
            num = self._dm_to_float(m.group(1))
            if num:
                vals['dm_servicio_aduana'] = num

        return vals

    # Al correr la IA sobre una DM, además del veredicto, vuelca los campos extraídos.
    def _run_ai(self):
        super()._run_ai()
        for d in self:
            if d.document_key != 'dm':
                continue
            vals = {}
            # Intentar primero desde los datos de la IA
            try:
                data = json.loads(d.ai_extracted_data or '{}')
            except Exception:
                data = {}
            if isinstance(data, dict):
                for src, dst in DM_FIELD_MAP.items():
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
            # Fallback: extraer del texto del PDF si la IA no devolvió datos
            if not vals:
                text = d._extraer_texto_dm()
                if text:
                    vals = d._extraer_campos_dm(text)
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
        Devuelve lista de alertas HTML y publica en el chatter del proceso."""
        self.ensure_one()
        imp = self.importation_id
        warnings = []

        text = self._extraer_texto_dm()
        _logger.info("DM _validar_dm: texto extraído %d chars | primeros 500: %s", len(text), text[:500])

        if not text:
            msg = 'No se pudo leer el texto del PDF. Verifique manualmente.'
            imp.message_post(
                body='<b>&#9888; DM:</b> ' + msg,
                subtype_xmlid='mail.mt_note')
            return ['<b>&#9888; DM:</b> ' + msg]

        # 1. Cliente
        if imp.customer_id:
            name = imp.customer_id.name or ''
            vat = imp.customer_id.vat or ''
            if name and name not in text and (not vat or vat not in text):
                warnings.append('Cliente <b>%s</b> no encontrado en la DM.' % name)

        # 2. Proveedor
        if imp.provider_id:
            name = imp.provider_id.name or ''
            vat = imp.provider_id.vat or ''
            if name and name not in text and (not vat or vat not in text):
                warnings.append('Proveedor <b>%s</b> no encontrado en la DM.' % name)

        # 3. Apoderado (usuario del sistema)
        agent = imp.en_customs_agent_id if hasattr(imp, 'en_customs_agent_id') else False
        if agent and agent.name and agent.name not in text:
            warnings.append('Apoderado <b>%s</b> no encontrado en la DM.' % agent.name)

        # 4. BL / referencia
        bl = imp.purchase_condition_number or ''
        if not bl:
            warnings.append('No hay número de BL/referencia registrado en la importación.')
        elif bl not in text:
            warnings.append('BL/referencia <b>%s</b> no encontrado en la DM.' % bl)

        # 5. Contenedor
        loads = self.env['importation.load'].search([('importation_id', '=', imp.id)])
        containers = [l.name for l in loads if l.name]
        if not containers:
            warnings.append('No hay contenedores registrados en la importación.')
        elif not any(c in text for c in containers):
            warnings.append('Ningún contenedor (%s) encontrado en la DM.' % ', '.join(containers))

        # 6. Líneas de costo: Arancel y Servicio de Aduana
        cost_lines = imp.cost_line_ids if hasattr(imp, 'cost_line_ids') else []
        has_arancel = any('arancel' in (l.product_id.name or '').lower() for l in cost_lines)
        has_servicio = any('aduana' in (l.product_id.name or '').lower() for l in cost_lines)
        if not has_arancel:
            warnings.append('No existe línea de costo <b>Arancel</b> en la importación.')
        if not has_servicio:
            warnings.append('No existe línea de costo <b>Servicio de Aduana</b> en la importación.')

        _logger.info("DM _validar_dm: %d alertas: %s", len(warnings), warnings)
        if warnings:
            body = '<b>Alertas al confirmar DM:</b><ul>' + \
                   ''.join('<li>%s</li>' % w for w in warnings) + '</ul>'
            imp.message_post(body=body, subtype_xmlid='mail.mt_note')
        return warnings

    # ----- Acciones del apoderado -----
    def action_dm_confirm(self):
        all_warnings = []
        for d in self:
            if d.document_key != 'dm':
                continue
            if not d.attachment_id:
                raise UserError(_("Sube el PDF de la DM antes de confirmarla."))
            all_warnings.extend(d._validar_dm())
            d.write({'dm_confirmed': True})
        if all_warnings:
            plain = '\n'.join(
                w.replace('<b>', '').replace('</b>', '').replace('<br/>', ' ')
                for w in all_warnings
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Alertas en la DM',
                    'message': plain,
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
