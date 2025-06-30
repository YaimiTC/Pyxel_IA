# Part of Odoo. See LICENSE file for full copyright and licensing details

import json
import logging
import io
import base64
from datetime import datetime

from dateutil.relativedelta import relativedelta
from werkzeug.exceptions import NotFound

from odoo import SUPERUSER_ID
from odoo import fields, tools
from odoo import http
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.website.controllers.form import WebsiteForm
from odoo.addons.website.controllers.main import QueryURL
from odoo.addons.website_sale.controllers.main import TableCompute
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.osv import expression
from odoo.tools import lazy

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
    providers = (
        request.env["res.partner"]
        .sudo()
        .search([("x_studio_type_of_contact", "=", "Supplier")])
    )
    customers = (
        request.env["res.partner"]
        .sudo()
        .search([("x_studio_type_of_contact", "=", "Customer")])
    )
    register_type = kw.get("type", "accreditation")
    banner = operation_banner_img.get(register_type, operation_banner_img["accreditation"])
    productos_de_importacion = request.env['product.template'].sudo().search([('de_importacion', '=', True)])
    alimentos_de_importacion = request.env['product.template'].sudo().search([('product_type', '=', 'alimento'),('de_importacion', '=', True)])
    electronicos_de_importacion = request.env['product.template'].sudo().search([('product_type', '=', 'electronico'),('de_importacion', '=', True)])
    
    product_selected = request.session.get('product_selected', [])
    electronic_selected = request.session.get('electronic_selected', [])
    alimentos_de_importacion_data = [{'id': product.id, 'name': product.name} for product in alimentos_de_importacion]
    electronicos_de_importacion_data = [{'id': product.id, 'name': product.name} for product in electronicos_de_importacion]


    render_values = {
        "countries": country.get_website_sale_countries(),
        "states": request.env["res.country.state"].sudo().search([]),
        "providers": providers,
        "customers": customers,
        "banner": banner,
        "register_type": register_type,
        "registered_user": False,
        "productos_de_importacion": productos_de_importacion,
        "alimentos_de_importacion": alimentos_de_importacion,
        "electronicos_de_importacion":electronicos_de_importacion,
        "productos_seleccionados_ids":product_selected,
        "electronic_selected_ids":electronic_selected,
        # "electronicos_de_importacion": electronicos_de_importacion,
        'alimentos_de_importacion': json.dumps(alimentos_de_importacion_data),
        'electronicos_de_importacion': json.dumps(electronicos_de_importacion_data),

    }
    domain_ids = [request.env.user.partner_id.id]
    if request.env.user.partner_id.parent_id:
        domain_ids.append(request.env.user.partner_id.parent_id.id)
    crm_lead_exists = request.env["crm.lead"].sudo().search([
        ("partner_id", "in", domain_ids)
    ], limit=1)
    render_values["crm_lead_exists"] = bool(crm_lead_exists)

    if "uid" in request.context:
        render_values["registered_user"] = True

    return render_values


