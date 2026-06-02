# Part of Odoo. See LICENSE file for full copyright and licensing details

import json
import logging
import base64
from datetime import datetime

from dateutil.relativedelta import relativedelta
from odoo import http, _
from odoo.addons.website.controllers import form
from odoo.addons.website_crm.controllers.website_form import WebsiteForm as WebsiteForm2
from odoo.exceptions import ValidationError
from odoo.http import Stream, request, Response
from odoo.addons.base.models.ir_qweb_fields import nl2br_enclose

_logger = logging.getLogger(__name__)

operation_banner_img = {
    "logistic": "banner_logistica_3.svg",
    "import": "banner_importaciones_2.svg",
    "accreditation": "acreditacion_2.svg",
    "accreditation_business": "acreditacion_2.svg",
}
SPG = 20  # Proveedores Per Page
SPR = 4  # Proveedores Per Row


def get_render_values(kw):
    country = request.env["res.country"].sudo()
    contact_types = (
        request.env["res.partner.contact.type"]
        .sudo()
        .search([])
    )
    providers = (
        request.env["res.partner"]
        .sudo()
        .search([("contact_type_id.type_of_contact", "=", "Supplier")])
    )
    customers = (
        request.env["res.partner"]
        .sudo()
        .search([("contact_type_id.type_of_contact", "=", "Customer")])
    )
    register_type = kw.get("type", "accreditation")
    banner = operation_banner_img.get(register_type, operation_banner_img["accreditation"])
    alimentos_de_importacion = request.env['product.template'].sudo().search_read(
        [('product_type', '=', 'alimento'), ('de_importacion', '=', True)], ['id', 'name'])

    product_selected = request.session.get('product_selected', [])

    render_values = {
        "countries": country.get_website_sale_countries(),
        "states": request.env["res.country.state"].sudo().search([]),
        "contact_types": contact_types,
        "partner_id": request.env.user.partner_id.id,
        "providers": providers,
        "customers": customers,
        "banner": banner,
        "register_type": register_type,
        "registered_user": False,
        "productos_seleccionados_ids": product_selected,
        'alimentos_de_importacion': json.dumps(alimentos_de_importacion),
    }
    crm_lead_exists = request.env["crm.lead"].sudo().search([
        ("partner_id", "=", request.env.user.commercial_partner_id.id)
    ], limit=1)
    render_values["crm_lead_exists"] = bool(crm_lead_exists)

    if "uid" in request.context:
        render_values["registered_user"] = True

    return render_values


def loged_in():
    user = request.env.user
    if user._is_public():
        return request.redirect("/web/login")


