# -*- coding: utf-8 -*-
import base64
import json

from odoo import http
from odoo.http import request

VALIDITY = {'1 mes': '1m', '3 meses': '3m', '6 meses': '6m', '1 año': '1y', 'Personalizada': 'custom'}


def _find_product(name):
    if not name:
        return False
    P = request.env['product.product'].sudo()
    return P.search([('name', 'ilike', name)], limit=1)


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
        accredited = bool(company.is_accredited)
        # Sin ?op=1: si ya está acreditada o en proceso, no se le vuelve a pedir
        # acreditarse; se le lleva a ver en qué etapa va su proceso.
        if not kw.get('op'):
            if accredited or (lead and not lead.stage_id.is_rejection_stage):
                return request.redirect('/my/seguimiento')
        role = 'proveedor' if company.contact_type_id.type_of_contact == 'Supplier' else 'cliente'
        pay_methods = env['en.payment.method'].sudo().search([])
        return request.render('pyxel_enetradex_website.en_wizard_page', {
            'wz_op': bool(kw.get('op')),
            'wz_accredited': accredited,
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
        return request.render('pyxel_enetradex_website.en_wizard_done', {'wz_op': bool(kw.get('op'))})

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
        import_only = (bool(payload.get('importOnly')) and role == 'cliente'
                       and company_existing.is_accredited)
        if import_only:
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
        if not lead:
            lead = Lead.create({
                'name': company.name or 'Acreditación',
                'partner_id': company.id, 'type': 'opportunity', 'en_initiated_by': 'self',
                'user_id': False,  # sin comercial: la revisa el abogado (no el usuario portal)
            })
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
        if role == 'proveedor':
            company.sudo().write({'en_is_public_provider': True})
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
            offer = payload.get('offer') or {}
            lines = []
            for ln in (offer.get('lines') or []):
                prod = _find_product(ln.get('prod'))
                lines.append((0, 0, {
                    'product_id': prod.id if prod else False,
                    'packaging': 'isotanque' if ln.get('env') == 'Isotanque' else 'isomodulo',
                    'qty': float(ln.get('qty') or 0), 'unit_price': float(ln.get('price') or 0),
                }))
            off = env['en.supply.offer'].sudo().create({
                'supplier_id': company.id, 'state': 'published',
                'validity': VALIDITY.get(offer.get('vigencia'), '3m'),
                'port': offer.get('port') or False,
                'flete': float(offer.get('flete') or 0), 'seguro': float(offer.get('seguro') or 0),
                'line_ids': lines,
            })
            created['offer'] = off.id
            for cname in (payload.get('clients') or []):
                cli = env['res.partner'].sudo().create({
                    'name': cname, 'company_type': 'company',
                    'contact_type_id': (_contact_type('Cliente nacional').id or False),
                })
                try:
                    Rel.create({'client_id': cli.id, 'supplier_id': company.id,
                                'initiated_by': 'supplier', 'state': 'pending'})
                    created['clients'] += 1
                except Exception:
                    pass
            # Difundir oferta: clientes que aceptan recibir ofertas
            created['diffused'] = 0
            for cname in (payload.get('diffused') or []):
                cli = env['res.partner'].sudo().create({
                    'name': cname, 'company_type': 'company', 'en_accepts_offers': True,
                    'contact_type_id': (_contact_type('Cliente nacional').id or False),
                })
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
                prod = _find_product(sol.get('product'))
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
                    lp = _find_product(ln.get('prod'))
                    pkg = ln.get('env')
                    lines.append((0, 0, {
                        'sequence': (i + 1) * 10,
                        'product_id': lp.id if lp else False,
                        'product_name': ln.get('prod') or False,
                        'qty': float(ln.get('qty') or 0),
                        'packaging': pkg if pkg in ('isotanque', 'isomodulo') else False,
                    }))
                if lines:
                    vals['en_request_line_ids'] = lines
                env_pkg = sol.get('envase')
                if env_pkg in ('isotanque', 'isomodulo'):
                    vals['en_packaging_type'] = env_pkg
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
                prod = _find_product(sol.get('product'))
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
                sup_name = (payload.get('cpInfo') or {}).get('name') \
                    or 'Proveedor (registrado por %s)' % (company.name or 'cliente')
                supplier = env['res.partner'].sudo().create({
                    'name': sup_name,
                    'company_type': 'company',
                    'contact_type_id': (_contact_type('Proveedor extranjero').id or False),
                })
                # Lead de acreditación del proveedor (lo registró el cliente) para
                # que entre a la bandeja del abogado y pueda acreditarse.
                Lead.create({
                    'name': sup_name, 'partner_id': supplier.id, 'type': 'opportunity',
                    'en_initiated_by': 'counterparty', 'user_id': False,
                    'en_inviter_partner_id': company.id,
                })
            elif cphas == 'si' and cp == 'invitar' and payload.get('inviteEmail'):
                rel = Rel.create({'client_id': company.id,
                                  'supplier_id': company.id,  # placeholder; se reemplaza al aceptar
                                  'initiated_by': 'client', 'state': 'invited'}) if False else False
                inv = Inv.create({'email': payload.get('inviteEmail'), 'expected_role': 'supplier',
                                  'inviter_partner_id': company.id, 'state': 'sent'})
                created['invitations'].append(inv.id)

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
