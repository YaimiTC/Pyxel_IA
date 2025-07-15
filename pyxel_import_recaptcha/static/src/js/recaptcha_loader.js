/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ReCaptcha } from "@google_recaptcha/js/recaptcha";  // Ruta del módulo original

patch(ReCaptcha.prototype, {
    /**
     * Sobrescribimos `loadLibs()` para cargar el script de reCAPTCHA v2
     */
    loadLibs() {
        if (!this._publicKey) {
            return false;
        }
        // Verificar si el div de reCAPTCHA existe en el DOM
        let recaptchaDiv = document.querySelector(".g-recaptcha");
        console.log(recaptchaDiv)

        if (!recaptchaDiv) {

            console.warn("No se encontró el div de reCAPTCHA. No se cargará la API.");
            return false;
        }

        this._recaptchaReady = new Promise((resolve, reject) => {
            console.log("Iniciando carga de reCAPTCHA v2...");

            let existingScript = document.querySelector(`script[src^="https://www.google.com/recaptcha/api.js"]`);
            if (existingScript) {
                console.log("Script ya existe. Esperando onload...");
                 // Fuerza la ejecución de onload si no se dispara
                setTimeout(() => {
                    if (typeof existingScript.onload === 'function') {
                        existingScript.onload();  // Forzamos el onload manualmente
                    }
                }, 1000); // Espera 1 segundo y ejecuta el onload si no ha sucedido aún

                console.log('existingScript', existingScript);
                existingScript.onload = () => {
                    console.log("Script cargado correctamente.");
                    resolve();
                };
                existingScript.onerror = () => {
                    console.error("Error al cargar el script de reCAPTCHA.");
                    reject("Error al cargar el script de reCAPTCHA");
                };
                return;
            }

            console.log("Insertando script de reCAPTCHA v2...");
            const script = document.createElement("script");
            script.src = `https://www.google.com/recaptcha/api.js?hl=es`;  // Asegúrate de cambiar el idioma si es necesario
            script.onload = () => {
                console.log("Script de reCAPTCHA cargado.");
                resolve();
            };

            script.onerror = () => {
                console.error("Error al cargar el script de reCAPTCHA.");
                reject("Error al cargar el script de reCAPTCHA.");
            };

            document.head.appendChild(script);
        });

        return this._recaptchaReady.then(() => !!document.querySelector('.grecaptcha-badge'));
    },

    /**
     * Sobrescribimos `getToken(action)` para la obtención del token en reCAPTCHA v2
     */
    async getToken(action) {
        console.log("Ejecutando getToken con acción:", action);
         // Verificar si el div de reCAPTCHA existe en el DOM
        let recaptchaDiv = document.querySelector(".g-recaptcha");
        console.log(recaptchaDiv)

        if (!recaptchaDiv) {
            console.warn("Por el Token No se encontró el div de reCAPTCHA. No se cargará la API.");
            return false;
        }

        if (!this._publicKey) {
            console.error("No se ha definido una clave pública para reCAPTCHA.");
            return {
                message: "No recaptcha site key set.",
            };
        }
        console.log("Antes de await this._recaptchaReady");
        await this._recaptchaReady;
        console.log("Después de await this._recaptchaReady");

        try {
            console.log("Ejecutando reCAPTCHA v2...");
            const token = window.grecaptcha.getResponse();  // Usamos getResponse en v2
            console.log("Token generado:", token);

            if (!token) {
                throw new Error("reCAPTCHA no fue completado correctamente.");
            }

            return { token };
        } catch (error) {
            console.error("Error ejecutando reCAPTCHA:", error);
            return {
                error: "El sitio de reCAPTCHA no es válido o no se completó correctamente.",
            };
        }
    }
});
