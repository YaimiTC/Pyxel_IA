# -*- coding: utf-8 -*-
import base64
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .lead_document import DOC_CATALOG, LABEL_TO_DOCVAL, VERDICT_MAP

_logger = logging.getLogger(__name__)

DOCVAL_URL = "http://localhost:8800"


class CrmLeadCreateWizard(models.TransientModel):
    _name = 'crm.lead.create.wizard'
    _description = 'Asistente de acreditación (backend)'

    step = fields.Selection([
        ('rol', 'Rol'),
        ('datos', 'Mis datos'),
        ('docs', 'Documentos'),
        ('solicitud', 'Solicitud'),
        ('proveedor', 'Proveedor'),
        ('resumen', 'Resumen'),
    ], default='rol', required=True)

    # ── Paso ROL ─────────────────────────────────────────────────────────────
    en_party_role = fields.Selection(
        [('client', 'Cliente'), ('supplier', 'Proveedor')],
        string="Tipo de empresa")

    # ── Paso DATOS (Mis datos) ────────────────────────────────────────────────
    # Tipo de entidad — solo para clientes
    client_type = fields.Selection([
        ('Pymes', 'Pyme · 5 docs'),
        ('Estatal', 'Estatal · 4 docs'),
        ('CNA', 'CNA · 7 docs'),
        ('Sucursal Extranjera', 'Sucursal Extranjera · 7 docs'),
    ], string="Tipo de entidad")

    # Clasificación del proveedor — solo para proveedores
    supplier_class = fields.Selection([
        ('Productor', 'Productor'),
        ('Comerciante', 'Comerciante'),
    ], string="Clasificación del proveedor")

    company_name = fields.Char(string="Nombre de la empresa")
    company_vat = fields.Char(string="NIT")
    company_street = fields.Char(string="Dirección")
    company_state_id = fields.Many2one('res.country.state', string="Provincia",
                                       domain="[('country_id.code', '=', 'CU')]")
    company_city_id = fields.Many2one('res.city', string="Municipio",
                                      domain="[('state_id', '=?', company_state_id)]")

    @api.onchange('company_state_id')
    def _onchange_company_state_id(self):
        # Al cambiar la provincia, limpiar el municipio si ya no pertenece a ella.
        if self.company_city_id and self.company_city_id.state_id != self.company_state_id:
            self.company_city_id = False

    @api.onchange('company_vat')
    def _onchange_company_vat_check_length(self):
        # El NIT solo aplica a clientes (los proveedores usan código MINCEX,
        # no NIT — ver company_mincex/license_holder).
        v = (self.company_vat or '').strip()
        if v and (not v.isdigit() or len(v) != 11):
            return {'warning': {
                'title': _("NIT inválido"),
                'message': _("El NIT debe tener exactamente 11 dígitos numéricos."),
            }}
    company_country_id = fields.Many2one('res.country', string="País")
    company_mincex = fields.Char(string="Código MINCEX")
    company_req_mincex = fields.Boolean(string="¿Requiere código MINCEX?")
    company_objeto = fields.Text(string="Objeto social")

    # Datos del contacto
    contact_name = fields.Char(string="Nombre y apellido del contacto")
    company_email = fields.Char(string="Correo electrónico")
    company_phone = fields.Char(string="Teléfono")

    # Visibilidad (como el front)
    visible_to_providers = fields.Boolean(string="Mis datos pueden ser visibles para proveedores")
    visible_to_clients = fields.Boolean(string="Mis datos pueden ser visibles para clientes")

    # ¿Tiene solicitud? — visible solo para clientes al final del paso datos
    has_solicitud = fields.Boolean(string="¿Tiene una solicitud de importación para registrar?")

    # ── Paso DOCS ─────────────────────────────────────────────────────────────
    doc_line_ids = fields.One2many('crm.lead.wizard.doc', 'wizard_id', string="Documentos")

    # ── Paso SOLICITUD ────────────────────────────────────────────────────────
    sol_product = fields.Selection([
        ('Diésel', 'Diésel'), ('Gasolina', 'Gasolina'), ('Jet A-1', 'Jet A-1'),
        ('Fuel oíl', 'Fuel oíl'), ('GLP', 'GLP'),
    ], string="Producto", default='Diésel')
    sol_qty = fields.Float(string="Cantidad")
    sol_env = fields.Selection([
        ('isotanque', 'Isotanque'), ('isomodulo', 'Isomódulo'),
    ], string="Tipo de envase", default='isotanque')
    sol_delivery = fields.Date(string="Fecha de entrega deseada")
    sol_budget = fields.Float(string="Presupuesto disponible (USD)")
    sol_specs = fields.Text(string="Especificaciones técnicas")
    sol_obs = fields.Text(string="Observaciones")

    # ── Paso PROVEEDOR ────────────────────────────────────────────────────────
    cp_mode = fields.Selection([
        ('cartera', 'Ya tengo un proveedor (mi cartera)'),
        ('nuevo', 'Acreditar nuevo proveedor'),
        ('cotiza', 'Que me coticen (ENETEC — pliego de concurrencia)'),
    ], string="¿Cómo eliges el proveedor?", default='cartera')

    cp_partner_id = fields.Many2one('res.partner', string="Proveedor de mi cartera",
                                    domain="[('supplier_rank','>',0)]")
    cp_name = fields.Char(string="Nombre de la empresa")
    cp_country_id = fields.Many2one('res.country', string="País")
    cp_mincex = fields.Char(string="Código MINCEX")
    cp_contact_name = fields.Char(string="Nombre del contacto")
    cp_contact_email = fields.Char(string="Correo electrónico")
    cp_contact_phone = fields.Char(string="Teléfono")
    cp_accredit = fields.Boolean(string="Acreditar también a este proveedor", default=True)

    # ── Resumen (computed) ────────────────────────────────────────────────────
    summary_html = fields.Html(
        string="Resumen", compute='_compute_summary_html', sanitize=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Navegación de pasos
    # ─────────────────────────────────────────────────────────────────────────

    def _next_step(self):
        cur = self.step
        is_client = self.en_party_role == 'client'
        if cur == 'rol':
            return 'datos'
        elif cur == 'datos':
            return 'docs'
        elif cur == 'docs':
            if is_client and self.has_solicitud:
                return 'solicitud'
            return 'resumen'
        elif cur == 'solicitud':
            return 'proveedor'
        elif cur == 'proveedor':
            return 'resumen'
        return 'resumen'

    def _prev_step(self):
        cur = self.step
        is_client = self.en_party_role == 'client'
        if cur == 'datos':
            return 'rol'
        elif cur == 'docs':
            return 'datos'
        elif cur == 'solicitud':
            return 'docs'
        elif cur == 'proveedor':
            return 'solicitud'
        elif cur == 'resumen':
            if is_client and self.has_solicitud:
                return 'proveedor'
            return 'docs'
        return 'rol'

    def _action_self(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_next(self):
        self.ensure_one()
        if self.step == 'rol':
            if not self.en_party_role:
                raise UserError(_("Selecciona el tipo de empresa (Cliente o Proveedor)."))
        elif self.step == 'datos':
            if not self.company_name:
                raise UserError(_("El nombre de la empresa es obligatorio."))
            if self.en_party_role == 'client' and not self.client_type:
                raise UserError(_("Selecciona el tipo de entidad."))
        elif self.step == 'solicitud':
            if not self.sol_budget:
                raise UserError(_("Indica el presupuesto disponible para continuar."))
        elif self.step == 'proveedor':
            if self.cp_mode == 'cartera' and not self.cp_partner_id:
                raise UserError(_("Selecciona un proveedor de tu cartera."))
            if self.cp_mode == 'nuevo' and not self.cp_name:
                raise UserError(_("Indica el nombre del nuevo proveedor."))

        next_step = self._next_step()

        # Inicializar documentos al entrar al paso docs
        if next_step == 'docs' and not self.doc_line_ids:
            self._init_doc_lines()

        self.step = next_step
        return self._action_self()

    def action_back(self):
        self.ensure_one()
        self.step = self._prev_step()
        return self._action_self()

    def _init_doc_lines(self):
        """Crea los registros de documento según el tipo de entidad."""
        # Determinar la clave del catálogo
        cat_key = self.client_type if self.en_party_role == 'client' else 'Proveedor'
        catalog = DOC_CATALOG.get(cat_key, [])
        WzDoc = self.env['crm.lead.wizard.doc']
        for key, label, required in catalog:
            WzDoc.create({
                'wizard_id': self.id,
                'doc_key': key,
                'doc_label': label,
                'is_required': required,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # Resumen
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('company_name', 'company_vat', 'en_party_role', 'client_type',
                 'contact_name', 'company_email', 'company_phone',
                 'doc_line_ids', 'doc_line_ids.ai_state', 'doc_line_ids.attachment_id',
                 'has_solicitud', 'sol_product', 'sol_qty', 'sol_budget',
                 'cp_mode', 'cp_partner_id', 'cp_name')
    def _compute_summary_html(self):
        role_lbl = {'client': 'Cliente', 'supplier': 'Proveedor'}
        ctype_lbl = {
            'Pymes': 'Pyme', 'Estatal': 'Estatal',
            'CNA': 'CNA', 'Sucursal Extranjera': 'Sucursal Extranjera',
        }
        st_color = {
            'passed': '#16a34a', 'doubt': '#a8650c', 'rejected': '#d33a4b',
            'validating': '#0f44ce', 'unavailable': '#5b6b85',
        }
        st_lbl = {
            'passed': 'Apto', 'doubt': 'Dudoso', 'rejected': 'No apto',
            'validating': 'Validando…', 'unavailable': 'Sin IA',
        }
        cp_mode_lbl = {
            'cartera': 'Cartera', 'nuevo': 'Acreditar nuevo',
            'cotiza': 'Que me coticen (ENETEC)',
        }

        def row(k, v):
            return (f'<div style="display:flex;justify-content:space-between;'
                    f'padding:5px 0;border-bottom:1px solid #e3e9f2;font-size:12.5px">'
                    f'<span style="color:#5b6b85">{k}</span>'
                    f'<span style="font-weight:500;text-align:right;max-width:60%">{v}</span>'
                    f'</div>')

        def section(title, content):
            return (f'<div style="background:#f6f8fc;border-radius:8px;'
                    f'padding:12px;margin-bottom:12px">'
                    f'<div style="font-weight:500;margin-bottom:8px;font-size:13px">{title}</div>'
                    f'{content}</div>')

        for wz in self:
            docs = wz.doc_line_ids
            total = len(docs)
            uploaded = len(docs.filtered(lambda d: d.attachment_id))

            h = '<div style="font-family:system-ui;font-size:13px">'
            h += '<div style="font-weight:600;font-size:15px;margin-bottom:12px">Resumen de acreditación</div>'

            # Empresa
            role_str = role_lbl.get(wz.en_party_role, '—')
            ctype_str = ctype_lbl.get(wz.client_type, wz.client_type or '') if wz.en_party_role == 'client' else ''
            tipo_display = f'{role_str} · {ctype_str}' if ctype_str else role_str
            empresa_rows = (
                row('Tipo', tipo_display) +
                row('Empresa', wz.company_name or '—') +
                row('NIT', wz.company_vat or '—') +
                row('Contacto', wz.contact_name or '—') +
                row('Correo', wz.company_email or '—') +
                row('Teléfono', wz.company_phone or '—')
            )
            h += section('Empresa', empresa_rows)

            # Solicitud
            if wz.has_solicitud:
                env_lbl = dict(wz._fields['sol_env'].selection).get(wz.sol_env, '—')
                sol_rows = (
                    row('Producto', wz.sol_product or '—') +
                    row('Cantidad', f"{wz.sol_qty} ({env_lbl})" if wz.sol_qty else '—') +
                    row('Entrega', str(wz.sol_delivery) if wz.sol_delivery else '—') +
                    row('Presupuesto (USD)', f"${wz.sol_budget:,.2f}" if wz.sol_budget else '—')
                )
                if wz.sol_obs:
                    sol_rows += row('Observaciones', wz.sol_obs)
                h += section('Solicitud de importación', sol_rows)

                # Proveedor
                cp_desc = cp_mode_lbl.get(wz.cp_mode, '—')
                if wz.cp_mode == 'cartera' and wz.cp_partner_id:
                    cp_desc += f' · {wz.cp_partner_id.name}'
                elif wz.cp_mode == 'nuevo' and wz.cp_name:
                    cp_desc += f' · {wz.cp_name}'
                h += section('Proveedor', row('Selección', cp_desc))

            # Documentos
            doc_rows = ''
            for doc in docs:
                icon = '✓ ' if doc.attachment_id else '○ '
                req = '' if doc.is_required else ' <span style="color:#5b6b85;font-size:11px">(opcional)</span>'
                right = ''
                if doc.attachment_id and doc.ai_state:
                    color = st_color.get(doc.ai_state, '#5b6b85')
                    conf = f' {int(doc.ai_confidence)}%' if doc.ai_confidence else ''
                    right = f'<span style="color:{color};font-size:11px;font-weight:500">{st_lbl.get(doc.ai_state, doc.ai_state)}{conf}</span>'
                elif doc.attachment_id:
                    right = '<span style="color:#16a34a;font-size:11px">Subido</span>'
                else:
                    right = '<span style="color:#5b6b85;font-size:11px">Sin subir</span>'
                doc_rows += (
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:5px 0;border-bottom:1px solid #e3e9f2;font-size:12.5px">'
                    f'<span>{icon}{doc.doc_label}{req}</span>{right}</div>'
                )
            h += section(f'Documentos ({uploaded}/{total} subidos)', doc_rows or '<span style="color:#5b6b85">Sin documentos</span>')

            h += '</div>'
            wz.summary_html = h

    # ─────────────────────────────────────────────────────────────────────────
    # Confirmar acreditación
    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_contact_type(self, role, country):
        """Tipo de contacto (res.partner.contact.type) según el rol
        (client/supplier) y si el país es Cuba (nacional) o no (extranjero).
        Sin esto, el partner queda sin contact_type_id y luego no se puede
        aprobar la oportunidad (falla en crm_lead.write, pyxel_import_backend)."""
        is_national = bool(country) and country.code == 'CU'
        if role == 'client':
            xml_id = ('pyxel_import_backend.res_partner_contact_type_client' if is_national
                      else 'pyxel_import_backend.res_partner_contact_type_foreign_client')
        else:
            xml_id = ('pyxel_import_backend.res_partner_contact_type_supplier' if is_national
                      else 'pyxel_import_backend.res_partner_contact_type_foreign_supplier')
        return self.env.ref(xml_id, raise_if_not_found=False)

    def action_confirm(self):
        self.ensure_one()

        # 1. Buscar partner existente por NIT (cliente) o código MINCEX
        # (proveedor) — cada rol usa un identificador distinto, no ambos.
        partner = False
        if self.en_party_role == 'client' and self.company_vat:
            partner = self.env['res.partner'].search(
                [('vat', '=', self.company_vat)], limit=1)
        elif self.en_party_role == 'supplier' and self.company_mincex:
            partner = self.env['res.partner'].search(
                [('license_holder', '=', self.company_mincex)], limit=1)
        if partner and not partner.contact_type_id:
            # Respaldo: contacto pre-existente que quedó sin tipo de contacto
            # (por este mismo bug en una carga anterior) — se completa ahora
            # para no dejar la oportunidad bloqueada al intentar aprobarla.
            ct = self._resolve_contact_type(self.en_party_role, self.company_country_id or partner.country_id)
            if ct:
                partner.contact_type_id = ct.id
        if not partner:
            vals = {
                'name': self.company_name,
                'is_company': True,
                'customer_rank': 1 if self.en_party_role == 'client' else 0,
                'supplier_rank': 1 if self.en_party_role == 'supplier' else 0,
            }
            ct = self._resolve_contact_type(self.en_party_role, self.company_country_id)
            if ct:
                vals['contact_type_id'] = ct.id
            # NIT solo aplica a clientes; el proveedor se identifica por
            # código MINCEX (license_holder), no por vat.
            if self.en_party_role == 'client' and self.company_vat:
                vals['vat'] = self.company_vat
            if self.en_party_role == 'supplier' and self.company_mincex:
                vals['license_holder'] = self.company_mincex
                vals['en_requiere_mincex'] = bool(self.company_req_mincex)
            for f, v in [
                ('street', self.company_street),
                ('email', self.company_email),
                ('phone', self.company_phone), ('objeto_social', self.company_objeto),
            ]:
                if v:
                    vals[f] = v
            if self.company_city_id:
                vals['city_id'] = self.company_city_id.id
                vals['city'] = self.company_city_id.name
            if self.company_state_id:
                vals['state_id'] = self.company_state_id.id
            if self.company_country_id:
                vals['country_id'] = self.company_country_id.id
            partner = self.env['res.partner'].create(vals)

        # 2. Si hay proveedor nuevo, crearlo
        cp_partner = self.cp_partner_id
        if self.has_solicitud and self.cp_mode == 'nuevo' and self.cp_name:
            cp_vals = {'name': self.cp_name, 'is_company': True, 'supplier_rank': 1}
            ct = self._resolve_contact_type('supplier', self.cp_country_id)
            if ct:
                cp_vals['contact_type_id'] = ct.id
            if self.cp_mincex:
                cp_vals['license_holder'] = self.cp_mincex
            if self.cp_country_id:
                cp_vals['country_id'] = self.cp_country_id.id
            if self.cp_contact_email:
                cp_vals['email'] = self.cp_contact_email
            if self.cp_contact_phone:
                cp_vals['phone'] = self.cp_contact_phone
            cp_partner = self.env['res.partner'].create(cp_vals)

        # 3. Crear lead CRM
        lead_vals = {
            'name': partner.name,
            'partner_id': partner.id,
            'email_from': self.company_email or partner.email or '',
            'phone': self.company_phone or partner.phone or '',
        }
        if self.has_solicitud:
            lines = [
                f"Producto: {self.sol_product or '—'}",
                f"Cantidad: {self.sol_qty} ({self.sol_env or ''})" if self.sol_qty else '',
                f"Presupuesto: ${self.sol_budget:,.2f} USD" if self.sol_budget else '',
                f"Entrega deseada: {self.sol_delivery}" if self.sol_delivery else '',
                f"Especificaciones: {self.sol_specs}" if self.sol_specs else '',
                f"Observaciones: {self.sol_obs}" if self.sol_obs else '',
            ]
            if self.cp_mode == 'cotiza':
                lines.append("Proveedor: Que me coticen (ENETEC)")
            elif cp_partner:
                lines.append(f"Proveedor: {cp_partner.name}")
            lead_vals['description'] = "\n".join(l for l in lines if l)

        lead = self.env['crm.lead'].create(lead_vals)

        # 4. Reasignar adjuntos y construir expediente
        cat_key = self.client_type if self.en_party_role == 'client' else 'Proveedor'
        uploaded = {}
        verdicts = {}
        for doc in self.doc_line_ids:
            if doc.attachment_id:
                doc.attachment_id.sudo().write({
                    'res_model': 'crm.lead',
                    'res_id': lead.id,
                })
                uploaded[doc.doc_label] = doc.attachment_id.id
                if doc.ai_state:
                    verdicts[doc.doc_label] = {
                        'ai_state': doc.ai_state,
                        'ai_confidence': doc.ai_confidence,
                        'ai_quality': doc.ai_quality,
                        'ai_reason': doc.ai_reason or False,
                        'ai_extracted_data': doc.ai_extracted_data or False,
                        'findings': json.loads(doc.ai_findings) if doc.ai_findings else [],
                    }

        self.env['pyxel.lead.document'].sudo().build_expediente(
            lead, cat_key, uploaded, verdicts)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CrmLeadWizardDoc(models.TransientModel):
    _name = 'crm.lead.wizard.doc'
    _description = 'Documento del asistente de acreditación'
    _order = 'id'

    wizard_id = fields.Many2one('crm.lead.create.wizard', ondelete='cascade')
    doc_key = fields.Char()
    doc_label = fields.Char(string="Documento")
    is_required = fields.Boolean(string="Requerido", default=True)

    attachment_id = fields.Many2one('ir.attachment', string="Archivo subido")
    attachment_name = fields.Char(related='attachment_id.name', string="Nombre archivo")
    ai_state = fields.Selection([
        ('passed', 'Apto'), ('doubt', 'Dudoso'), ('rejected', 'No apto'),
        ('validating', 'Validando'), ('unavailable', 'Sin IA'),
    ], string="Dictamen IA")
    ai_confidence = fields.Float(string="Confianza (%)")
    ai_quality = fields.Float(string="Calidad (%)")
    ai_reason = fields.Text(string="Motivo IA")
    ai_extracted_data = fields.Text(string="Datos extraídos")
    ai_findings = fields.Text(string="Findings (JSON)")

    @api.model
    def upload_and_validate(self, wizard_doc_id, b64_data, filename):
        doc = self.sudo().browse(wizard_doc_id)
        if not doc.exists():
            return {'error': 'Documento no encontrado'}

        att = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'datas': b64_data,
            'res_model': self._name,
            'res_id': wizard_doc_id,
            'mimetype': 'application/pdf',
        })
        doc.attachment_id = att.id
        doc.ai_state = 'validating'

        try:
            import urllib.request

            doc_type = LABEL_TO_DOCVAL.get(doc.doc_label)
            if not doc_type:
                doc.ai_state = 'unavailable'
                return {'ok': True, 'ai_state': 'unavailable', 'attachment_id': att.id}

            payload = json.dumps({
                'doc_type': doc_type,
                'file_b64': b64_data,
                'filename': filename,
            }).encode()
            req = urllib.request.Request(
                f"{DOCVAL_URL}/validate",
                data=payload,
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())

            verdict = result.get('verdict', 'revisar')
            ai_state = VERDICT_MAP.get(verdict, 'doubt')
            findings = result.get('findings') or []
            doc.write({
                'ai_state': ai_state,
                'ai_confidence': float(result.get('confidence', 0)) * 100,
                'ai_quality': float(result.get('quality', 0)) * 100,
                'ai_reason': result.get('reason') or False,
                'ai_extracted_data': json.dumps(result.get('fields') or {}, ensure_ascii=False) if result.get('fields') else False,
                'ai_findings': json.dumps(findings, ensure_ascii=False) if findings else False,
            })
        except Exception as e:
            _logger.warning("DocValidator no disponible para wizard doc %s: %s", wizard_doc_id, e)
            doc.ai_state = 'unavailable'

        return {
            'ok': True,
            'ai_state': doc.ai_state,
            'ai_confidence': doc.ai_confidence,
            'ai_reason': doc.ai_reason or '',
            'attachment_id': att.id,
            'attachment_name': att.name,
        }
