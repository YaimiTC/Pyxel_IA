# WhatsApp Cloud API Integration (Odoo 17 Community)

Integración Odoo 17 ↔ **WhatsApp Cloud API oficial de Meta** (sin Twilio ni BSPs de
pago). Notificaciones automáticas dirigidas por eventos, mensajería bidireccional
(webhook entrante), plantillas pre-aprobadas con variables, y un registro/auditoría
de cada mensaje que funciona como un mini-CRM de WhatsApp dentro de Odoo.

## Arquitectura

```
                 ┌──────────────── Odoo 17 ────────────────┐
  Evento ORM     │  sale.order.action_confirm()            │
  (venta/factura │  account.move._post()                   │   build_components()
   /entrega) ───▶│  stock.picking.button_validate()        │──────────────┐
                 │        │                                 │              │
                 │        ▼                                 │              ▼
                 │  whatsapp.message.log._send_event()      │   whatsapp.template.mapping
                 │        │  (opt-in? número? plantilla?)    │   (+ variables {{1}},{{2}})
                 │        ▼                                 │
                 │  whatsapp.api.send(payload) ── requests ─┼──▶ graph.facebook.com/vXX/
                 │        ▲                                 │      {phone_number_id}/messages
   Webhook       │        │ estados (sent/delivered/read)   │
   POST /whatsapp│  controllers/main.py  ◀──────────────────┼──── Meta (statuses + inbound)
   /webhook ─────┼──▶ _log_inbound() / _update_status()     │
                 └──────────────────────────────────────────┘
```

- **Salida (outbound):** un evento de Odoo dispara `whatsapp.message.log._send_event`,
  que resuelve la plantilla (`whatsapp.template.mapping`), arma el payload y lo manda
  vía `whatsapp.api`. Se registra el `wa_message_id` y el estado.
- **Entrada (inbound):** Meta llama al webhook (`/whatsapp/webhook`). Los mensajes
  entrantes se registran (`_log_inbound`) y se enlazan al `res.partner` por número;
  los acuses (sent/delivered/read) actualizan el log (`_update_status`).

## Estructura del módulo

```
whatsapp_integration/
├── models/
│   ├── whatsapp_api.py            # cliente HTTP de la Cloud API (config + envío)
│   ├── whatsapp_template_mapping.py  # evento → plantilla + variables
│   ├── whatsapp_message_log.py    # log/CRM + reglas (24h) + reintentos
│   ├── res_partner.py             # whatsapp_number, opt-in, helpers de número
│   ├── res_config_settings.py     # credenciales (ir.config_parameter)
│   ├── sale_order.py / account_move.py / stock_picking.py  # hooks de eventos
├── controllers/main.py           # webhook (verify GET + inbound/status POST) + health
├── security/ir.model.access.csv
├── data/whatsapp_data.xml        # cron de reintentos + plantilla de ejemplo
└── views/...                     # log, plantillas, partner, ajustes, menús
```

## Modelos (esquema de datos)

- **whatsapp.message.log**: `partner_id`, `phone`, `direction` (outbound/inbound),
  `msg_type` (text/template), `template_name`, `body`, `state` (draft→sent→delivered
  →read / failed / received), `wa_message_id`, `error`, `response_json`, `res_model`,
  `res_id`, `event`, `retry_count`.
- **whatsapp.template.mapping**: `event`, `model_id`, `template_name`, `lang_code`,
  `category` (utility/marketing/authentication), `is_default`, `variable_ids`.
- **whatsapp.template.variable**: `sequence`, `field_path` (ej. `partner_id.name`),
  `fallback`.
- **res.partner** (+): `whatsapp_number`, `whatsapp_opt_in`, `whatsapp_formatted`.
- Credenciales en `ir.config_parameter`: `whatsapp_integration.token`,
  `.phone_number_id`, `.business_account_id`, `.api_version`, `.verify_token`, `.app_secret`.

