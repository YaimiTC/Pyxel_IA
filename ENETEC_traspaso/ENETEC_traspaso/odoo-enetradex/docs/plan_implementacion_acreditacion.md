# Plan de implementación — Acreditación, contraparte y ofertas (ODIN 2.0 / ENETEC)

> Documento de diseño aprobado, **pendiente de implementación**. Aterriza el wizard y los
> flujos validados en sesión sobre el código existente (`pyxel_import_backend`,
> `pyxel_import_website`, `pyxel_enetradex_*`). NO programar hasta aprobar este plan.

## 0. Qué YA existe (reutilizar, no reinventar)

| Pieza | Modelo / archivo | Uso en el nuevo flujo |
|---|---|---|
| Acreditación (motor) | `crm.lead` + `crm.stage.is_accreditation_stage` / `is_rejection_stage` | El abogado mueve el lead a la etapa de acreditación; eso "acredita". |
| Estado acreditado del partner | `res.partner.is_accredited` (computed) | Gate de operación (ambos acreditados). |
| Tipo de empresa | `res.partner.contact.type` (cliente/proveedor) + `res.partner.management.type` (Pymes/Estatal/CNA/Sucursal) | Rol y documentos por tipo. |
| Operación de importación | `importation.process` + `importation.stage` (`is_final`) | La solicitud/operación y su tubería de estados. |
| Formulario de acreditación | `pyxel_import_website` controller `/business-register` + plantilla + override en `pyxel_enetradex_website` | Se reutiliza como **paso "Datos"** del wizard (docs por tipo ya funcionan). |
| Documentos | `ir.attachment` (claves `legal_documentation_*`) | Subida de documentos por tipo. |

## 1. Modelos de datos

### 1.1. Extensiones a modelos existentes
- `res.partner` (en `pyxel_import_backend`):
  - `en_is_public_provider` (Boolean) — proveedor visible en catálogo público (lo marca ENETEC).
  - `en_accepts_offers` (Boolean) — el cliente acepta recibir ofertas de proveedores (opt-in del cliente).
  - Helpers `en_is_client()` / `en_is_supplier()` leyendo `contact_type` (no duplicar verdad).
- `crm.lead`:
  - `en_party_role` (Selection: client/supplier, computed del `contact_type`) — chip y group-by en kanban.
  - `en_initiated_by` (Selection: self/counterparty) y `en_inviter_partner_id` (M2o res.partner) — quién originó la acreditación (sub-acreditación).
- `importation.process`:
  - Enlace a `en_counterparty_id` (proveedor o cliente de la operación) y a la oferta elegida (`en_offer_id`).
  - Gate: estado inicial "Pendiente de acreditación"; transición a "Solicitud para atender" cuando cliente Y proveedor `is_accredited`.

### 1.2. Modelos NUEVOS (genéricos, en `pyxel_import_backend`)
- `en.counterparty.relation` — cartera cliente↔proveedor.
  - `client_id`, `supplier_id`, `state` (invited/draft/self_accrediting/pending/active/rejected), `initiated_by` (client/supplier), `source` (panel/request), `process_id` (opcional).
  - Constraint único por pareja activa.
- `en.accreditation.invitation` — invitación con enlace.
  - `email`, `expected_role` (client/supplier), `inviter_partner_id`, `relation_id`, `token` (uuid), `state` (sent/opened/accepted/expired/cancelled), `expiry` (def. 30 días).
  - Al aceptar y enviar docs: crea/asocia `res.partner` + `crm.lead` (entra al CRM), notifica al invitador.
- `en.supply.offer` + `en.supply.offer.line` — oferta del proveedor (cotización).
  - Cabecera: `supplier_id`, `vigencia` (selección/fecha), `incoterm_id`, `port`, `payment_term`, `flete`, `seguro`, `subtotal` (computed), `total` (computed), `state` (draft/published/expired).
  - Línea: `product_id`, `packaging` (isotanque/isomódulo), `qty`, `unit_price`, `amount` (computed = qty×price).
- `en.tender` (pliego de concurrencia) — ligado a una `importation.process`/solicitud.
  - `process_id`, `product_id`, `qty`, `state` (open/collecting/awarded/closed), líneas de ofertas recibidas, oferta adjudicada.

