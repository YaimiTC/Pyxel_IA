# -*- coding: utf-8 -*-
import base64
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

VALIDITY = {'1 mes': '1m', '3 meses': '3m', '6 meses': '6m', '1 año': '1y', 'Personalizada': 'custom'}

# Nombres reales (en_US, sin traducción es_ES) de los combustibles que ofrece
# el wizard. Buscar en ese idioma evita el problema de tildes/traducciones
# vacías al hacer match por nombre.
FUEL_PRODUCT_NAMES = ['DIESEL', 'GASOLINA-91', 'GASOLINA-83', 'Jet A-1', 'Fuel oíl', 'GLP']

# Prefijos de docGrid() para tipos de cliente cubano (en_wizard.xml, var DOCS).
# Solo válidos dentro de newClients[i].docFiles (prefijo newclient:N:); si
# aparecen sueltos con el prefijo genérico doc: es que quedaron pegados de una
# edición de cliente abandonada a medias — no son del proveedor que los envía.
CLIENT_TYPE_PREFIXES = ('Pymes', 'Estatal', 'CNA', 'Sucursal Extranjera')


def _find_product(name):
    if not name:
        return False
    P = request.env['product.product'].sudo().with_context(lang='en_US')
    return P.search([('name', 'ilike', name)], limit=1)


def _resolve_product(pid, name):
    """Resuelve un producto por id (preferido, viene del desplegable real del
    wizard) o, si falta, por nombre (compatibilidad/último recurso)."""
    if pid and str(pid).isdigit():
        p = request.env['product.product'].sudo().browse(int(pid))
        if p.exists():
            return p
    return _find_product(name)


# Litro (11) / Galón US (25) — las únicas 2 unidades de volumen que el front
# deja elegir por línea, según lo que declare la factura de cada envío.
UOM_IDS = {11, 25}


def _line_uom_id(ln):
    try:
        uid = int(ln.get('uom'))
    except (TypeError, ValueError):
        return 11
    return uid if uid in UOM_IDS else 11


def _safe_packaging(product, pkg):
    """La gasolina no puede entrar al país en isomódulo — si llega esa
    combinación (el front ya la filtra, pero esto cubre envíos directos a la
    API), se corrige a isotanque. Válida también del lado del servidor lo que
    el JS de en_wizard.xml ya restringe en el desplegable de envase."""
    if pkg != 'isomodulo' or not product:
        return pkg
    is_gasoline = bool(request.env['product.product'].sudo().with_context(lang='en_US').search(
        [('id', '=', product.id), ('name', 'in', ['GASOLINA-91', 'GASOLINA-83'])], limit=1))
    return 'isotanque' if is_gasoline else pkg


def _contact_type(name):
    return request.env['res.partner.contact.type'].sudo().search([('name', '=', name)], limit=1)


