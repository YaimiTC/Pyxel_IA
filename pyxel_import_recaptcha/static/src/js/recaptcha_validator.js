odoo.define('pyxel_fruxelimport_portal_recaptcha.recaptcha_validation', function (require) {
    'use strict';

    // Importación del widget público de Odoo
    const publicWidget = require('web.public.widget');

    // Registro del widget personalizado para manejar la validación de reCAPTCHA
    publicWidget.registry.LoginRecaptcha = publicWidget.Widget.extend({
        selector: '.oe_login_form', // Selector del formulario de login
        events: {
            'submit': '_onSubmitForm', // Evento submit para el formulario
        },

        /**
         * Maneja el evento submit del formulario para validar reCAPTCHA antes de enviarlo.
         * @param {Event} ev - Evento de submit del formulario.
         */
        _onSubmitForm: function (ev) {
            const self = this; // Referencia al widget

            // Verificar si el checkbox de reCAPTCHA está marcado
            const recaptchaCheckbox = document.querySelector('.g-recaptcha input[type="checkbox"]');

            if (!recaptchaCheckbox || !recaptchaCheckbox.checked) {
                console.error('El checkbox de reCAPTCHA no está marcado.');
                alert('Por favor, marca el reCAPTCHA para continuar.');
                ev.preventDefault(); // Detener el envío del formulario
                return;
            }

            // Prevenir el envío del formulario mientras se valida reCAPTCHA
            ev.preventDefault();

            // Si está marcado, se procede a verificar el token de reCAPTCHA
            const siteKey = document.querySelector('.g-recaptcha')?.dataset?.sitekey;
            if (!siteKey) {
                console.error('No se encontró el atributo data-sitekey en el elemento reCAPTCHA.');
                alert('Error de configuración: reCAPTCHA no está configurado correctamente.');
                return;
            }

            console.log('Clave del sitio:', siteKey);

            // Ejecutar reCAPTCHA v3 con la acción "login"
            grecaptcha.execute(siteKey, { action: 'login' })
                .then(function (token) {
                    console.log('Token generado:', token);

                    if (token) {
                        // Asignar el token generado al input hidden
                        const recaptchaInput = document.querySelector('#g-recaptcha-response');
                        if (recaptchaInput) {
                            recaptchaInput.value = token;
                        } else {
                            console.error('No se encontró el campo #g-recaptcha-response en el formulario.');
                            alert('Error de configuración: reCAPTCHA no está configurado correctamente.');
                            return;
                        }

                        // Desvincular el evento submit para evitar loops y reenviar el formulario
                        self.$el.off('submit').submit();
                    } else {
                        alert('Por favor, completa el reCAPTCHA para continuar.');
                    }
                })
                .catch(function (error) {
                    // Manejar errores de reCAPTCHA
                    console.error('Error en reCAPTCHA:', error);
                    alert('Ocurrió un error con reCAPTCHA. Por favor, intenta de nuevo.');
                });
        },
    });
});