class WebsiteForm(form.WebsiteForm):

    @http.route('/check_duplicate_nit', type="json", auth="public", website=True)
    def check_duplicate_nit(self, nit, **kw):
        partner = request.env['res.partner'].sudo().search([('vat', '=', nit), ('is_company', '=', True)])
        return not bool(partner)

    @http.route('/check_file_type', type="json", auth="public", website=True)
    def check_file_type(self, config_param, file_type, **kw):
        attachment_id_str = request.env['ir.config_parameter'].sudo().get_param(f'{config_param}.attachment_id')
        if attachment_id_str:
            try:
                attachment_id = int(attachment_id_str)
            except ValueError:
                return
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment and attachment.mimetype:
                return attachment.mimetype == file_type

    @http.route("/get_form_management_types", type="json", auth="public", website=True)
    def get_form_management_types(self, contact_type_id=None, **kw):
        res = {}
        if contact_type_id:
            contact_types = (
                request.env["res.partner.contact.type"]
                .sudo()
                .search([("id", "=", int(contact_type_id))])
            )
            res = {str(x.id): x.name for x in contact_types.management_type_ids}
        return res

    @http.route("/get_form_states", type="json", auth="public", website=True)
    def get_form_states(self, country_code=None, **kw):
        res = {}
        if country_code:
            states = (
                request.env["res.country.state"]
                .sudo()
                .search([("country_id.code", "=", country_code)])
            )
            res = {str(x.id): x.name for x in states}
        return res

    @http.route("/get_form_cities", type="json", auth="public", website=True)
    def get_form_cities(self, state_id=None, **kw):
        res = {}
        if state_id:
            states = (
                request.env["res.city"]
                .sudo()
                .search([("state_id", "=", int(state_id))])
            )
            res = {str(x.id): x.name for x in states}
        return res
    
    def _get_partner_data(self, kwargs):
        partner_data = {
                "name": kwargs.get("parent_company_name"),
                "vat": kwargs.get("nit", False),
                "dap": kwargs.get("dap", False),
                "company_type": 'company',
                "phone": kwargs.get("phone"),
                "email": kwargs.get("parent_company_email"),
                "country_id": int(kwargs.get("country", request.env.ref('base.cu').id)),
                "state_id": int(kwargs.get("state",False)),
                "street": kwargs.get("address"),
                "license_holder": kwargs.get("license_holder"),
                "management_type_id": int(kwargs.get("fgne_type", False)),
                "deed_number": int(kwargs.get("deed_input_number", False)),
                "deed_date": kwargs.get("deed_input_date"),
                "contact_type_id": int(kwargs.get("contact_type", False)),
            }
        if kwargs.get("supplier_type"):
            if kwargs.get("supplier_type") == 'Productor':
                category_id = request.env.ref('pyxel_import_backend.res_partner_category_producer').id  
                partner_data['category_id'] = [(4, category_id)]   
            elif kwargs.get("supplier_type") == 'Comerciante':
                category_id = request.env.ref('pyxel_import_backend.res_partner_category_businessman').id
                partner_data['category_id'] = [(4, category_id)]   

        if kwargs.get("city"):
            city_id = int(kwargs.get("city",False))
            partner_data['city'] = request.env["res.city"].sudo().search([("id", "=", city_id)], limit=1).name
            partner_data['city_id'] = city_id
        return partner_data

    def website_form(self, model_name, **kwargs):
        tipo_registro = kwargs.get("register_type") 
        public_user = request.env.user.sudo()

        if model_name == "crm.lead" and tipo_registro == "accreditation":
            crm_lead_exists = request.env["crm.lead"].sudo().search([
                        ("partner_id", "=", request.env.user.commercial_partner_id.id)
                        ], limit=1)
            if crm_lead_exists:
                return Response(
                    json.dumps({'error': 'Usted ya se ha acreditado, para volver a acreditarse debe hacerlo con un usuario nuevo que no esté acreditado'}),
                    status=400,
                    headers={'Content-Type': 'application/json'}
                )
            valid_nit = self.check_duplicate_nit(kwargs.get("nit", False))
            if not valid_nit:
                return Response(
                        json.dumps({'error': 'El NIT ingresado ya existe. Verifique la información antes de continuar'}),
                        status=400,
                        headers={'Content-Type': 'application/json'}
                    )

            partner_data = self._get_partner_data(kwargs)
            partner = request.env["res.partner"].sudo().create(partner_data)
            public_user.partner_id.write({"name": kwargs["partner_name"], "parent_id": partner.id})
            request.params.update({'partner_id': partner.id, 'email_from': kwargs.get("parent_company_email"), 'partner_name': kwargs.get("parent_company_name")})
            kwargs.update({'partner_id': partner.id, 'email_from': kwargs.get("parent_company_email"), 'partner_name': kwargs.get("parent_company_name")})

            # 1. Filtrar las claves que empiezan con 'files'
            file_keys = [key for key in kwargs.keys() if key.startswith('legal_documentation')]

            if kwargs.get('ficha_cliente[0][0]'):
                file_keys.append('ficha_cliente[0][0]')
            if kwargs.get('planilla_proveedor[0][0]'):
                file_keys.append('planilla_proveedor[0][0]')
            if kwargs.get('cuban_partner[0][0]'):
                file_keys.append('cuban_partner[0][0]')

            for file_key in file_keys:
                file = kwargs.get(file_key, {})
                # for file in request.httprequest.files.getlist(file_key):
                file.seek(0)  # Rebobinar al inicio del archivo, xq sino el file.read() devuelve b'', o sea que está vacío
                request.env['ir.attachment'].sudo().create({
                    "name": file.filename,
                    "datas": base64.b64encode(file.read()),
                    "res_model": "res.partner",
                    "res_id": partner.id,
                    'type': 'binary',
                    'mimetype': file.mimetype,
                })

        elif model_name == "sale.order" and tipo_registro == "import":
            # Crear la Cotización a partir de la solicitud de importación
            order_line = kwargs.get("productRequired", "")

            request.params.update({'partner_id': public_user.partner_id.parent_id.id, 'order_line': order_line})
            kwargs.update({'partner_id': public_user.partner_id.parent_id.id, 'order_line': order_line})
            request.params.pop('productRequired')
            request.params.pop('register_type')
            kwargs.pop('productRequired')
            kwargs.pop('register_type')

        res = super(WebsiteForm, self).website_form(model_name, **kwargs)
        _logger.info("Todas las claves disponibles en kwargs: %s", kwargs.keys())

        request.session['product_selected'] = []

        return res

    def insert_record(self, request, model, values, custom, meta=None):
        is_lead_model = model.model == 'crm.lead'
        if is_lead_model:
            visitor_sudo = request.env['website.visitor']._get_visitor_from_request()
            
            if 'company_id' not in values:
                values['company_id'] = request.website.company_id.id
            lang = request.context.get('lang', False)
            values['lang_id'] = values.get('lang_id') or request.env['res.lang']._lang_get_id(lang)

        if model.model == 'sale.order':
            values['user_id'] = None
            nomenclature_ids = request.env["product.product"].sudo().search([('product_tmpl_id', 'in', values['order_line'])]).ids
            values['order_line'] = [(0,0, {"product_id": product_id}) for product_id in nomenclature_ids]

        if is_lead_model or model.model == 'sale.order':
            record = request.env[model.model].sudo().with_context(
                mail_create_nosubscribe=True,
            ).create(values)
            if custom or meta:
                _custom_label = "%s\n___________\n\n" % _("Other Information:")  # Title for custom fields
                default_field = model.website_form_default_field_id
                default_field_data = values.get(default_field.name, '')
                custom_content = (default_field_data + "\n\n" if default_field_data else '') \
                    + (_custom_label + custom + "\n\n" if custom else '') \
                    + (self._meta_label + "\n________\n\n" + meta if meta else '')

                # If there is a default field configured for this model, use it.
                # If there isn't, put the custom data in a message instead
                if default_field.name:
                    if default_field.ttype == 'html':
                        custom_content = nl2br_enclose(custom_content)
                    record.update({default_field.name: custom_content})

            result = record.id
        else:
            # Llama al método insert_record del website, no del website_crm
            result = super(WebsiteForm2, self).insert_record(request, model, values, custom, meta=meta)

        if is_lead_model and visitor_sudo and result:
            lead_sudo = request.env['crm.lead'].browse(result).sudo()
            if lead_sudo.exists():
                vals = {'lead_ids': [(4, result)]}
                if not visitor_sudo.lead_ids and not visitor_sudo.partner_id:
                    vals['name'] = lead_sudo.contact_name
                visitor_sudo.write(vals)
        return result
    
