from odoo import http
from odoo.http import request
from datetime import datetime
import logging
import json

_logger = logging.getLogger(__name__)


class PartnerController(http.Controller):
    check_create_client_supplier = ['access_token', 'name', 'email', 'phone', 'vat_or_minrex', 'fgne', 'company',
                                    'address', 'state', 'city']
    check_accreditation_status = ['access_token', 'vat_or_minrex', 'type_of_contact']

    # check_import_request = ['access_token', 'estimated_start_date', 'estimated_end_date', 'supplier', 'client',
    #                         'country_origin_id',
    #                         'certifies_receipt_load', 'purchase_condition_number', 'products']

    check_import_request = ['access_token', 'estimated_start_date', 'estimated_end_date', 'supplier', 'client',
                            'country_origin_id', 'purchase_condition_number', 'products']

    check_import_status = ['access_token', 'import_request_code']

    def _json_integrity(self, data, keys):
        for element in keys:
            if element not in data:
                return {'status': 'error', 'msg': 'key ' + element + ' missing in Json'}
            if not data.get(element):
                return {'status': 'error', 'msg': element + ' value is required'}
        return {'status': 'OK'}

    def _check_access_token(self, token):
        user = request.env['res.users'].sudo().search([('access_token', '=', token)], limit=1)
        if not user:
            return False
        request.update_env(user=user)
        return True

    def _set_all_data(self, data, type_of_contact_id):
        type_of_contact_obj = request.env['res.partner.contact.type'].sudo().browse(type_of_contact_id)
        type_of_contact = type_of_contact_obj.type_of_contact
        if type_of_contact != 'Client' and type_of_contact != 'Supplier':
            return {'error': 'type_of_contact must be Client or Supplier'}

        contact_data = {
            'name': data.get('name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
        }

        if type_of_contact == 'Client':
            contact_data['vat'] = data.get('vat_or_minrex')
            field_to_compare = 'vat'
        else:
            contact_data['license_holder'] = data.get('vat_or_minrex')
            field_to_compare = 'license_holder'

        existing_partner = request.env['res.partner'].sudo().search(
            [('name', '=', data.get('name')), (field_to_compare, '=', data.get('vat_or_minrex'))], limit=1)
        if existing_partner:
            return {'error': type_of_contact + ' already exists'}

        contact_record = request.env['res.partner'].sudo().create(contact_data)

        internal_notes = f"""
        Otra información:

        ___________
        register_type : accreditation
        Register as : {type_of_contact}
        FGNE type : {data.get('fgne')}
        company : {data.get('company')}
        nit : {data.get('vat')}
        company_email : {data.get('email')}
        Address : {data.get('address')}
        State : {data.get('state')}
        City : {data.get('city')}
        """

        internal_notes = internal_notes.replace("\n", "<br>")

        crm_lead_data = {
            'name': data.get('name'),
            'contact_name': data.get('name'),
            'email_from': data.get('email'),
            'phone': data.get('phone'),
            'partner_id': contact_record.id,
            'description': internal_notes
        }

        crm_lead_record = request.env['crm.lead'].sudo().create(crm_lead_data)

        return {'name': crm_lead_record.name,
                'status': crm_lead_record.stage_id.name}

    @http.route('/api/type_of_contact', type='json', auth='public', methods=['POST'])
    def type_of_contact(self, **kwargs):
        data = json.loads(request.httprequest.data)

        if not self._check_access_token(data.get('access_token')):
            return {'status': 'error', 'msg': 'Invalid access token'}

        # Obtener todos los registros del modelo res.country
        types_of_contact = request.env['res.partner.contact.type'].search([])
        types_of_contact_list = [
            {'id': type_of_contact.id, 'name': type_of_contact.name, 'type_of_contact': type_of_contact.type_of_contact}
            for type_of_contact in types_of_contact]

        return {
            'types_of_contact': types_of_contact_list
        }

    @http.route('/api/create_client', type='json', auth='public', methods=['POST'])
    def create_client(self, **kwargs):
        data = json.loads(request.httprequest.data)

        data_integrity = self._json_integrity(data, self.check_create_client_supplier)
        if data_integrity.get('status') == 'error':
            return data_integrity

        if not self._check_access_token(data.get('access_token')):
            return {'status': 'error', 'msg': 'Invalid access token'}

        return self._set_all_data(data, 'Client')

    @http.route('/api/create_supplier', type='json', auth='public', methods=['POST'])
    def create_supplier(self, **kwargs):
        data = json.loads(request.httprequest.data)

        data_integrity = self._json_integrity(data, self.check_create_client_supplier)
        if data_integrity.get('status') == 'error':
            return data_integrity

        if not self._check_access_token(data.get('access_token')):
            return {'status': 'error', 'msg': 'Invalid access token'}

        return self._set_all_data(data, 'Supplier')

    @http.route('/api/accreditation_status', type='json', auth='public', methods=['POST'])
    def accreditation_status(self, **kwargs):
        data = json.loads(request.httprequest.data)

        data_integrity = self._json_integrity(data, self.check_accreditation_status)
        if data_integrity.get('status') == 'error':
            return data_integrity

        if not self._check_access_token(data.get('access_token')):
            return {'status': 'error', 'msg': 'Invalid access token'}

        vat_or_minrex = data.get('vat_or_minrex')
        field_to_compare = 'vat' if data.get('type_of_contact') == 'Client' else 'license_holder'

        partner = request.env['res.partner'].sudo().search([(field_to_compare, '=', vat_or_minrex)], limit=1)
        if not partner:
            return {'status': 'error', 'msg': 'Partner not found'}
        crm_lead = request.env['crm.lead'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not crm_lead:
            return {'status': 'error', 'msg': 'CRM Lead not found'}

        return {'crm_name': crm_lead.name,
                'crm_status': crm_lead.stage_id.name
                }

    @http.route(route='/api/import_request', type='json', auth='public', methods=['POST'])
    def import_request(self, **kwargs):
        data = json.loads(request.httprequest.data)

        data_integrity = self._json_integrity(data, self.check_import_request)
        if data_integrity.get('status') == 'error':
            return data_integrity

        if not self._check_access_token(data.get('access_token')):
            return {'status': 'error', 'msg': 'Invalid access token'}

        supplier = request.env['res.partner'].sudo().search([('name', '=', data.get('supplier')),
                                                             ('license_holder', '!=', False)],
                                                            limit=1)
        if not supplier:
            return {'status': 'error', 'msg': 'Supplier not found or does not have a valid MINREX code'}
        Client = request.env['res.partner'].sudo().search([('name', '=', data.get('Client')),
                                                           ('vat', '!=', False)],
                                                          limit=1)
        if not Client:
            return {'status': 'error', 'msg': 'Client not found or does not have a valid VAT code'}

        country = request.env['res.country'].sudo().search([('name', '=', data.get('country_origin_id'))], limit=1)
        if not country:
            return {'status': 'error', 'msg': 'Country not found'}

        internal_notes = f"""
                    Otra información:

                    ___________
                    register_type : import
                    Proveedor : {supplier.name}
                    Email proveedor : {supplier.email}
                    Productos a importar : {data.get('products')}
                    id del país : {country.id}
                    Tipo de envío de la carga : {data.get('certifies_receipt_load')}
                    No. BL/AWB : {data.get('purchase_condition_number')}
                    Client_id : {Client.id}
                    
                    Cliente : {Client.name}
                    NIT : {Client.vat}
                    """

        internal_notes = internal_notes.replace("\n", "<br>")

        try:
            estimated_start_date = datetime.strptime(data.get('estimated_start_date'), "%Y-%m-%d").strftime("%Y-%m-%d")
            estimated_end_date = datetime.strptime(data.get('estimated_end_date'), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return {'status': 'error', 'msg': 'The dates must be in this format: 2024-01-01'}

        import_data = {
            "estimated_start_date": estimated_start_date,
            "estimated_end_date": estimated_end_date,
            "provider_id": supplier.id,
            "country_origin_id": country.id,
            # "x_studio_certifies_receipt_load": data.get('certifies_receipt_load'),
            "purchase_condition_number": data.get('purchase_condition_number'),
            # "x_studio_website_description": internal_notes
        }

        import_record = request.env['importation.process'].sudo().create(import_data)

        return {'code': import_record.name,
                'status': import_record.stage_id.name}

    @http.route(route='/api/import_status', type='json', auth='public', methods=['POST'])
    def import_status(self, **kwargs):
        data = json.loads(request.httprequest.data)

        data_integrity = self._json_integrity(data, self.check_import_status)
        if data_integrity.get('status') == 'error':
            return data_integrity

        if not self._check_access_token(data.get('access_token')):
            return {'status': 'error', 'msg': 'Invalid access token'}

        import_request = request.env['importation.process'].sudo().search(
            [('name', '=', data.get('import_request_code'))],
            limit=1)
        if not import_request:
            return {'status': 'error', 'msg': 'The import Request does not exist'}
        else:
            return {'code': import_request.name,
                    'status': import_request.stage_id.name}

    @http.route(route='/api/reference_data', type='json', auth='public', methods=['POST'])
    def reference_data(self, **kwargs):
        data = json.loads(request.httprequest.data)

        if not self._check_access_token(data.get('access_token')):
            return {'status': 'error', 'msg': 'Invalid access token'}

        # Formas de gestión no estatal
        fgne = ['TCP', 'MIPYME', 'PDL']

        # Obtener todos los registros del modelo res.country
        countries = request.env['res.country'].search([])
        country_list = [{'id': country.id, 'name': country.name} for country in countries]

        return {
            'fgne': fgne,
            'countries': country_list
        }