class WebsiteForm(WebsiteForm):

    @http.route("/get_form_states", type="json", auth="public", website=True)
    def get_form_states(self, country_id=None, **kw):
        res = {}
        if country_id:
            states = (
                request.env["res.country.state"]
                .sudo()
                .search([("country_id", "=", int(country_id))])
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

    @http.route(
        ["/business-register"],
        type="http",
        auth="public",
        methods=["POST", "GET"],
        website=True,
    )
    def business_register(self, **kw):
        render_values = get_render_values(kw)
        x_studio_license_holder = kw.get('x_studio_license_holder')
        if x_studio_license_holder:
            request.env['res.partner'].create({
                'x_studio_license_holder': x_studio_license_holder,
            })
        if render_values["registered_user"]:
            if render_values["register_type"] == "accreditation":
                return request.render(
                    "pyxel_import_website.business_register_thanks", render_values
                )
            if (
                    render_values["register_type"] == "import"
                    and request.env.user.partner_id.x_studio_type_of_contact == "Supplier"
            ):
                customers = (
                    request.env["res.partner"]
                    .sudo()
                    .search([("x_studio_type_of_contact", "=", "Customer")])
                )
                render_values["customers"] = customers
                return request.render(
                    "pyxel_import_website.import_registration", render_values
                )

            # if(
            #     render_values["register_type"] == "import"
            #     and request.env.user.partner_id.x_studio_type_of_contact == "Customer"
            # ):
            #    productRequired = kw.get('productRequired')

        return request.render(
            "pyxel_import_website.business_registration", render_values
        )

    def website_form(self, model_name, **kwargs):
        res = super(WebsiteForm, self).website_form(model_name, **kwargs)
        _logger.info("Todas las claves disponibles en kwargs: %s", kwargs.keys())
        tipo_registro = kwargs.get("register_type") 
    

        if model_name == "x_import":
            if tipo_registro == "logistic":
                pass
            else:
                id_import = eval(res.response[0])
                import_rec = request.env["x_import"].sudo().browse(id_import["id"])
                supplier = request.env.user.sudo().partner_id.id
                
                def process_file(field_name):
                    _logger.info("Procesando campo: %s", field_name)
                    file_storage = kwargs.get(f'{field_name}[0][0]', False)
                    _logger.info("Tipo de file_storage para %s: %s", field_name, type(file_storage))
                    
                    if file_storage:
                        if hasattr(file_storage, 'filename'):
                            _logger.info("Nombre del archivo: %s", file_storage.filename)
                            filename = file_storage.filename
                        else:
                            filename = f'documento_{field_name}.pdf'
                            
                        if hasattr(file_storage, 'seek') and callable(file_storage.seek):
                            try:
                                file_storage.seek(0)
                                _logger.info("Archivo rebobinado correctamente")
                            except Exception as e:
                                _logger.error("Error al rebobinar: %s", str(e))
                    
                        try:
                            if hasattr(file_storage, 'read') and callable(file_storage.read):
                                file_content = file_storage.read()
                                _logger.info("Tamaño del contenido leído: %s bytes", len(file_content))
                            else:
                                _logger.warning("El objeto no tiene método read()")
                                file_content = b''
                        except Exception as e:
                            _logger.error("Error leyendo el archivo: %s", str(e))
                            file_content = b''
                    else:
                        _logger.warning("No se encontró el objeto file_storage para %s", field_name)
                        file_content = b''
                        filename = f'documento_{field_name}.pdf'
                    
                    if file_content == b'' and hasattr(request, 'httprequest') and hasattr(request.httprequest, 'files'):
                        _logger.info("Intentando método alternativo para %s...", field_name)
                        file_found = False
                        
                        for key in request.httprequest.files:
                            _logger.info("Revisando clave: %s", key)
                            if field_name.replace('x_studio_', '') in key:
                                alt_file = request.httprequest.files[key]
                                try:
                                    if hasattr(alt_file, 'seek'):
                                        alt_file.seek(0)
                                    alt_content = alt_file.read()
                                    if alt_content and len(alt_content) > 0:
                                        file_content = alt_content
                                        if hasattr(alt_file, 'filename'):
                                            filename = alt_file.filename
                                        _logger.info("Contenido obtenido por método alternativo: %s bytes", len(file_content))
                                        file_found = True
                                        break
                                except Exception as e:
                                    _logger.error("Error en método alternativo: %s", str(e))
                        
                        if not file_found:
                            _logger.warning("No se encontró un archivo válido para %s", field_name)
                    
                    if file_content and len(file_content) > 0:
                        file_data_base64 = base64.b64encode(file_content)
                        _logger.info("Datos codificados en base64 para %s: %s bytes", field_name, len(file_data_base64))
                        return {
                            field_name: file_data_base64,
                            f"{field_name}_filename": filename
                        }
                    else:
                        _logger.warning("No hay datos para codificar en base64 para %s", field_name)
                        return {}
                    
                #agregar los campos de tipo pdf en el formulario...
                file_fields = [
                    'x_studio_oferta_firmada',
                    'x_studio_bill_of_lading_bl',
                    'x_studio_x_comercial_invoice', 
                    'x_studio_package_list', 
                    'x_studio_export_certify', 
                    'x_studio_quality_certify', 
                    'x_studio_certificate_of_origin_co'
                ]
                
                values = {
                    "x_studio_origin_country": eval(kwargs.get("Id de país", "None")),
                    "x_studio_certifies_receipt_load": kwargs.get("Tipo de envío de la carga", None),
                    "x_studio_bill_of_landing_number": kwargs.get("x_studio_bill_of_landing_number", ""),
                    "x_studio_supplier": supplier,
                    
                }

                for field in file_fields:
                    file_values = process_file(field)
                    values.update(file_values)

                import_rec.write(values)
                
                if "Cliente nuevo" not in kwargs and model_name == "x_import":
                    cliente = request.env["res.partner"].sudo().browse(int(kwargs["customer_id"]))
                    import_rec.write({'x_studio_form_note': (
                                                            import_rec.x_studio_form_note or '') + "Cliente: " + cliente.name + "\nNIT: " + (
                                                            cliente.vat or '')})
                    
                #CREACIÓN DE LA ORDEN DE COMPRA ASOCIACIÓN AL LA IMPORTACION (x_import)
                purchase_order_vals = {
                    "x_studio_client": int(kwargs["customer_id"]),  
                    "partner_id": supplier,                            
                    "x_studio_import_id": import_rec.id,               
                    "receipt_status": "pending",
                }
                purchase_order = request.env["purchase.order"].sudo().create(purchase_order_vals)
                _logger.info("Orden de compra creada con ID: %s", purchase_order.id)
                
        if model_name == "crm.lead":
            id_crm = eval(res.response[0])
            product_onure_ids = [int(id.strip()) for id in kwargs.get("productOnure", "").split(",") if id.strip().isdigit()]
            product_nomenclature_ids = [int(id.strip()) for id in kwargs.get("productRequired", "").split(",") if id.strip().isdigit()]

            public_user = request.env.user
            # Crear la Cotización a partir de la solicitud de importación
            if tipo_registro == "import":
                nomenclature_ids = request.env["product.product"].sudo().with_user(SUPERUSER_ID).search([('product_tmpl_id', 'in', product_nomenclature_ids)]).ids
                onure_ids = request.env["product.product"].sudo().with_user(SUPERUSER_ID).search([('product_tmpl_id', 'in', product_onure_ids)]).ids
                order_line = [(0,0, {"product_id": product_id}) for product_id in nomenclature_ids] + [(0,0, {"product_id": product_id}) for product_id in onure_ids] 
                order = request.env["sale.order"].sudo().with_user(SUPERUSER_ID).create(
                    {
                        "partner_id": public_user.sudo().partner_id.id,
                        "order_line": order_line,
                    }
                )

            # if "uid" not in request.context:
            if not public_user.sudo().partner_id.parent_id:
                partner = (
                    request.env["res.partner"].sudo().with_user(SUPERUSER_ID)
                    .create(
                        {
                            "name": kwargs["company"],
                            "company_type": 'company',
                            # "phone": kwargs["phone"],
                            "email": kwargs["company_email"],
                            "x_studio_type_of_contact": 'Supplier' if kwargs["Register as"] == 'Provider' else 'Customer',
                            "child_ids": [(4, public_user.sudo().partner_id.id)],
                             
                        }
                    )
                )
            crm_lead = request.env["crm.lead"].with_user(SUPERUSER_ID).sudo().browse(id_crm["id"])
            crm_lead.sudo().write({
                    # "partner_id": partner.sudo().id,
                    "x_studio_product_onure": [(6, 0, product_onure_ids)],
        
                    }),
                
                # partner.write({"child_ids": [(4, public_user.sudo().partner_id.id)]})
                # public_user.sudo().partner_id.write({"parent_id":partner.sudo().id})

        if kwargs.get('productRequired') or kwargs.get('productOnure'):
            # Evitar doble creación si el formulario ya es de 'x_import'
            if model_name == 'x_import':
                # Aquí podemos saltarnos la creación manual porque el super() ya loo creó
                pass
            else:

                product_ids_str = kwargs.get('productRequired') if kwargs.get('productRequired') else kwargs.get('productOnure')
                product_ids_list = product_ids_str.split(
                    ',')  # divide la cadena en una lista de strings usando la coma como delimitador porque al ser un campo many2many toma la coma entre los elementos y da

                # Convertir los IDs a enteros usando una comprensión de lista
                productos_ids = [int(pid.strip()) for pid in product_ids_list if pid.strip().isdigit()]

                start_date = datetime.now()
                end_date = start_date + relativedelta(months=8)

                new_partner_supplier = None

                if kwargs.get('other_provider') == 'Yes':
                    new_partner_supplier = request.env['res.partner'].sudo().create({
                        'name': kwargs.get('other_provider_name'),
                        "company_type": 'company',
                        'x_studio_license_holder': kwargs.get('x_studio_license_holder'),
                        'email': kwargs.get('other_provider_company_email'),
                        'street': kwargs.get('other_provider_address'),
                        'country_id': int(kwargs.get('other_provider_country')),
                        'x_studio_type_of_contact': 'Supplier',

                    })

                supplier_id = None

                if kwargs.get('provider_purchase'):
                    supplier_id = int(kwargs.get('provider_purchase'))
                    supplier = request.env['res.partner'].sudo().browse(supplier_id)
                    origin_country_id = supplier.country_id.id


                else:
                    origin_country_value = kwargs.get("Id de país")
                    if origin_country_value and origin_country_value.isdigit():
                        origin_country_id = int(origin_country_value)
                    elif new_partner_supplier:
                        origin_country_id = new_partner_supplier.country_id.id
                    else:
                        origin_country_id = None

                if supplier_id is not None:
                    import_supplier = supplier
                elif new_partner_supplier is not None:
                    import_supplier = new_partner_supplier
                else:
                    import_supplier = request.env.user.partner_id.company_id

                studio_client = kwargs.get("customer_id") if kwargs.get(
                    "customer_id") else request.env.user.partner_id.parent_id.id

                if studio_client:

                    product_onure_ids = [
                        int(id.strip())
                        for id in kwargs.get("productOnure", "").split(",")
                        if id.strip().isdigit()
                    ]

                    # request.env['x_import'].sudo().create({
                    #     'x_studio_form_note': kwargs.get('productRequired'),
                    #     "x_studio_product_onure": [(6, 0, product_onure_ids)],
                    #     # 'x_studio_producto_a_importar': [(6, 0, productos_ids)],
                    #     'x_studio_supplier': import_supplier.id,
                    #     'x_studio_origin_country': origin_country_id,
                    #     'x_studio_client': studio_client,
                    #     'x_studio_date_start': start_date,
                    #     'x_studio_date_stop': end_date,
                    #     # 'provider_purchase': kwargs.get('provider_purchase'),
                    #     # 'user_name': request.env.user.name,
                    #     # "company": kwargs.get("company"),
                    #     # "company_email": kwargs.get("company_email"),

                    # })

            # public_user.sudo().partner_id.write({"parent_id":partner.sudo().id})

        # bandera
        # public_user.partner_id.sudo().write({"has_accredited_company": True})
        
        
        request.session['product_selected'] =[]
        
        request.session['electronic_selected'] =[]

        return res

    def _handle_website_form(self, model_name, **kwargs):

        res = super(WebsiteForm, self)._handle_website_form(model_name, **kwargs)
        # id_crm = eval(res)
        # crm_lead = request.env['crm.lead'].browse(id_crm['id'])
        if kwargs.get("password") != kwargs.get("confirm_password"):
            raise ValidationError(["password", "confirm_password"])
            return json.dumps(
                {
                    "error_fields": ["password", "confirm_password"],
                    "error": "Passwords do not match; please retype them.",
                }
            )

        return res

    # def _get_provider_search_domain(self, search):
    #     domain = [
    #         ("x_studio_type_of_contact", "=", "Supplier"),
    #         ("is_fx_published", "=", True),
    #     ]

    #     if search:
    #         for srch in search.split(" "):
    #             domain += [("name", "ilike", srch)]
    #     return domain

    # def _get_provider_catalog_search_domain(self, provider, search):
    #     # domain = [
    #     #     ("x_studio_type_of_contact", "=", "Supplier")
    #     # ]
    #     domain = [("type", "in", ["consu", "product"])]
    #     if search:
    #         for srch in search.split(" "):
    #             domain += [("name", "ilike", srch)]
    #     if provider:
    #         domain += [
    #             "|",
    #             ("seller_ids.partner_id", "=", provider),
    #             ("seller_ids.partner_id", "=", provider),
    #         ]
    #     return domain

    # def _shop_get_query_url_kwargs(self, category, search, min_price, max_price, attrib=None, order=None, tags=None,
    #                                **post):
    #     return {
    #         "category": category,
    #         "search": search,
    #         "attrib": attrib,
    #         "tags": tags,
    #         "min_price": min_price,
    #         "max_price": max_price,
    #         "order": order,
    #     }

    # def _shop_lookup_products(
    #         self, attrib_set, options, post, search, website, partner):
    #     order_s = (
    #             post.get("order")
    #             or request.env["website"].get_current_website().shop_default_sort
    #     )
    #     order = "is_published desc, %s, id desc" % order_s

    #     # No limit because attributes are obtained from complete product list
    #     product_count, details, fuzzy_search_term = website._search_with_fuzzy(
    #         "products_only",
    #         search,
    #         limit=None,
    #         order=order,
    #         options=options,
    #     )
    #     search_result = (
    #         details[0]
    #         .get("results", request.env["product.template"])
    #         .with_context(bin_size=True)
    #     )
    #     search_result = search_result.filtered(
    #         lambda a: partner in a.seller_ids.mapped("partner_id").ids
    #     )
    #     return (fuzzy_search_term, len(search_result), search_result)

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


    @http.route('/business-register/update_session_electronics', type='json', auth='user')
    def actualizar_sesion_electronicos(self, selected_electronics, action=None):
        """
        Actualiza la variable de sesión `electronic_selected` con los valores seleccionados.
        Puede agregar o eliminar productos según el parámetro `action`. Si no se le pasa por param, por defecto agrega.
        """
        action = action or "add"

        if not isinstance(selected_electronics, list):
            selected_electronics = []
        else:
            selected_electronics = [
                int(p) for p in selected_electronics if isinstance(p, (int, str)) and str(p).isdigit()
            ]

        # Obtén la lista de productos previamente seleccionados para electrónicos
        previous_products = request.session.get('electronic_selected', [])

        # Asegúrate de que previous_products sea una lista válida
        if not isinstance(previous_products, list):
            previous_products = []
        else:
            previous_products = [
                int(p) for p in previous_products if isinstance(p, (int, str)) and str(p).isdigit()
            ]

        if action == "add":
            updated_products = list(set(previous_products + selected_electronics))
        elif action == "remove":
            updated_products = [p for p in previous_products if p not in selected_electronics]
        else:
            return {'status': 'error', 'message': f'Acción no válida: {action}'}

        # Actualizar la sesión con los nuevos productos seleccionados
        request.session['electronic_selected'] = updated_products
        request.session.modified = True

        return {'status': 'success', 'message': 'Sesión de electrónicos actualizada correctamente'}
        
    @http.route('/business-register', type='http', auth="public", website=True)
    def controller_register(self, **kw):
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=/business-register?type=accreditation')

        if kw.get('type') == 'accreditation':
            domain_ids = [request.env.user.partner_id.id]

        if kw.get('type') == 'accreditation':

            domain_ids = [request.env.user.partner_id.id]

            if request.env.user.partner_id.parent_id:
                domain_ids.append(request.env.user.partner_id.parent_id.id)

            crm_lead_exists = request.env["crm.lead"].sudo().search([
                ("partner_id", "in", domain_ids)
            ], limit=1)

            if crm_lead_exists:
                return request.redirect('/business-register-thanks')

        render_values = get_render_values(kw)

        partner = request.env.user.partner_id

        if partner.parent_id:
            contact_type = partner.parent_id.x_studio_type_of_contact
        else:
            contact_type = partner.x_studio_type_of_contact

        if contact_type == "Supplier":

            return request.render('pyxel_import_website.import_registration', render_values)
        else:
            return request.render('pyxel_import_website.business_registration', render_values)


class ProductSearchController(http.Controller):

    @http.route(['/nomenclador', '/nomenclador/page/<int:page>'], type='http', auth='public', website=True)
    def nomenclador_view(self, search=None, page=1, **kwargs):
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

    @http.route(['/onure', '/onure/page/<int:page>'], type='http', auth='public', website=True)
    def onure_view(self, search=None, page=1, **kwargs):
        """Renderiza la vista con el buscador y los resultados paginados."""
        electronicos_de_importacion = request.env['product.template'].sudo().search([('product_type', '=', 'electronico'),('de_importacion', '=', True)])

        
        # Filtros para búsqueda
        filters = [('product_type', '=', 'electronico')]
        domain = [('name', 'ilike', search)] if search else []
        domain += filters

        from_view = kwargs.get('from', None)
   
        total_products = request.env['product.template'].sudo().search_count(domain)

        base_url = "/onure"
              
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

        return request.render('pyxel_import_website.onure_template', {
            'products': products,
            'search': search,
            'from_view': from_view,
            "electronicos_de_importacion":electronicos_de_importacion,
            'pager': pager,
        })
  
class PerfilProveedorController(http.Controller):

    @http.route('/descargar/perfil_proveedor', type='http', auth='public')
    def descargar_perfil_proveedor(self, **kw):
        attachment_id_str = request.env['ir.config_parameter'].sudo().get_param('perfil_proveedor.attachment_id')
        if attachment_id_str:
            try:
                attachment_id = int(attachment_id_str)
            except ValueError:
                return request.redirect('/web')
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment and attachment.datas:
                file_content = base64.b64decode(attachment.datas)
                return http.send_file(
                    io.BytesIO(file_content),
                    filename=attachment.name or 'plantilla_proveedor',
                    as_attachment=True
                )
        return request.redirect('/web')

class SolicitudController(http.Controller):

    @http.route('/descargar/solicitud', type='http', auth='public')
    def descargar_solicitud(self, **kw):
        attachment_id_str = request.env['ir.config_parameter'].sudo().get_param('solicitud.attachment_id')
        if attachment_id_str:
            try:
                attachment_id = int(attachment_id_str)
            except ValueError:
                return request.redirect('/web')
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment and attachment.datas:
                file_content = base64.b64decode(attachment.datas)
                return http.send_file(
                    io.BytesIO(file_content),
                    filename=attachment.name or 'solicitud',
                    as_attachment=True
                )
        return request.redirect('/web')

class FichaClienteEstatalController(http.Controller):

    @http.route('/descargar/ficha_cliente_estatal', type='http', auth='public')
    def descargar_ficha_cliente_estatal(self, **kw):
        attachment_id_str = request.env['ir.config_parameter'].sudo().get_param('ficha_cliente_estatal.attachment_id')
        if attachment_id_str:
            try:
                attachment_id = int(attachment_id_str)
            except ValueError:
                return request.redirect('/web')
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment and attachment.datas:
                file_content = base64.b64decode(attachment.datas)
                return http.send_file(
                    io.BytesIO(file_content),
                    filename=attachment.name or 'ficha_cliente',
                    as_attachment=True
                )
        return request.redirect('/web')

class FichaClienteFGNEoTCPController(http.Controller):

    @http.route('/descargar/ficha_cliente_fgne_tcp', type='http', auth='public')
    def descargar_ficha_cliente_fgne_tcp(self, **kw):
        attachment_id_str = request.env['ir.config_parameter'].sudo().get_param('ficha_cliente_fgne_tcp.attachment_id')
        if attachment_id_str:
            try:
                attachment_id = int(attachment_id_str)
            except ValueError:
                return request.redirect('/web')
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment and attachment.datas:
                file_content = base64.b64decode(attachment.datas)
                return http.send_file(
                    io.BytesIO(file_content),
                    filename=attachment.name or 'ficha_cliente',
                    as_attachment=True
                )
        return request.redirect('/web')

class SocioConNacionalidadCubanaController(http.Controller):

    @http.route('/descargar/cuban_partner', type='http', auth='public')
    def descargar_cuban_partner(self, **kw):
        attachment_id_str = request.env['ir.config_parameter'].sudo().get_param('cuban_partner.attachment_id')
        if attachment_id_str:
            try:
                attachment_id = int(attachment_id_str)
            except ValueError:
                return request.redirect('/web')
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment and attachment.datas:
                file_content = base64.b64decode(attachment.datas)
                return http.send_file(
                    io.BytesIO(file_content),
                    filename=attachment.name or 'cuban_partner',
                    as_attachment=True
                )
        return request.redirect('/web')