class ControllerTest(http.Controller):

    @http.route('/business-register/update_session_products', type='json', auth='user')
    def actualizar_sesion(self, selected_products, action=None):
        """
        Actualiza la variable de sesión `product_selected` con los valores seleccionados.
        Puede agregar o eliminar productos según el parámetro `action`. Si no se le pasa por param, por defecto agrega.
        """
        action = action or "add"

        if not isinstance(selected_products, list):
            selected_products = []
        else:
            selected_products = [
                int(p) for p in selected_products if isinstance(p, (int, str)) and str(p).isdigit()
            ]

        # Obtén la lista de productos previamente seleccionados de la sesión
        previous_products = request.session.get('product_selected', [])

        # Asegúrate de que previous_products sea una lista válida
        if not isinstance(previous_products, list):
            previous_products = []
        else:
            # Convierte todos los elementos a enteros si son válidos
            previous_products = [
                int(p) for p in previous_products if isinstance(p, (int, str)) and str(p).isdigit()
            ]
        if action == "add":

            updated_products = list(set(previous_products + selected_products))

        elif action == "remove":

            updated_products = [p for p in previous_products if p not in selected_products]
        else:
            return {'status': 'error', 'message': f'Acción no válida: {action}'}

        # Actualizar la sesión con los nuevos productos seleccionados
        request.session['product_selected'] = updated_products
        request.session.modified = True

        return {'status': 'success', 'message': 'Sesión actualizada correctamente'}

    @http.route('/business-register-thanks', type='http', auth="public", website=True)
    def business_register_thanks(self, **kw):
        crm_lead_exists = request.env["crm.lead"].sudo().search([
            ("partner_id", "=", request.env.user.commercial_partner_id.id)
        ], limit=1)
        days_in_process = 'False'

        if crm_lead_exists: 
            is_accredited = crm_lead_exists.partner_id.is_accredited

            if not is_accredited:
                days_in_process = (datetime.now() - crm_lead_exists.create_date).days
            
        return request.render('pyxel_import_website.business_register_thanks', {"days_in_process": days_in_process})

    @http.route('/business-register', type='http', auth="public", website=True)
    def controller_register(self, **kw):
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect(f"/web/login?redirect=/business-register?type={kw.get('type', 'accreditation')}")

        crm_lead_exists = request.env["crm.lead"].sudo().search([
            ("partner_id", "=", request.env.user.commercial_partner_id.id)
        ], limit=1)
        is_accredited = False
        
        if crm_lead_exists:
            is_accredited = crm_lead_exists.partner_id.is_accredited
        if kw.get('type') == 'accreditation' and crm_lead_exists:
            if is_accredited:
                return request.redirect('/my/home')
            else:
                return request.redirect('/business-register-thanks')

        render_values = get_render_values(kw)
        
        
        if kw.get('type') == 'import':
            # Si no se ha realizado el formulario de acreditación
            if not crm_lead_exists:
                return request.render('pyxel_import_website.waiting_for_active_contract')
            # Si no es Cliente nacional no puede solicitar una importación
            if request.env.user.commercial_partner_id.contact_type_id.type_of_contact == "Client" and request.env.user.commercial_partner_id.contact_type_id.nationality_type == 'national':
                pass
            else:
                return request.render('pyxel_import_website.you_are_not_a_national_client', {'contact_type': request.env.user.commercial_partner_id.contact_type_id.name})
            # Si realizó el formulario de acreditación pero no está acreditado
            if not is_accredited:
                return request.redirect('/business-register-thanks')
            return request.render('pyxel_import_website.import_registration', render_values)
        
        return request.render('pyxel_import_website.business_registration', render_values)


