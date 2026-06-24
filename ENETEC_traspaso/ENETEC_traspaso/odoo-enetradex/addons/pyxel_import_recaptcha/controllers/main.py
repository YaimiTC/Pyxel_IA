import logging
import requests
import werkzeug.utils

from odoo import http, _
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AuthSignupRecaptcha(AuthSignupHome):
    @http.route()
    def web_login(self, *args, **kw):
        """Extiende el login para agregar validación con reCAPTCHA."""
        _logger.info("Entró al controller AuthSignupRecaptcha Login")

        recaptcha_public_key = request.env['ir.config_parameter'].sudo().get_param('recaptcha_public_key')
        recaptcha_private_key = request.env['ir.config_parameter'].sudo().get_param('recaptcha_private_key')

        _logger.info(f"Clave Pública reCAPTCHA: {recaptcha_public_key}")

        # Solo se verifica si reCAPTCHA está CONFIGURADO (claves presentes).
        # Si no hay claves, se delega al login normal de Odoo (no bloquear).
        if recaptcha_public_key and recaptcha_private_key and 'g-recaptcha-response' in kw:
            recaptcha_response = kw.get('g-recaptcha-response')

            # Verificar el token de reCAPTCHA con Google
            verify_url = 'https://www.google.com/recaptcha/api/siteverify'
            data = {'secret': recaptcha_private_key, 'response': recaptcha_response}
            result = requests.post(verify_url, data=data).json()

            if result.get('success'):
                # Si reCAPTCHA es válido, proceder con la autenticación
                login = kw.get('login')
                password = kw.get('password')

                if login and password:
                    try:
                        request.session.authenticate(request.env.cr.dbname, login, password)
                        return request.redirect(kw.get('redirect', '/web'))
                    except Exception:
                        return request.render('web.login', {
                            'error': 'Las credenciales son incorrectas. Por favor, inténtalo de nuevo.',
                            'recaptcha_public_key': recaptcha_public_key
                        })
                else:
                    return request.render('web.login', {
                        'error': 'Por favor, ingresa un nombre de usuario y contraseña.',
                        'recaptcha_public_key': recaptcha_public_key
                    })
            else:
                _logger.warning("Fallo la verificación de reCAPTCHA.")
                return request.render('web.login', {
                    'error': 'La verificación de reCAPTCHA falló. Inténtalo de nuevo.',
                    'recaptcha_public_key': recaptcha_public_key
                })

        # Si no hay reCAPTCHA en la request, renderiza el login normal
        response = super(AuthSignupRecaptcha, self).web_login(*args, **kw)
        _logger.info("hasattr qcontext in response: %s", hasattr(response, 'qcontext'))

        if hasattr(response, 'qcontext'):
            response.qcontext['recaptcha_public_key'] = recaptcha_public_key

        return response

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        _logger.info("Entró al controller AuthSignupRecaptcha signup!")

        # Obtener claves de reCAPTCHA desde los parámetros del sistema
        recaptcha_secret_key = request.env['ir.config_parameter'].sudo().get_param('recaptcha_private_key')
        recaptcha_public_key = request.env['ir.config_parameter'].sudo().get_param('recaptcha_public_key')

        # Verificar si el reCAPTCHA está habilitado y validar la respuesta
        # Solo se exige/verifica reCAPTCHA si está CONFIGURADO (clave presente).
        if recaptcha_secret_key:
            if 'g-recaptcha-response' not in kw:
                _logger.warning("No se encontró el reCAPTCHA en la solicitud.")
                return request.render('auth_signup.signup', {
                    'error': _('Debes completar la verificación reCAPTCHA.'),
                    'recaptcha_public_key': recaptcha_public_key
                })
            recaptcha_response = kw.get('g-recaptcha-response')
            verify_url = 'https://www.google.com/recaptcha/api/siteverify'
            data = {'secret': recaptcha_secret_key, 'response': recaptcha_response}
            result = requests.post(verify_url, data=data).json()

            if not result.get('success'):
                _logger.warning("Validación de reCAPTCHA fallida.")
                return request.render('auth_signup.signup', {
                    'error': _('La verificación reCAPTCHA falló. Inténtalo nuevamente.'),
                    'recaptcha_public_key': recaptcha_public_key
                })
        # Si no hay claves de reCAPTCHA, se omite la verificación y se continúa.

        # Llamar al método original para continuar con el proceso de signup
        response = super(AuthSignupRecaptcha, self).web_auth_signup(*args, **kw)

        # Obtener el usuario recién creado
        login = kw.get('login')
        if login:
            user = request.env['res.users'].sudo().search([('login', '=', login)], limit=1)
            if user:
                # Autenticar automáticamente al usuario después del registro
                request.session.authenticate(request.env.cr.dbname, login, kw.get('password'))
                _logger.info(f"Usuario {login} autenticado automáticamente después del registro.")
                return request.redirect(kw.get('redirect', '/web'))  # Redirigir al portal

        return response