## Puesta en marcha en Meta (WhatsApp Cloud API)

1. **Meta for Developers** → crea una app de tipo *Business* y añade el producto
   **WhatsApp**.
2. Anota el **Phone Number ID** y el **WhatsApp Business Account ID** (panel de WhatsApp → API Setup).
3. Genera un **Access Token** (recomendado: *System User* token permanente con permisos
   `whatsapp_business_messaging` y `whatsapp_business_management`).
4. Crea y **aprueba tus plantillas** (utility/marketing/authentication) en
   *WhatsApp Manager → Message Templates*.
5. En Odoo → **Ajustes → WhatsApp**: pega Token, Phone Number ID, Business Account ID,
   define un **Verify Token** (string a tu gusto) y, opcional, el **App Secret**.
6. En Meta → **Configuration → Webhook**:
   - Callback URL = la **Webhook URL** que muestra Odoo (`https://TU_DOMINIO/whatsapp/webhook`).
   - Verify Token = el mismo que pusiste en Odoo.
   - Suscríbete a los campos `messages`.
   - Meta hará un `GET` con `hub.challenge`; el controlador responde y queda verificado.

> La URL debe ser pública y HTTPS. En desarrollo usa un túnel (ngrok/Cloudflare Tunnel).

## Configuración funcional en Odoo

- Marca **WhatsApp → Acepta WhatsApp (opt-in)** y rellena el **WhatsApp** (E.164,
  con código de país) en cada `res.partner`. Para empresas con varios números, usa
  los **contactos hijos** (cada uno con su número).
- En **WhatsApp → Plantillas** crea un mapeo por evento: `template_name` EXACTO de Meta,
  idioma, y las **variables** ({{1}}, {{2}}…) apuntando a campos del registro
  (`partner_id.name`, `name`, `amount_total`, …).

## Reglas de mensajería (ventana de 24h)

- Dentro de la **ventana de 24h** desde el último mensaje *entrante* del contacto se
  permite **texto libre**.
- Fuera de esa ventana, **solo plantillas** aprobadas (los eventos automáticos usan
  plantillas siempre, por eso funcionan en cualquier momento).
- Si no hay plantilla para el evento y no hay ventana abierta, el mensaje no se envía
  (queda registrado el motivo).

## Ejemplos de payload (Cloud API)

Texto:
```json
{ "messaging_product": "whatsapp", "to": "5352807765",
  "type": "text", "text": { "body": "Hola, tu pedido fue confirmado." } }
```
Plantilla con variables:
```json
{ "messaging_product": "whatsapp", "to": "5352807765", "type": "template",
  "template": { "name": "order_confirmation", "language": { "code": "es" },
    "components": [ { "type": "body", "parameters": [
        { "type": "text", "text": "Juan Pérez" },
        { "type": "text", "text": "S00021" } ] } ] } }
```

## Producción

- **Rate limits:** la Cloud API limita por número/calidad. Para 10k+/día, envía en
  cola (el cron de reintentos y `state=queued` permiten desacoplar; se puede mover el
  envío a un cron por lotes si hace falta).
- **Reintentos:** `_cron_retry_failed` reintenta los `failed` hasta `MAX_RETRY` (3).
- **Idempotencia:** cada salida guarda `wa_message_id`; los acuses actualizan estado.
- **Seguridad:** credenciales en `ir.config_parameter` (nunca en código); webhook
  valida `X-Hub-Signature-256` con `app_secret`; endpoints públicos mínimos.
- **Escalado:** el envío es stateless (HTTP); para alto volumen, usar varios workers
  Odoo y, si se requiere, un broker/cola externa llamando a `whatsapp.api`.

## Estado / pruebas

El módulo instala y expone el webhook. El **envío real** requiere credenciales de Meta
(token + phone_number_id) y plantillas aprobadas. Sin credenciales, los envíos quedan
en `failed` con el motivo "WhatsApp no configurado".