class ProductSearchController(http.Controller):

    @http.route(['/nomenclador', '/nomenclador/page/<int:page>'], type='http', auth='public', website=True)
    def nomenclador_view(self, search=None, page=1, **kwargs):
        loged_in()
        """Renderiza la vista con el buscador y los resultados paginados."""
        alimentos_de_importacion = request.env['product.template'].sudo().search(
            [('product_type', '=', 'alimento'), ('de_importacion', '=', True)])
        filters = [('product_type', '=', 'alimento')]
        domain = [('name', 'ilike', search)] if search else []
        domain += filters

        from_view = kwargs.get('from', None)

        total_products = request.env['product.template'].sudo().search_count(domain)

        base_url = "/nomenclador"

        url_args = {}
        if from_view:
            url_args['from'] = from_view
        if search:
            url_args['search'] = search

        pager = request.website.pager(
            url=base_url,
            url_args=url_args,
            total=total_products,
            page=page,
            step=10,  # 10 productos por página
            scope=3
        )

        products = request.env['product.template'].sudo().search(domain, limit=10, offset=(page - 1) * 10)

        return request.render('pyxel_import_website.nomenclador_template', {
            'products': products,
            'search': search,
            'from_view': from_view,
            'alimentos_de_importacion': alimentos_de_importacion,
            'pager': pager,
        })

class DownloadFileController(http.Controller):

    @http.route('/descargar/<string:file_name>', type='http', auth='public')
    def download_file(self,file_name, **kw):
        if file_name not in ['load_products', 'solicitud', 'ficha_cliente_estatal', 'ficha_cliente_fgne_tcp','perfil_proveedor', 'cuban_partner']:
            return request.redirect('/web')
        attachment_id_str = request.env['ir.config_parameter'].sudo().get_param(f'{file_name}.attachment_id')
        if attachment_id_str:
            try:
                attachment_id = int(attachment_id_str)
            except ValueError:
                return request.redirect('/web')
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment and attachment.datas:
                return Stream.from_attachment(attachment).get_response(as_attachment=True)
        return request.redirect('/web')