class EnWizard(http.Controller):

    @http.route('/en/wizard', type='http', auth='user', website=True)
    def wizard_page(self, **kw):
        env = request.env
        person = env.user.partner_id
        # La empresa es el partner padre (si ya existe); la persona es el contacto.
        company = person.parent_id if (person.parent_id and person.parent_id.is_company) else person
        lead = env['crm.lead'].sudo().search(
            [('partner_id', '=', company.id), ('en_party_role', '!=', False)],
            order='create_date desc', limit=1)
        # Un lead activo (no rechazado) = ya tiene oportunidad → importOnly.
        # No hace falta haber pasado la etapa de acreditación: simplemente tener
        # una oportunidad abierta significa que no hay que crear otra.
        has_active_lead = bool(lead and not lead.stage_id.is_rejection_stage)
        # Sin ?op=1: si ya tiene proceso en curso, redirigir a seguimiento.
        if not kw.get('op'):
            if has_active_lead:
                return request.redirect('/my/seguimiento')
        role = 'proveedor' if company.contact_type_id.type_of_contact == 'Supplier' else 'cliente'
        pay_methods = env['en.payment.method'].sudo().search([])
        return request.render('pyxel_enetradex_website.en_wizard_page', {
            'wz_op': bool(kw.get('op')),
            'wz_accredited': has_active_lead,
            'wz_role': role,
            'wz_company': (company.name or '') if company != person else '',
            'wz_contact': person.name or '',
            'wz_email': person.email or '',
            'wz_phone': person.phone or '',
            'wz_pay_methods': json.dumps(
                [{'id': m.id, 'name': m.name} for m in pay_methods]),
        })

    @http.route('/en/wizard/enviado', type='http', auth='user', website=True)
    def wizard_done(self, **kw):
        return request.render('pyxel_enetradex_website.en_wizard_done',
                               {'wz_op': bool(kw.get('op')), 'wz_offer': bool(kw.get('offer'))})

    @http.route('/check_duplicate_nit', type='json', auth='user', website=True)
    def check_duplicate_nit(self, nit, **kw):
        """True si el NIT está libre (no lo usa otra empresa). Excluye la propia
        empresa del usuario para no marcar su propio NIT como duplicado."""
        if not nit:
            return True
        me = request.env.user.partner_id.commercial_partner_id or request.env.user.partner_id
        partner = request.env['res.partner'].sudo().search(
            [('vat', '=', nit), ('id', '!=', me.id)], limit=1)
        return not bool(partner)

    @http.route('/get_form_countries', type='json', auth='user', website=True)
    def get_form_countries(self, **kw):
        countries = request.env['res.country'].sudo().search([])
        return {str(c.id): c.name for c in countries}

    @http.route('/en/wizard/fuel_products', type='json', auth='user', website=True)
    def wizard_fuel_products(self, **kw):
        """Productos reales de combustible (id + nombre) para los desplegables
        de Solicitud/Oferta — evita adivinar el producto por nombre."""
        P = request.env['product.product'].sudo().with_context(lang='en_US')
        products = P.search([('name', 'in', FUEL_PRODUCT_NAMES)])
        by_name = {p.name: p for p in products}
        ordered = [by_name[n] for n in FUEL_PRODUCT_NAMES if n in by_name]
        return [{'id': p.id, 'name': p.name, 'uom_name': p.uom_id.name} for p in ordered]

    @http.route('/en/wizard/debug_ping', type='json', auth='user', website=True)
    def wizard_debug_ping(self, **kw):
        """Diagnóstico temporal (2026-07-15): registra el estado del wizard en
        cada paso, para investigar el reporte de 'un cliente y no sale
        Solicitud' sin depender de capturas de pantalla de la usuaria. Escribe
        a un archivo plano en vez de solo al log — docker logs no lo mostraba
        de forma confiable en el servidor real."""
        import datetime
        line = '%s user=%s %s\n' % (datetime.datetime.now().isoformat(), request.env.user.login, kw)
        try:
            with open('/tmp/wz_debug.log', 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass
        _logger.info('WZ_DEBUG user=%s %s', request.env.user.login, kw)
        return {'ok': True}

    @http.route('/en/wizard/portfolio', type='json', auth='user', website=True)
    def wizard_portfolio(self, **kw):
        """Proveedores reales del cliente (su cartera) para elegir en la solicitud."""
        env = request.env
        person = env.user.partner_id
        company = person.parent_id if (person.parent_id and person.parent_id.is_company) else person
        rels = env['en.counterparty.relation'].sudo().search([('client_id', '=', company.id)])
        res, seen = [], set()
        for r in rels:
            s = r.supplier_id
            if not s or s.id in seen or s.id == company.id:
                continue
            seen.add(s.id)
            nit = s.vat or ''
            if len(nit) > 7:
                nit = nit[:4] + '…' + nit[-3:]
            res.append({'id': s.id, 'name': s.name,
                        'nit': nit, 'accredited': bool(s.is_accredited)})
        return res

    @http.route('/en/wizard/my_clients', type='json', auth='user', website=True)
    def wizard_my_clients(self, **kw):
        """Clientes reales del proveedor (su cartera) para elegir en la oferta."""
        env = request.env
        person = env.user.partner_id
        company = person.parent_id if (person.parent_id and person.parent_id.is_company) else person
        rels = env['en.counterparty.relation'].sudo().search([('supplier_id', '=', company.id)])
        res, seen = [], set()
        for r in rels:
            c = r.client_id
            if not c or c.id in seen or c.id == company.id:
                continue
            seen.add(c.id)
            nit = c.vat or ''
            if len(nit) > 7:
                nit = nit[:4] + '…' + nit[-3:]
            res.append({'id': c.id, 'name': c.name,
                        'nit': nit, 'accredited': bool(c.is_accredited)})
        return res

    @http.route('/en/wizard/photo_to_pdf', type='json', auth='user', website=True)
    def photo_to_pdf(self, images=None, **kw):
        """Recibe lista de imágenes base64, las une en PDF con Pillow y devuelve el PDF base64."""
        import base64, io
        images = images or []
        if not images:
            return {'error': 'Sin imágenes'}
        try:
            from PIL import Image as PILImage
            imgs = []
            for b64 in images:
                raw = base64.b64decode(b64)
                imgs.append(PILImage.open(io.BytesIO(raw)).convert('RGB'))
            buf = io.BytesIO()
            imgs[0].save(buf, format='PDF', save_all=True, append_images=imgs[1:])
            pdf_b64 = base64.b64encode(buf.getvalue()).decode()
            return {'pdf': pdf_b64}
        except Exception as e:
            return {'error': str(e)}

    @http.route('/en/wizard/validate_doc', type='json', auth='user', website=True)
    def validate_doc(self, label=None, file_b64=None, **kw):
        """Valida un documento al subirlo (DocValidator IA) y devuelve el veredicto."""
        return request.env['pyxel.lead.document'].sudo()._docvalidator_verify(
            file_b64 or '', label or '')

    # Catálogo público de ofertas (filtrado por producto + texto)
    @http.route('/en/catalog/offers', type='json', auth='public', website=True)
    def catalog_offers(self, product=None, query=None, **kw):
        Offer = request.env['en.supply.offer'].sudo()
        domain = [('state', '=', 'published'), ('supplier_id.en_is_public_provider', '=', True)]
        offers = Offer.search(domain)
        res = []
        for o in offers:
            fuels = ', '.join(o.line_ids.mapped('product_id.name')) or '—'
            if product and product.lower() not in fuels.lower():
                continue
            blob = '%s %s %s' % (o.supplier_id.name or '', fuels, o.port or '')
            if query and query.lower() not in blob.lower():
                continue
            prices = o.line_ids.mapped('unit_price')
            rng = ('$%.2f–%.2f' % (min(prices), max(prices))) if prices else '—'
            res.append({
                'id': o.id, 'supplier': o.supplier_id.name, 'fuels': fuels,
                'price': rng, 'port': o.port or '—', 'total': o.total,
            })
        return res

    # ===== Página del invitado (auto-acreditación mínima) =====
    @http.route('/en/accredit/<string:token>', type='http', auth='public', website=True)
    def invited_page(self, token, **kw):
        inv = request.env['en.accreditation.invitation'].sudo().search([('token', '=', token)], limit=1)
        if not inv:
            return request.render('pyxel_enetradex_website.en_invited_invalid', {})
        if inv.state == 'sent':
            inv.state = 'opened'
        mtypes = request.env['res.partner.management.type'].sudo().search([])
        return request.render('pyxel_enetradex_website.en_invited_page', {'inv': inv, 'mtypes': mtypes})

    @http.route('/en/accredit/<string:token>/submit', type='http', auth='public', website=True, csrf=False)
    def invited_submit(self, token, **post):
        inv = request.env['en.accreditation.invitation'].sudo().search([('token', '=', token)], limit=1)
        if not inv or inv.state == 'accepted':
            return request.redirect('/en/accredit/%s' % token)
        name = post.get('company_name') or inv.email
        role = inv.expected_role
        ct = _contact_type('Proveedor extranjero' if role == 'supplier' else 'Cliente nacional')
        vals = {'name': name, 'company_type': 'company', 'email': inv.email}
        if ct:
            vals['contact_type_id'] = ct.id
        if role == 'client' and post.get('management_type_id'):
            vals['management_type_id'] = int(post['management_type_id'])
        partner = request.env['res.partner'].sudo().create(vals)
        lead = request.env['crm.lead'].sudo().create({
            'name': name, 'partner_id': partner.id, 'type': 'opportunity',
            'en_initiated_by': 'counterparty', 'user_id': False,
            'en_inviter_partner_id': inv.inviter_partner_id.id if inv.inviter_partner_id else False,
        })
        inv.sudo().write({'state': 'accepted', 'accepted_partner_id': partner.id, 'accepted_lead_id': lead.id})
        if inv.inviter_partner_id:
            inv.inviter_partner_id.sudo().message_post(
                body="%s ya envió su información de acreditación (invitación a %s). El abogado la revisará." % (name, inv.email))
        return request.render('pyxel_enetradex_website.en_invited_done',
                              {'inv': inv, 'inviter': inv.inviter_partner_id})

    @http.route('/en/wizard/submit', type='http', auth='user', website=True, csrf=False)
    def wizard_submit(self, **post):
        try:
            return self._wizard_submit_impl(**post)
        except Exception as e:
            # Sin este try/except, cualquier error a mitad del proceso (NIT
            # duplicado, campo obligatorio faltante, etc.) hace que Odoo devuelva
            # una página de error HTML en vez de JSON: el front no puede leer el
            # motivo real y solo muestra "No se pudo enviar. Inténtalo de nuevo."
            _logger.exception('Error en /en/wizard/submit')
            request.env.cr.rollback()
            return request.make_response(
                json.dumps({'ok': False, 'error': str(e)}),
                headers=[('Content-Type', 'application/json')])

    def _wizard_submit_impl(self, **post):
        try:
            payload = json.loads(post.get('payload') or '{}')
        except Exception:
            payload = {}
        env = request.env
        user = env.user
        person = user.partner_id
        role = payload.get('role')
        created = {'lead': None, 'relation': None, 'offer': None, 'tender': None,
                   'process': None, 'invitations': [], 'clients': 0}

        # Empresa actual del usuario (misma resolución que /en/wizard): la empresa
        # es el partner padre si es compañía; si no, el propio partner del usuario.
        company_existing = person.parent_id if (person.parent_id and person.parent_id.is_company) else person
        # Modo "solo importación": cliente YA acreditado que pide una operación. NO
        # se reestructura su empresa ni se crea un lead de acreditación; se usa su
        # empresa existente y se va directo a crear la solicitud de importación.
        lead_existing = env['crm.lead'].sudo().search(
            [('partner_id', '=', company_existing.id), ('en_party_role', '!=', False)],
            order='create_date desc', limit=1)
        # importOnly: basta con tener una oportunidad activa (no rechazada).
        # No se requiere haber pasado la etapa de acreditación.
        _has_active_lead = bool(
            lead_existing and not lead_existing.stage_id.is_rejection_stage)
        import_only = (bool(payload.get('importOnly')) and role == 'cliente'
                       and _has_active_lead)
        offer_only = (bool(payload.get('offerOnly')) and role == 'proveedor'
                      and _has_active_lead)
        skip_accreditation = import_only or offer_only
        if skip_accreditation:
            company = company_existing
            created['lead'] = False
        else:
            company = self._wizard_accreditation(env, payload, person, role, created)

        Rel = env['en.counterparty.relation'].sudo()
        Inv = env['en.accreditation.invitation'].sudo()
        cuba = env['res.country'].sudo().search([('code', '=', 'CU')], limit=1)
        return self._wizard_after_company(
            env, payload, person, role, company, created, Rel, Inv, cuba)

    def _wizard_accreditation(self, env, payload, person, role, created):
        # 1) Acreditación propia: separar PERSONA (contacto) y EMPRESA (partner padre)
        ct = _contact_type('Cliente nacional' if role == 'cliente' else 'Proveedor extranjero')
        mt = False
        mt_name = payload.get('ctype')
        if mt_name:
            mt = env['res.partner.management.type'].sudo().search([('name', '=', mt_name)], limit=1)
        co = payload.get('company') or {}
        contact = payload.get('contact') or {}

        # Empresa = partner padre (is_company); se crea si aún no existe.
        Partner = env['res.partner'].sudo()
        company = person.parent_id if (person.parent_id and person.parent_id.is_company) else False
        cvals = {'is_company': True, 'company_type': 'company'}
        if ct:
            cvals['contact_type_id'] = ct.id
        if mt:
            cvals['management_type_id'] = mt.id
        if co.get('name'):
            cvals['name'] = co['name']
        if co.get('nit'):
            cvals['vat'] = co['nit']
        cvals['visible_to_clients'] = bool(co.get('visible_to_clients'))
        cvals['visible_to_providers'] = bool(co.get('visible_to_providers'))
        if co.get('address'):
            cvals['street'] = co['address']
        if co.get('state_id'):
            try:
                cvals['state_id'] = int(co['state_id'])
            except (ValueError, TypeError):
                pass
        if co.get('city_id'):
            try:
                city = env['res.city'].sudo().browse(int(co['city_id']))
                if city.exists():
                    cvals['city_id'] = city.id
                    cvals['city'] = city.name
            except (ValueError, TypeError):
                pass
        # Campos propios del proveedor extranjero
        if role == 'proveedor':
            prov = payload.get('prov') or {}
            if prov.get('country_id'):
                try:
                    cvals['country_id'] = int(prov['country_id'])
                except (ValueError, TypeError):
                    pass
            cvals['en_requiere_mincex'] = bool(prov.get('requiere_mincex'))
            cvals['en_socio_cubano'] = bool(prov.get('socio_cubano'))
            if prov.get('mincex'):
                cvals['license_holder'] = prov['mincex']
            cat_xmlid = {
                'Productor': 'pyxel_import_backend.res_partner_category_producer',
                'Comerciante': 'pyxel_import_backend.res_partner_category_businessman',
            }.get(prov.get('clasificacion'))
            if cat_xmlid:
                cat = env.ref(cat_xmlid, raise_if_not_found=False)
                if cat:
                    cvals['category_id'] = [(4, cat.id)]
        if not company:
            cvals.setdefault('name', co.get('name') or 'Empresa')
            company = Partner.create(cvals)
        else:
            company.write(cvals)

        # Persona = el usuario portal, como contacto de la empresa.
        pvals = {'parent_id': company.id, 'company_type': 'person'}
        if contact.get('name'):
            pvals['name'] = contact['name']
        if contact.get('email'):
            pvals['email'] = contact['email']
        if contact.get('phone'):
            pvals['phone'] = contact['phone']
        person.sudo().write(pvals)

        Lead = env['crm.lead'].sudo()
        lead = Lead.search([('partner_id', '=', company.id)], limit=1)
        client_type_val = 'Proveedor' if role == 'proveedor' else (mt.name if mt else False)
        # Campos nativos de CRM (enlace contacto): persona de contacto + datos.
        native_contact = {
            'contact_name': contact.get('name') or person.name or False,
            'email_from': contact.get('email') or person.email or False,
            'phone': contact.get('phone') or person.phone or False,
        }
        if not lead:
            lead = Lead.create(dict({
                'name': company.name or 'Acreditación',
                'partner_id': company.id, 'type': 'opportunity', 'en_initiated_by': 'self',
                'user_id': False,
                'accreditation_client_type': client_type_val or False,
            }, **native_contact))
        else:
            lvals = {k: v for k, v in native_contact.items() if v}
            if client_type_val and not lead.accreditation_client_type:
                lvals['accreditation_client_type'] = client_type_val
            if lvals:
                lead.write(lvals)
        created['lead'] = lead.id
        created['docs'] = 0

        # Documentos subidos (multipart) -> adjuntos en el LEAD (donde el abogado
        # revisa) y también en el partner (la empresa los conserva).
        uploaded = {}  # {etiqueta_documento: attachment_id} para el expediente
        verdicts = payload.get('verdicts') or {}
        # La IA rechazó por completo -> NO se sube (el cliente debe reemplazarlo).
        rejected_labels = {lbl for lbl, v in verdicts.items() if (v or {}).get('ai_state') == 'rejected'}
        for field, f in request.httprequest.files.items():
            if field.startswith('socio:'):
                continue  # adjuntos del socio cubano: se procesan aparte
            if field.startswith('ship:') or field.startswith('shipnat:'):
                continue  # documentos del embarque: van a la solicitud de importación
            if role == 'cliente' and field.startswith('doc:Proveedor|'):
                continue  # documentos del proveedor que este cliente está acreditando:
                          # se adjuntan más abajo al partner del proveedor, no al del cliente
            if role == 'proveedor' and field.startswith('doc:') and \
                    field[len('doc:'):].split('|', 1)[0] in CLIENT_TYPE_PREFIXES:
                continue  # documentos de un cliente nuevo (newClients) que quedaron
                          # sueltos por una edición abandonada: no son del proveedor
            doc_label = field.split('|')[-1] if (field.startswith('doc:') and '|' in field) else None
            if doc_label and doc_label in rejected_labels:
                continue  # IA rechazó: no se adjunta, queda pendiente
            if f and f.filename:
                data = base64.b64encode(f.read())
                doc_name = field.split(':', 1)[-1].replace('|', ' · ') if ':' in field else f.filename
                att1 = env['ir.attachment'].sudo().create({
                    'name': '%s (%s)' % (doc_name, f.filename),
                    'datas': data, 'res_model': 'crm.lead', 'res_id': lead.id, 'type': 'binary',
                })
                env['ir.attachment'].sudo().create({
                    'name': f.filename, 'datas': data,
                    'res_model': 'res.partner', 'res_id': company.id, 'type': 'binary',
                })
                created['docs'] += 1
                if doc_label:
                    uploaded[doc_label] = att1.id

        # Expediente de acreditación (3 pasos por documento). Los rechazados por IA
        # no llevan attachment ni veredicto -> quedan "pendientes" para reemplazar.
        client_type = 'Proveedor' if role == 'proveedor' else (mt.name if mt else False)
        clean_verdicts = {k: v for k, v in verdicts.items() if k not in rejected_labels}
        if client_type and not lead.accreditation_document_ids:
            env['pyxel.lead.document'].sudo().build_expediente(
                lead, client_type, uploaded, clean_verdicts)
        return company

    def _wizard_after_company(self, env, payload, person, role, company, created, Rel, Inv, cuba):
        prov = payload.get('prov') or {}
        Lead = env['crm.lead'].sudo()
        lead = Lead.browse(created['lead']) if created.get('lead') else Lead
        # 2) PROVEEDOR: oferta + clientes
        co = payload.get('company') or {}
        offer_payload_peek = payload.get('offer') or {}
        has_provider_activity = bool(
            offer_payload_peek.get('lines') or payload.get('clients')
            or payload.get('newClients') or payload.get('diffused'))
        if role == 'proveedor' and has_provider_activity:
            # Visible en el catálogo solo si de verdad marcó la casilla — antes
            # quedaba público siempre que llegara a enviar oferta/clientes.
            company.sudo().write({'en_is_public_provider': bool(co.get('visible_to_clients'))})
            # Socio cubano residente en el exterior (si la empresa lo declara)
            socio = payload.get('socio') or {}
            sd = socio.get('data') or {}
            if prov.get('socio_cubano') and sd.get('nombre'):
                _d = lambda v: v or False
                cub = env['en.cuban.partner'].sudo().create({
                    'partner_id': company.id, 'lead_id': lead.id,
                    'name': sd.get('nombre'),
                    'passport_no': sd.get('pasaporte'),
                    'foreign_passport_no': sd.get('pasaporte_ext'),
                    'birth_date': _d(sd.get('nacimiento')),
                    'birth_place': sd.get('lugar_nac'),
                    'father_info': sd.get('padre'),
                    'mother_info': sd.get('madre'),
                    'current_address': sd.get('direccion'),
                    'mobile': sd.get('movil'),
                    'landline': sd.get('fijo'),
                    'email': sd.get('correo'),
                    'exit_date': _d(sd.get('salida')),
                    'last_address_cuba': sd.get('ult_dir_cuba'),
                    'graduated_of': sd.get('graduado'),
                    'graduation_date': _d(sd.get('fecha_grad')),
                    'work_in_cuba': sd.get('labor'),
                })
                for fkey, ff in request.httprequest.files.items():
                    if fkey.startswith('socio:') and ff and ff.filename:
                        env['ir.attachment'].sudo().create({
                            'name': '%s — %s (%s)' % (cub.name, fkey.split(':', 1)[-1], ff.filename),
                            'datas': base64.b64encode(ff.read()),
                            'res_model': 'en.cuban.partner', 'res_id': cub.id, 'type': 'binary',
                        })
                created['cuban_partner'] = cub.id
                # PDF del socio, adjunto entre los documentos de la empresa (lead + partner)
                try:
                    pdf, _x = env['ir.actions.report'].sudo()._render_qweb_pdf(
                        'pyxel_enetradex_backend.action_report_en_cuban_partner', [cub.id])
                    pdf_b64 = base64.b64encode(pdf)
                    pdf_name = 'Socio cubano - %s.pdf' % (cub.name or '')
                    for rmodel, rid in (('crm.lead', lead.id), ('res.partner', company.id)):
                        env['ir.attachment'].sudo().create({
                            'name': pdf_name, 'datas': pdf_b64,
                            'res_model': rmodel, 'res_id': rid,
                            'type': 'binary', 'mimetype': 'application/pdf',
                        })
                    created['socio_pdf'] = True
                except Exception:
                    created['socio_pdf'] = False
            # Oferta: catálogo/difusión únicamente — el detalle real por cliente
            # (costos, cantidades) vive en reqByClient, más abajo.
            offer = payload.get('offer') or {}
            lines = []
            for ln in (offer.get('lines') or []):
                qty = float(ln.get('qty') or 0)
                price = float(ln.get('price') or 0)
                if qty <= 0 or price <= 0:
                    continue  # cantidad/precio deben ser positivos y distintos de cero
                prod = _resolve_product(ln.get('pid'), ln.get('prod'))
                pkg = _safe_packaging(prod, 'isotanque' if ln.get('env') == 'Isotanque' else 'isomodulo')
                lines.append((0, 0, {
                    'product_id': prod.id if prod else False,
                    'packaging': pkg, 'qty': qty, 'unit_price': price,
                    'product_uom_id': _line_uom_id(ln),
                }))
            if lines:
                off = env['en.supply.offer'].sudo().create({
                    'supplier_id': company.id, 'state': 'published',
                    'validity': VALIDITY.get(offer.get('vigencia'), '3m'),
                    'port': offer.get('port') or False,
                    'flete': float(offer.get('flete') or 0), 'seguro': float(offer.get('seguro') or 0),
                    'line_ids': lines,
                })
                created['offer'] = off.id

            # --- Clientes del envío: hasta 3 orígenes posibles, cada uno con una
            # "key" que coincide con el esquema del front (embarqueClients()) para
            # poder enlazar después BL/documentos por bloque. ---
            resolved_clients = []  # [(key, partner_record)]

            # 1) Cartera real ("tengo"): ids reales, ya tienen relación —
            # no se crea nada, solo se reutiliza el partner existente.
            for cid in (payload.get('clients') or []):
                try:
                    cid_int = int(cid)
                except (TypeError, ValueError):
                    continue
                cand = env['res.partner'].sudo().browse(cid_int)
                if cand.exists():
                    resolved_clients.append(('cartera:%s' % cid_int, cand))

            # 2) Clientes nuevos con datos completos ("sumar"): antes el botón
            # "+ Agregar cliente" no leía nada del formulario y solo guardaba un
            # nombre genérico — ahora crea el partner con sus datos reales,
            # contacto y documentos. Busca primero por NIT: si el cliente ya
            # existe (acreditado o no), se reutiliza en vez de crear un
            # duplicado sin acreditar que dejaría la operación bloqueada.
            for idx, ncli in enumerate(payload.get('newClients') or []):
                cli = False
                if ncli.get('nit'):
                    cli = env['res.partner'].sudo().search(
                        [('vat', '=', ncli['nit']), ('company_type', '=', 'company')], limit=1)
                if not cli:
                    ct = _contact_type('Cliente nacional')
                    mt = False
                    if ncli.get('ctype'):
                        mt = env['res.partner.management.type'].sudo().search(
                            [('name', '=', ncli['ctype'])], limit=1)
                    cvals = {
                        'name': ncli.get('name') or 'Cliente (registrado por %s)' % (company.name or 'proveedor'),
                        'company_type': 'company',
                        'contact_type_id': (ct.id if ct else False),
                        'visible_to_providers': bool(ncli.get('visibleToProviders')),
                    }
                    if mt:
                        cvals['management_type_id'] = mt.id
                    if ncli.get('nit'):
                        cvals['vat'] = ncli['nit']
                    if ncli.get('address'):
                        cvals['street'] = ncli['address']
                    if ncli.get('state'):
                        try:
                            cvals['state_id'] = int(ncli['state'])
                        except (TypeError, ValueError):
                            pass
                    if ncli.get('city'):
                        try:
                            city = env['res.city'].sudo().browse(int(ncli['city']))
                            if city.exists():
                                cvals['city_id'] = city.id
                                cvals['city'] = city.name
                        except (TypeError, ValueError):
                            pass
                    cli = env['res.partner'].sudo().create(cvals)
                    if ncli.get('contactName') or ncli.get('contactEmail') or ncli.get('contactPhone'):
                        env['res.partner'].sudo().create({
                            'parent_id': cli.id, 'company_type': 'person',
                            'name': ncli.get('contactName') or False,
                            'email': ncli.get('contactEmail') or False,
                            'phone': ncli.get('contactPhone') or False,
                        })
                prefix = 'newclient:%d:' % idx
                for fkey, ff in request.httprequest.files.items():
                    if not fkey.startswith(prefix) or not (ff and ff.filename):
                        continue
                    doc_label = fkey[len(prefix):]
                    doc_label = doc_label.split('|')[-1] if '|' in doc_label else doc_label
                    env['ir.attachment'].sudo().create({
                        'name': '%s (%s)' % (doc_label, ff.filename),
                        'datas': base64.b64encode(ff.read()),
                        'res_model': 'res.partner', 'res_id': cli.id, 'type': 'binary',
                    })
                if not Rel.search([('client_id', '=', cli.id), ('supplier_id', '=', company.id)], limit=1):
                    try:
                        Rel.create({'client_id': cli.id, 'supplier_id': company.id,
                                    'initiated_by': 'supplier', 'state': 'pending'})
                        created['clients'] += 1
                    except Exception:
                        pass
                resolved_clients.append(('new:%d' % idx, cli))

            # 3) Consignación: la mercancía llega sin cliente final definido —
            # se usa un partner fijo (ENETEC como responsable temporal), igual
            # patrón que "Proveedor por designar" del lado cliente.
            if payload.get('cpHas') == 'consignacion':
                consig = env['res.partner'].sudo().search(
                    [('name', '=', 'Enetec_Consignacion'), ('company_type', '=', 'company')], limit=1)
                if not consig:
                    consig = env['res.partner'].sudo().create({
                        'name': 'Enetec_Consignacion', 'company_type': 'company',
                        'contact_type_id': (_contact_type('Cliente nacional').id or False),
                    })
                resolved_clients.append(('consignacion', consig))

            # Costos por cliente (paso "Solicitud"): cada cliente tiene sus
            # propios productos/cantidades/precios — ya NO se reutiliza la
            # oferta compartida (esa es solo para el catálogo/difusión).
            resolved_lines_by_key = {}
            for key, rlines in (payload.get('reqByClient') or {}).items():
                resolved = []
                for ln in (rlines or []):
                    rqty = float(ln.get('qty') or 0)
                    rprice = float(ln.get('price') or 0)
                    if rqty <= 0 or rprice <= 0:
                        continue  # cantidad/precio deben ser positivos y distintos de cero
                    rprod = _resolve_product(ln.get('pid'), ln.get('prod'))
                    if not rprod:
                        continue
                    rpkg = _safe_packaging(rprod, 'isotanque' if ln.get('env') == 'Isotanque' else 'isomodulo')
                    resolved.append({'product': rprod, 'qty': rqty, 'packaging': rpkg,
                                      'price': rprice, 'uom_id': _line_uom_id(ln)})
                if resolved:
                    resolved_lines_by_key[key] = resolved

            # Si el proveedor llenó el paso Clientes con datos reales, ya no es
            # solo una oferta suelta: se crea una importación real (misma
            # arquitectura que usa el equipo desde "Crear Clientes del envío"),
            # con un bloque por cada cliente — y la OC correspondiente en
            # borrador, con los costos de ESE cliente si ya los cargó (si no,
            # queda vacía y el comercial la completa después).
            if resolved_clients:
                # País de origen: el elegido en el paso "Documentos del embarque"
                # tiene prioridad (es la señal más explícita para esta solicitud
                # en concreto); si no se llenó, cae al país declarado en "Mis
                # datos" y, como último recurso, al país registrado del proveedor.
                origin = False
                ship = payload.get('shipData') or {}
                if ship.get('country_id') and str(ship['country_id']).isdigit():
                    origin = int(ship['country_id'])
                if not origin and prov.get('country_id'):
                    try:
                        origin = int(prov['country_id'])
                    except (TypeError, ValueError):
                        origin = False
                if not origin and company.country_id:
                    origin = company.country_id.id
                if not origin and cuba:
                    origin = cuba.id
                if origin:
                    prov_bl = payload.get('provBl') or {}
                    blocks = []
                    for i, (key, cli) in enumerate(resolved_clients):
                        block_lines = [(0, 0, {
                            'product_id': rl['product'].id,
                            'product_name': rl['product'].name,
                            'qty': rl['qty'],
                            'packaging': rl['packaging'],
                            'product_uom_id': rl['uom_id'],
                        }) for rl in resolved_lines_by_key.get(key, [])]
                        blocks.append((0, 0, {
                            'sequence': (i + 1) * 10,
                            'customer_id': cli.id,
                            'bl_number': prov_bl.get(key) or False,
                            'product_line_ids': block_lines,
                        }))
                    proc = env['importation.process'].sudo().create({
                        'provider_id': company.id,
                        'country_origin_id': origin,
                        'en_request_client_ids': blocks,
                    })
                    proc._compute_filtered_hubs()
                    created['process'] = proc.id

                    # OC en borrador por cada bloque: el comercial la revisa y
                    # confirma, pero el precio y los documentos ya llegan cargados.
                    default_ccy = env.ref('base.USD', raise_if_not_found=False)
                    doc_type_map = {
                        'Oferta firmada': 'oferta_firmada',
                        'Factura comercial': 'factura_comercial',
                        'Lista de empaque': 'lista_empaque',
                        'Permisos regulatorios': 'permisos',
                    }
                    for block, (key, cli) in zip(proc.en_request_client_ids, resolved_clients):
                        po_lines = [(0, 0, {
                            'product_id': rl['product'].id, 'name': rl['product'].display_name,
                            'product_qty': rl['qty'] or 0.0, 'price_unit': rl['price'] or 0.0,
                            'product_uom': rl['uom_id'],
                            'taxes_id': [(6, 0, [])],
                        }) for rl in resolved_lines_by_key.get(key, [])]
                        po = env['purchase.order'].sudo().create({
                            'partner_id': company.id,
                            'customer_id': cli.id,
                            'importation_id': proc.id,
                            'bl_number': prov_bl.get(key) or False,
                            'currency_id': default_ccy.id if default_ccy else False,
                            'origin': proc.name,
                            'order_line': po_lines,
                        })
                        block.purchase_order_id = po.id

                        doc_prefix = 'provship:%s|' % key
                        for fkey, ff in request.httprequest.files.items():
                            if not fkey.startswith(doc_prefix) or not (ff and ff.filename):
                                continue
                            doc_label = fkey[len(doc_prefix):]
                            env['en.import.request.document'].sudo().create({
                                'client_block_id': block.id,
                                'document_type': doc_type_map.get(doc_label, 'otro'),
                                'name': doc_label,
                                'attachment': base64.b64encode(ff.read()),
                                'filename': ff.filename,
                            })

            # Certificados compartidos del embarque (aplican a todo el proceso,
            # no a una OC en particular) — mismo mecanismo que usa cliente.
            if created.get('process'):
                proc_ship = env['importation.process'].sudo().browse(created['process'])
                nship = 0
                for fkey, ff in request.httprequest.files.items():
                    if not fkey.startswith('ship:') or not (ff and ff.filename):
                        continue
                    doc_name = fkey.split(':', 1)[-1]
                    env['ir.attachment'].sudo().create({
                        'name': '%s (%s)' % (doc_name, ff.filename),
                        'datas': base64.b64encode(ff.read()),
                        'res_model': 'importation.process', 'res_id': proc_ship.id,
                        'type': 'binary',
                    })
                    nship += 1
                if nship:
                    created['ship_docs'] = nship
                NATIVE_FIELDS = {'documentation_file', 'export_certificate',
                                 'quality_certificate', 'origin_certificate'}
                nat_vals = {}
                for fkey, ff in request.httprequest.files.items():
                    if not fkey.startswith('shipnat:') or not (ff and ff.filename):
                        continue
                    fname = fkey.split(':', 1)[-1]
                    if fname in NATIVE_FIELDS:
                        nat_vals[fname] = base64.b64encode(ff.read())
                        nat_vals[fname + '_filename'] = ff.filename
                if nat_vals:
                    proc_ship.write(nat_vals)
                    created['ship_native_docs'] = len([k for k in nat_vals if not k.endswith('_filename')])

            # Clientes invitados por email: solo enviar correo + nota en el lead
            base_url = env['ir.config_parameter'].sudo().get_param('web.base.url')
            signup_url = '%s/web/signup?redirect=/en/wizard' % base_url
            lead_prov = env['crm.lead'].sudo().search([('partner_id', '=', company.id)], limit=1)
            for inv_email in (payload.get('inviteEmails') or []):
                try:
                    env['mail.mail'].sudo().create({
                        'subject': 'Invitación para acreditarse en ENETRADEX',
                        'email_to': inv_email,
                        'body_html': (
                            '<p>Estimado cliente,</p>'
                            '<p><b>%s</b> le ha invitado a acreditarse en la plataforma ENETRADEX.</p>'
                            '<p><a href="%s">Haga clic aquí para registrarse y comenzar su acreditación</a></p>'
                        ) % (company.name or 'Un proveedor', signup_url),
                    }).send()
                except Exception:
                    pass
                if lead_prov:
                    lead_prov.message_post(body='Se invitó al cliente: %s' % inv_email)
            created['invited_clients'] = len(payload.get('inviteEmails') or [])
            # Difundir oferta: clientes que aceptan recibir ofertas
            created['diffused'] = 0
            for cname in (payload.get('diffused') or []):
                cli = env['res.partner'].sudo().search(
                    [('name', '=', cname), ('company_type', '=', 'company')], limit=1)
                if not cli:
                    cli = env['res.partner'].sudo().create({
                        'name': cname, 'company_type': 'company', 'en_accepts_offers': True,
                        'contact_type_id': (_contact_type('Cliente nacional').id or False),
                    })
                if not Rel.search([('client_id', '=', cli.id), ('supplier_id', '=', company.id)], limit=1):
                    try:
                        Rel.create({'client_id': cli.id, 'supplier_id': company.id,
                                    'initiated_by': 'supplier', 'state': 'pending', 'source': 'panel'})
                        created['diffused'] += 1
                    except Exception:
                        pass

        # 3) CLIENTE: contraparte (proveedor) + solicitud (operación)
        if role == 'cliente':
            cphas = payload.get('cpHas')
            cp = payload.get('cp')
            cpsel = payload.get('cpSel')
            sol = payload.get('sol') or {}
            supplier = False

            # Datos de la solicitud (se guardan en la importation.process para
            # que el comercial los revise).
            def _sol_vals():
                prod = _resolve_product(sol.get('productId'), sol.get('product'))
                pm = sol.get('payment_method_id')
                vals = {
                    'en_requested_product_id': prod.id if prod else False,
                    'en_requested_qty': float(sol.get('qty') or 0),
                    'en_specifications': sol.get('specifications') or False,
                    'en_observations': sol.get('observations') or False,
                }
                # Líneas multiproducto de la solicitud.
                lines = []
                for i, ln in enumerate(sol.get('lines') or []):
                    if float(ln.get('qty') or 0) <= 0:
                        continue  # cantidad debe ser positiva y distinta de cero
                    lp = _resolve_product(ln.get('pid'), ln.get('prod'))
                    pkg = ln.get('env')
                    pkg = _safe_packaging(lp, pkg) if pkg in ('isotanque', 'isomodulo') else False
                    lines.append((0, 0, {
                        'sequence': (i + 1) * 10,
                        'product_id': lp.id if lp else False,
                        'product_name': ln.get('prod') or False,
                        'qty': float(ln.get('qty') or 0),
                        'packaging': pkg,
                        'product_uom_id': _line_uom_id(ln),
                    }))
                if lines:
                    vals['en_request_line_ids'] = lines
                env_pkg = sol.get('envase')
                if env_pkg in ('isotanque', 'isomodulo'):
                    vals['en_packaging_type'] = _safe_packaging(prod, env_pkg)
                if sol.get('delivery'):
                    vals['en_delivery_date'] = sol.get('delivery')
                if pm and str(pm).isdigit():
                    vals['en_payment_method_id'] = int(pm)
                if sol.get('budget') not in (None, ''):
                    try:
                        vals['en_budget_usd'] = float(sol.get('budget'))
                    except (TypeError, ValueError):
                        pass
                return vals

            if cphas == 'cotiza':
                prod = _resolve_product(sol.get('productId'), sol.get('product'))
                t = env['en.tender'].sudo().create({
                    'client_id': company.id, 'product_id': prod.id if prod else False,
                    'qty': float(sol.get('qty') or 0), 'state': 'open',
                })
                created['tender'] = t.id
            elif cphas == 'buscar' and cpsel and str(cpsel).isdigit():
                off = env['en.supply.offer'].sudo().browse(int(cpsel))
                if off.exists():
                    supplier = off.supplier_id
            elif cphas == 'si' and cp == 'cartera' and cpsel and str(cpsel).isdigit():
                cand = env['res.partner'].sudo().browse(int(cpsel))
                if cand.exists():
                    supplier = cand
            elif cphas == 'si' and cp == 'info':
                cpinfo = payload.get('cpInfo') or {}
                sup_name = cpinfo.get('name') \
                    or 'Proveedor (registrado por %s)' % (company.name or 'cliente')
                # Proveedor se identifica por código MINCEX (license_holder), no
                # por NIT — si ya existe (acreditado o no), se reutiliza en vez
                # de crear un duplicado que dejaría la operación bloqueada. Si
                # no llegó MINCEX, se cae a buscar por nombre como último recurso.
                supplier = False
                if cpinfo.get('mincex'):
                    supplier = env['res.partner'].sudo().search(
                        [('license_holder', '=', cpinfo['mincex']), ('company_type', '=', 'company')], limit=1)
                if not supplier and sup_name:
                    supplier = env['res.partner'].sudo().search(
                        [('name', '=', sup_name), ('company_type', '=', 'company')], limit=1)
                if not supplier:
                    supplier = env['res.partner'].sudo().create({
                        'name': sup_name,
                        'company_type': 'company',
                        'contact_type_id': (_contact_type('Proveedor extranjero').id or False),
                        'license_holder': cpinfo.get('mincex') or False,
                    })
                    # Lead de acreditación del proveedor (lo registró el cliente)
                    # para que entre a la bandeja del abogado y pueda acreditarse.
                    # Solo si se creó de verdad: si se reutilizó uno existente,
                    # ya tiene (o no necesita) su propio lead de acreditación.
                    Lead.create({
                        'name': sup_name, 'partner_id': supplier.id, 'type': 'opportunity',
                        'en_initiated_by': 'counterparty', 'user_id': False,
                        'en_inviter_partner_id': company.id,
                    })
                # Documentos del proveedor (docGrid('Proveedor')) subidos por este
                # cliente: se adjuntan al partner del proveedor y a su propio lead
                # de acreditación — nunca al lead/partner del cliente que los sube.
                supplier_lead = Lead.search(
                    [('partner_id', '=', supplier.id), ('en_party_role', '!=', False)],
                    order='create_date desc', limit=1)
                for pfield, pf in request.httprequest.files.items():
                    if not pfield.startswith('doc:Proveedor|') or not (pf and pf.filename):
                        continue
                    pdata = base64.b64encode(pf.read())
                    pdoc_name = pfield.split(':', 1)[-1].replace('|', ' · ')
                    env['ir.attachment'].sudo().create({
                        'name': '%s (%s)' % (pdoc_name, pf.filename),
                        'datas': pdata, 'res_model': 'res.partner', 'res_id': supplier.id, 'type': 'binary',
                    })
                    if supplier_lead:
                        env['ir.attachment'].sudo().create({
                            'name': '%s (%s)' % (pdoc_name, pf.filename),
                            'datas': pdata, 'res_model': 'crm.lead', 'res_id': supplier_lead.id, 'type': 'binary',
                        })
            elif cphas == 'si' and cp == 'invitar' and payload.get('inviteEmail'):
                invite_email = payload.get('inviteEmail')
                base_url = env['ir.config_parameter'].sudo().get_param('web.base.url')
                signup_url = '%s/web/signup?redirect=/en/wizard' % base_url
                try:
                    env['mail.mail'].sudo().create({
                        'subject': 'Invitación para acreditarse en ENETRADEX',
                        'email_to': invite_email,
                        'body_html': (
                            '<p>Estimado proveedor,</p>'
                            '<p><b>%s</b> le ha invitado a acreditarse en la plataforma ENETRADEX.</p>'
                            '<p><a href="%s">Haga clic aquí para registrarse y comenzar su acreditación</a></p>'
                            '<p>Si el enlace no funciona, copie esta dirección en su navegador:<br/>%s</p>'
                        ) % (company.name or 'Un cliente', signup_url, signup_url),
                    }).send()
                except Exception:
                    pass
                if created.get('lead'):
                    env['crm.lead'].sudo().browse(created['lead']).message_post(
                        body='Se invitó al proveedor: %s' % invite_email)
                created['invitations'].append(invite_email)

            # Sin proveedor resuelto (no eligió vía, o "que me coticen"): en vez de
            # perder la solicitud, se usa un proveedor placeholder compartido, sin
            # acreditar. El proceso queda igual en el gate (nunca avanza porque el
            # placeholder no está acreditado) hasta que un comercial reemplace
            # provider_id por el proveedor real cuando lo consiga.
            if not supplier:
                supplier = env['res.partner'].sudo().search(
                    [('name', '=', 'Proveedor por designar'), ('company_type', '=', 'company')], limit=1)
                if not supplier:
                    supplier = env['res.partner'].sudo().create({
                        'name': 'Proveedor por designar',
                        'company_type': 'company',
                        'contact_type_id': (_contact_type('Proveedor extranjero').id or False),
                    })

            if supplier:
                # La relación cliente-proveedor es única: reusar si ya existe
                # (pueden tener varias operaciones sobre la misma relación).
                rel = Rel.search([('client_id', '=', company.id),
                                  ('supplier_id', '=', supplier.id)], limit=1)
                if not rel:
                    rel = Rel.create({'client_id': company.id, 'supplier_id': supplier.id,
                                      'initiated_by': 'client',
                                      'state': 'active' if supplier.is_accredited else 'pending'})
                created['relation'] = rel.id
                # País de origen: el elegido en el embarque; si no, el del proveedor;
                # como último recurso, Cuba (el campo es obligatorio en el proceso).
                ship = payload.get('shipData') or {}
                origin = False
                if ship.get('country_id') and str(ship['country_id']).isdigit():
                    origin = int(ship['country_id'])
                elif supplier.country_id:
                    origin = supplier.country_id.id
                elif cuba:
                    origin = cuba.id
                if origin:
                    proc_vals = {
                        'customer_id': company.id, 'provider_id': supplier.id,
                        'country_origin_id': origin,
                    }
                    proc_vals.update(_sol_vals())
                    proc = env['importation.process'].sudo().create(proc_vals)
                    # _compute_filtered_hubs es un @api.onchange: solo corre cuando
                    # alguien cambia el país a mano en el formulario. Al crear el
                    # proceso por API ese paso nunca se dispara y el comercial ve el
                    # puerto sin opciones hasta reseleccionar el país — se calcula
                    # aquí una vez para que ya quede resuelto desde el principio.
                    proc._compute_filtered_hubs()
                    created['process'] = proc.id
                    if created['relation']:
                        Rel.browse(created['relation']).process_id = proc.id
                    # Documentos del embarque -> adjuntos en la solicitud de
                    # importación (los revisa un comercial). TODO: validarlos con
                    # DocValidator y cruzar lista de empaque <-> factura comercial
                    # (detalle, cantidad, peso neto, peso bruto).
                    nship = 0
                    for fkey, ff in request.httprequest.files.items():
                        if not fkey.startswith('ship:') or not (ff and ff.filename):
                            continue
                        doc_name = fkey.split(':', 1)[-1]
                        env['ir.attachment'].sudo().create({
                            'name': '%s (%s)' % (doc_name, ff.filename),
                            'datas': base64.b64encode(ff.read()),
                            'res_model': 'importation.process', 'res_id': proc.id,
                            'type': 'binary',
                        })
                        nship += 1
                    if nship:
                        created['ship_docs'] = nship
                    # Documentación de la carga -> campos nativos del proceso
                    # (Documentación BL/AWB, Certificados de exportación/calidad/origen).
                    NATIVE_FIELDS = {'documentation_file', 'export_certificate',
                                     'quality_certificate', 'origin_certificate'}
                    nat_vals = {}
                    for fkey, ff in request.httprequest.files.items():
                        if not fkey.startswith('shipnat:') or not (ff and ff.filename):
                            continue
                        fname = fkey.split(':', 1)[-1]
                        if fname in NATIVE_FIELDS:
                            nat_vals[fname] = base64.b64encode(ff.read())
                            nat_vals[fname + '_filename'] = ff.filename
                    if nat_vals:
                        proc.write(nat_vals)
                        created['ship_native_docs'] = len([k for k in nat_vals if not k.endswith('_filename')])

        return request.make_response(
            json.dumps({'ok': True, 'created': created}),
            headers=[('Content-Type', 'application/json')])
