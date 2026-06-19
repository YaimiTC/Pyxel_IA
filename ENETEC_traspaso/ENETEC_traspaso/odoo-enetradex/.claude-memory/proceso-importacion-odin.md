---
name: proceso-importacion-odin
description: Arquitectura técnica y máquina de estados del motor de importación (pyxel_import_backend) base del clon ENETEC
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4c1918a5-33b6-4251-837d-dc0bfe097d44
---

Motor de importación en `C:\odoo_agrimpex\addons\pyxel_import_backend` (genérico, sin marca; ~5.578 LOC). Es el corazón del sistema ODIN 2.0 / [[proyecto-enetec-odin]].

**Modelos nuevos clave:** `importation.process` (orquestador, campos `state`=new/in_progress/done/cancelled y `stage_id`), `importation.stage` (7 etapas: SOLICITUD → TRÁMITES ORIGEN → EN TRÁNSITO → TRÁMITES DESTINO → LISTO EXTRAER → EN ALMACÉN CLIENTE → DEVOLUCIÓN CONTENEDOR/is_final), `importation.load` (contenedor, state computed: to_arrive→to_extract→ready_extract→to_return→returned según fechas arrival/release/extraction/return), `importation.load.line`, `importation.cost.line` (costos fixed/percentage), `purchase.provider.evaluation` (draft→evaluated→po_created→apply→evaluating_offer), `import.type` (Ocean/Air/On Site, flags has_bl/has_awb), `incoterm.import.type`, `sale.order.process` (agrupa SO).

**Flujo (= manual de 51 pasos):** CRM lead/acreditación → Sale Order (SLI) → wizard evalúa proveedores sin stock → genera 1 PO por proveedor → RFQ por correo → costos de importación (+margen +arancel) → genera oferta/anexo → confirma al aprobar cliente → referencias de contrato → `action_initial_process_importation()` crea `importation.process` → contenedores con BL/AWB → estados avanzan por fechas → Generar Venta de Costos → factura (`account.move.invoice_type`=import_service) → pago. Importación "en plaza" = `import_type.no_container=True` (sin contenedor).

**Herencias:** purchase.order (importation_id, evaluation_id), sale.order (order_type, process_id), account.move (invoice_type: normal/operative/import_service/tariff_service/other_costs), res.partner (management_type_id, contact_type_id, is_accredited, dap 4 dígitos, legal_activity_ids, contract_import_ids), crm.lead/crm.stage (is_accreditation_stage).

**Capas del sistema:** backend genérico (`pyxel_import_*`, `transport_hub`, `pyxel_sale_*`, `pyxel_po_so_*`, `pyxel_phone_*`, `pyxel_custom_invoice_format`, `pyxel_import_conciliation_report`) + capa de marca (`pyxel_agrimpex_*`). Ver [[rebrand-agrimpex-a-enetradex]].