#
# class WebsiteFormInherit(WebsiteForm):
#     @http.route(
#         ["/business-register"],
#         type="http",
#         auth="public",
#         methods=["POST", "GET"],
#         website=True,
#     )
#     def business_register(self, **kw):
#         """
#         Hereda '/business-register' de WebsiteForm y agrega la clave pública de reCAPTCHA al contexto.
#         """
#         _logger.info(" entro al controller WebsiteFormInherit!!!!!!!!!!!!!!!!!!!!!!!!!!!! ")
#
#         response = super(WebsiteFormInherit, self).business_register(**kw)
#
#         recaptcha_public_key = request.env['ir.config_parameter'].sudo().get_param('recaptcha_public_key')
#         _logger.info(" entro al controller WebsiteFormInherit! %s", recaptcha_public_key)
#
#         request.session['recaptcha_public_key'] = recaptcha_public_key
#
#         if isinstance(response, dict):
#             response['recaptcha_public_key'] = recaptcha_public_key
#
#         return response
#
#
# class BusinessRegisterInherit(ControllerTest):
#     def get_public_key(self):
#         """ Devuelve la clave pública de reCAPTCHA desde la configuración """
#         return request.env['ir.config_parameter'].sudo().get_param('recaptcha_public_key')
#
#     def _render_template(self, template, values):
#         """ Extiende el método para añadir la clave pública a todas las respuestas """
#         # Obtener la clave pública de reCAPTCHA
#         recaptcha_public_key = self.get_public_key()
#
#         # Añadir la clave pública al contexto de la plantilla
#         values['recaptcha_public_key'] = recaptcha_public_key
#
#         # Llamar al método original para renderizar la plantilla con el nuevo contexto
#         return super(BusinessRegisterInherit, self)._render_template(template, values)
#
#     @http.route('/business-register', type='http', auth="public", website=True)
#     def controller_register(self, **kw):
#
#         recaptcha_public_key = self.get_public_key()
#         # Guardar la clave en la sesión
#         request.session['recaptcha_public_key'] = recaptcha_public_key
#
#         _logger.info(" entro al controler mio y el captcha es: %s", recaptcha_public_key)
#         # Redirigir al login si el usuario es público
#         if request.env.user.id == request.env.ref('base.public_user').id:
#             return request.redirect('/web/login?redirect=/business-register?type=import')
#
#         # """ Modifica la ruta /business-register para agregar la clave pública al contexto """
#         response = super(BusinessRegisterInherit, self).controller_register(**kw)
#
#         # Si la respuesta es un diccionario, agregar la clave pública al contexto
#         if isinstance(response, dict):
#             response['recaptcha_public_key'] = recaptcha_public_key
#
#         return response

    # @http.route('/business-register', type='http', auth="public", website=True)
    # def controller_register(self, **kw):
    #     """ Hereda la ruta '/business-register' y agrega la clave pública de reCAPTCHA al contexto """
    #
    #     # Llamar al método original para reutilizar su lógica
    #     response = super().controller_register(**kw)
    #     logging.info(f"response: {response}")
    #     # Si la respuesta es una renderización de plantilla, agregar la clave pública al contexto
    #     if isinstance(response, dict):
    #         recaptcha_public_key = request.env['ir.config_parameter'].sudo().get_param('recaptcha_public_key')
    #         response['recaptcha_public_key'] = recaptcha_public_key  # Agregar clave pública al contexto
    #         logging.info(f"recaptcha_public_key: {recaptcha_public_key}")
    #
    #     return response