> Nota: el patrón es el de GranComerx (handoff), pero con prefijo propio `en_`/`en.` (no `gcx_`,
> que es marca ajena). Todo genérico vive en `pyxel_import_backend` para que sea reutilizable.

## 2. Frontend (wizard + páginas) — `pyxel_import_website` + tema `pyxel_enetradex_*`

- **Asistente por pasos** (reemplaza el formulario único de `/business-register`):
  - Cliente: Rol → Datos+tipo → **Solicitud** → **Proveedor** (3 vías) → Resumen.
  - Proveedor: Rol → Datos → **Oferta** (cotización) → **Clientes** (tengo/sumar/difundir) → Resumen.
  - Reutiliza el form de acreditación actual como paso "Datos"; el motor JS `publicWidget` ya existe.
- **Endpoints RPC nuevos** (controladores):
  - `/en/catalog/offers` — ofertas públicas filtradas por producto + búsqueda (catálogo).
  - `/en/counterparty/invite` — crear invitación + enviar correo.
  - `/en/tender/request` — solicitar pliego de concurrencia.
  - `/en/offer/save` — guardar oferta del proveedor (cabecera + líneas).
- **Página del invitado** `/en/accredit/<token>` — acreditación MÍNIMA (solo datos + documentos según rol/tipo); al enviar: notifica al invitador y entra al CRM.
- **Portal `/my/...`** — paneles "Mis Proveedores" / "Mis Clientes" (cartera = `en.counterparty.relation`).

## 3. Backend (CRM + módulo importación)

- **CRM (acreditación):** una bandeja/pipeline única "Solicitudes para atender" con **chip Cliente/Proveedor** (`en_party_role`) + filtro/group-by. Stages: Por revisar → En revisión → Acreditado / (Rechazado-subsanar). El abogado revisa por NIT y acredita cada empresa.
- **Módulo importación (operación):** `importation.stage` con primer estado "Pendiente de acreditación" → (gate ambos acreditados) → "Solicitud para atender" → etapas operativas.
- **Notificaciones:** correos por situaciones (invitación, "ya envió acreditación", aprobado/rechazado, oferta difundida, pliego adjudicado).

## 4. Fases de entrega (MVP primero, cada fase testeable)

- **Fase 0 — Cimientos backend (reusa lo existente).** Chip `en_party_role` + group-by en kanban; gate en `importation.process` ("Pendiente de acreditación" → ambos acreditados). Sin tocar frontend. *Valida el núcleo.*
- **Fase 1 — Wizard (frontend).** Asistente por pasos con el orden nuevo; reusa el form de datos. Contraparte/oferta como placeholders. *Valida navegación.*
- **Fase 2 — Contraparte + invitación.** Modelos `relation` + `invitation`, página del invitado, notificación, entrada al CRM. Paso Proveedor/Clientes funcional (cartera/acreditar/invitar).
- **Fase 3 — Ofertas + catálogo + búsqueda.** Modelos `supply.offer`/line; flags `is_public_provider` + `accepts_offers`; catálogo con buscador filtrado por producto; difundir oferta.
- **Fase 4 — Pliego de concurrencia.** Modelo `en.tender`; flujo de licitación gestionado por ENETEC.
- **Fase 5 — Pulido.** Estados completos del módulo importación, dashboards, todos los correos.

## 5. Riesgos / decisiones abiertas
- Confirmar moneda/impuestos/descuentos en la oferta (hoy: USD, sin impuestos).
- Definir QUÉ situaciones disparan correo (notificaciones).
- Caducidad de invitación (propuesto 30 días) y de la oferta (vigencia).
- Provincias/municipios de Cuba ya cargados (16/168) para los selects.
- Mantener `workers = 0` (threaded) — workers>0 tumbó el servicio.

## 6. Flujo estándar de cada cambio (recordatorio operativo)
1. Backup BD (`pg_dump`) + snapshot del módulo (`Compress-Archive`).
2. Editar en `addons/<modulo>/`.
3. `docker exec enetradex_odoo odoo -u <modulo> -d enetradex_dev --stop-after-init --no-http` (uno a la vez).
4. `docker restart enetradex_odoo`; revisar `docker logs`.
5. Test visual en http://localhost:8469 (incógnito + Ctrl+Shift+R).
