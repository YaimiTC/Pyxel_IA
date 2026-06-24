# -*- coding: utf-8 -*-
import logging
import json

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

TIMEOUT = 20
PARAM_PREFIX = "whatsapp_integration"


class WhatsappApi(models.AbstractModel):
    """Cliente de la WhatsApp Cloud API (Meta). Centraliza configuración,
    cabeceras y llamadas HTTP. Las credenciales se leen de ir.config_parameter
    (nunca hardcodeadas)."""
    _name = "whatsapp.api"
    _description = "WhatsApp Cloud API client"

    # ---- Configuración (ir.config_parameter) ----
    @api.model
    def _param(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param(
            "%s.%s" % (PARAM_PREFIX, key), default)

    @api.model
    def _config(self):
        return {
            "token": self._param("token"),
            "phone_number_id": self._param("phone_number_id"),
            "api_version": self._param("api_version", "v19.0"),
            "verify_token": self._param("verify_token"),
            "app_secret": self._param("app_secret"),
            "business_account_id": self._param("business_account_id"),
            "gateway_url": (self._param("gateway_url") or "").rstrip("/"),
            "gateway_api_key": self._param("gateway_api_key"),
        }

    @api.model
    def _use_gateway(self):
        return bool(self._config()["gateway_url"])

    @api.model
    def _is_configured(self):
        c = self._config()
        # Modo gateway: basta con la URL del gateway (el token vive en el servidor
        # exterior). Modo directo: hace falta token + phone_number_id.
        if c["gateway_url"]:
            return True
        return bool(c["token"] and c["phone_number_id"])

    @api.model
    def _messages_url(self):
        c = self._config()
        return "https://graph.facebook.com/%s/%s/messages" % (
            c["api_version"], c["phone_number_id"])

    @api.model
    def _headers(self):
        return {
            "Authorization": "Bearer %s" % self._config()["token"],
            "Content-Type": "application/json",
        }

    # ---- Construcción de payloads ----
    @api.model
    def build_text_payload(self, to, body):
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body or ""},
        }

    @api.model
    def build_template_payload(self, to, template_name, lang_code, components=None):
        tmpl = {"name": template_name, "language": {"code": lang_code or "es"}}
        if components:
            tmpl["components"] = components
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": tmpl,
        }

    # ---- Envío ----
    @api.model
    def send(self, payload):
        """Envía un payload a la Cloud API. Si hay gateway configurado, lo manda
        al gateway exterior (que añade el token y llama a Meta); si no, va directo.
        Devuelve dict: {ok, wa_message_id, status_code, response, error}."""
        if not self._is_configured():
            return {"ok": False, "error": "WhatsApp no configurado (falta gateway o token).",
                    "status_code": 0, "response": {}}
        c = self._config()
        if c["gateway_url"]:
            return self._send_via_gateway(payload, c)
        url = self._messages_url()
        try:
            resp = requests.post(url, headers=self._headers(),
                                 data=json.dumps(payload), timeout=TIMEOUT)
            try:
                data = resp.json()
            except ValueError:
                data = {"raw": resp.text}
            if resp.ok:
                wa_id = (data.get("messages") or [{}])[0].get("id")
                return {"ok": True, "wa_message_id": wa_id,
                        "status_code": resp.status_code, "response": data, "error": False}
            err = (data.get("error") or {}).get("message") or resp.text
            return {"ok": False, "wa_message_id": False,
                    "status_code": resp.status_code, "response": data, "error": err}
        except requests.RequestException as e:
            _logger.exception("WhatsApp API request failed")
            return {"ok": False, "wa_message_id": False, "status_code": 0,
                    "response": {}, "error": str(e)}

    @api.model
    def _send_via_gateway(self, payload, c):
        """Envía el payload al gateway exterior (POST /send con X-API-Key)."""
        try:
            resp = requests.post(
                c["gateway_url"] + "/send",
                headers={"Content-Type": "application/json", "X-API-Key": c["gateway_api_key"] or ""},
                data=json.dumps(payload), timeout=TIMEOUT)
            try:
                data = resp.json()
            except ValueError:
                data = {"raw": resp.text}
            if resp.ok and data.get("ok"):
                return {"ok": True, "wa_message_id": data.get("wa_message_id"),
                        "status_code": resp.status_code, "response": data.get("response") or data,
                        "error": False}
            err = data.get("error") or ("HTTP %s" % resp.status_code)
            return {"ok": False, "wa_message_id": False, "status_code": resp.status_code,
                    "response": data, "error": err}
        except requests.RequestException as e:
            _logger.exception("WhatsApp gateway request failed")
            return {"ok": False, "wa_message_id": False, "status_code": 0,
                    "response": {}, "error": str(e)}

    @api.model
    def pull_gateway(self, limit=50):
        """Consulta los eventos encolados en el gateway (GET /pull). Devuelve lista
        de {id, kind, payload} o []."""
        c = self._config()
        if not c["gateway_url"]:
            return []
        try:
            resp = requests.get(
                c["gateway_url"] + "/pull",
                headers={"X-API-Key": c["gateway_api_key"] or ""},
                params={"limit": limit}, timeout=TIMEOUT)
            if resp.ok:
                return (resp.json() or {}).get("events", [])
            _logger.warning("WhatsApp gateway /pull HTTP %s", resp.status_code)
        except requests.RequestException:
            _logger.exception("WhatsApp gateway /pull failed")
        return []
