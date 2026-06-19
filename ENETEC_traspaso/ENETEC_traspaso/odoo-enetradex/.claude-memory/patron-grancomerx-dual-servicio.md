---
name: patron-grancomerx-dual-servicio
description: Patrón de diseño GranComerx (servicio dual + acreditación + contraparte) reutilizable para ENETEC
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4c1918a5-33b6-4251-837d-dc0bfe097d44
---

Doc `C:\odoo_enetradex\ENETEC SA\Handoff_Acreditacion_Importacion_GranComerx.pdf` — handoff técnico de OTRA importadora (GranComerx) sobre la MISMA plataforma pyxel (`pyxel_import_backend`/`pyxel_import_website`). Diseño aprobado, **pendiente de implementación** (NO está aún en el código base de Agrimpex). Aplica a [[proyecto-enetec-odin]] porque ENETEC también tiene servicio dual: Importación Online + Tienda Online (mayorista).

**Idea central:** soportar 2 servicios (mayorista + importación) con acreditación previa y selección de contraparte. Los campos custom viven en un módulo SEPARADO `gcx_crm_service_origin` (+ `grancomerx_theme`), NO dentro de pyxel_import_*. Prefijo de campos `gcx_*`.

**Componentes:**
1. `crm.lead`: `gcx_service_origin` Selection(wholesale/import) required+index para chip en kanban; `gcx_origin_url`; SQL constraint EXCLUDE que impide 2 leads activos del mismo partner+servicio. Hook en `write()` recomputa flags del partner al cambiar stage.
2. `res.partner`: flags `gcx_is_wholesale_customer`/`gcx_is_import_accredited`; estados computados `gcx_wholesale_state`/`gcx_import_state` (none/pending/approved); helpers `_is_gcx_client()`/`_is_gcx_supplier()` que LEEN el campo nativo de tipo (no duplican verdad).
3. `crm.stage`: reutiliza `allows_sale` (aprobación mayorista) e `is_accreditation_stage` (acreditación importación) — NO crea stages nuevas.
4. `importation.process`: `gcx_counterparty_role` (supplier/client computed), `gcx_counterparty_mode` (none/existing/new), `gcx_counterparty_id`, campos modo 'new' (name/nit/email/phone/address) + `gcx_accreditation_lead_id`. Constraint: NIT obligatorio SOLO si contraparte es cliente.
5. Vistas backend: chip MAY(violeta #7F77DD)/IMP(azul #1B74E4) en kanban CRM, badge en lista, filtros+group_by, pestaña "Servicios" en form partner.
6. Form de solicitud: 4 secciones (Productos / Solicitud de oferta / Carga productos opcional / **Contraparte** con 3 radio cards). Título dinámico por rol: si logueado es cliente→"Proveedor de la importación" y viceversa. "Sub-acreditación" = acreditar contraparte nueva genera lead extra con service_origin=import.
7. Portal `/my/home`: 2 cards por servicio (mayorista/importación) con estado none/pending/approved (gris/amarillo/verde) + mini progress bar de stages.
8. Banner acreditación ramifica con t-if según `partner.gcx_is_import_accredited`.

**Decisiones cerradas (espejar en ENETEC):** un solo equipo de ventas (no separar crm.team por servicio); sin auto-aprobación para personas naturales (humano valida); stages compartidas; tipo cliente/proveedor del campo nativo; cada acreditación = lead independiente; NIT obligatorio solo para acreditación de cliente (proveedor extranjero no siempre).

**Para ENETEC:** el prefijo `gcx_`/tema son de marca GranComerx; si se adopta, replicar el patrón con prefijo propio o reusar el módulo compartido cuando se mergee. El concepto contraparte (cliente cubano ↔ proveedor extranjero) calza con el modelo de combustibles de ENETEC.
