# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WhatsappController(http.Controller):

    # ---- Verificación del webhook (Meta hace un GET con hub.challenge) ----
    @http.route("/whatsapp/webhook", type="http", auth="public", methods=["GET"], csrf=False)
    def webhook_verify(self, **kw):
        args = request.httprequest.args
        mode = args.get("hub.mode")
        token = args.get("hub.verify_token")
        challenge = args.get("hub.challenge")
        cfg = request.env["whatsapp.api"].sudo()._config()
        if mode == "subscribe" and token and token == cfg.get("verify_token"):
            return request.make_response(challenge or "", [("Content-Type", "text/plain")])
        return request.make_response("Forbidden", status=403)

    # ---- Recepción de mensajes y estados (Meta hace POST con JSON) ----
    @http.route("/whatsapp/webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def webhook_receive(self, **kw):
        raw = request.httprequest.get_data() or b""
        if not self._valid_signature(raw):
            _logger.warning("WhatsApp webhook: firma inválida")
            return request.make_response("Invalid signature", status=403)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            return request.make_response("Bad payload", status=400)
        Log = request.env["whatsapp.message.log"].sudo()
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    for msg in value.get("messages", []):
                        body = ""
                        mtype = msg.get("type", "text")
                        if mtype == "text":
                            body = (msg.get("text") or {}).get("body", "")
                        else:
                            body = "[%s]" % mtype
                        Log._log_inbound(msg.get("from"), body, msg.get("id"), mtype)
                    for st in value.get("statuses", []):
                        Log._update_status(st.get("id"), st.get("status"))
        except Exception:
            _logger.exception("WhatsApp webhook processing error")
        # Meta espera 200 siempre que recibamos el evento.
        return request.make_response("EVENT_RECEIVED", [("Content-Type", "text/plain")])

    def _valid_signature(self, raw):
        """Valida X-Hub-Signature-256 si hay app_secret configurado."""
        secret = request.env["whatsapp.api"].sudo()._config().get("app_secret")
        if not secret:
            return True  # sin secreto configurado, no se valida
        sig = request.httprequest.headers.get("X-Hub-Signature-256", "")
        if not sig.startswith("sha256="):
            return False
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig.split("=", 1)[1], expected)

    # ---- Health check ----
    @http.route("/whatsapp/status", type="http", auth="public", methods=["GET"], csrf=False)
    def status(self, **kw):
        configured = request.env["whatsapp.api"].sudo()._is_configured()
        body = json.dumps({"ok": True, "configured": configured})
        return request.make_response(body, [("Content-Type", "application/json")])
