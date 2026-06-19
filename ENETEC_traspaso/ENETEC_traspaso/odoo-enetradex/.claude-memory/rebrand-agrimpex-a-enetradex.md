---
name: rebrand-agrimpex-a-enetradex
description: Alcance exacto del rebrand de los módulos Agrimpex a pyxel_enetradex_* (qué tocar y qué es genérico)
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4c1918a5-33b6-4251-837d-dc0bfe097d44
---

Mapa del rebrand para el clon ENETEC ([[proyecto-enetec-odin]]). Base: `C:\odoo_agrimpex\addons` (16 módulos).

**GENÉRICOS — NO requieren cambios de código** (solo se copian; opcional ajustar `author`/`website` en manifest): `pyxel_import_backend`, `pyxel_import_website`, `pyxel_import_api`, `pyxel_import_recaptcha`, `pyxel_import_conciliation_report` (sin manifest, es librería), `transport_hub`, `pyxel_sale_process_sequence`, `pyxel_sale_available_budget`, `pyxel_po_so_report_currency`, `pyxel_phone_signup_signin`, `pyxel_custom_invoice_format`.

**EXCEPCIÓN en genéricos:** `pyxel_import_email_excel/models/scheduled_task.py:68` tiene hardcodeado **"Frutas Selectas"** en el mensaje de aviso de vencimiento de contrato → cambiar a configurable o "ENETEC".

**MÓDULOS DE MARCA a renombrar a `pyxel_enetradex_*`:**
1. `pyxel_agrimpex_backend` (bajo impacto; solo hereda crm.lead._compute_name). Renombrar carpeta + manifest.
2. `pyxel_agrimpex_website` (bajo; template `business_registration_agrimpex`, override JS de campo `dap`). Renombrar carpeta, ids, rutas de asset.
3. `pyxel_agrimpex_conciliation_report` (ALTO): **3 modelos con _name** `pyxel.agrimpex.conciliation.{wizard,service,xls_exporter}` → `pyxel.enetradex.conciliation.*`; 3 ids XML (`action_/menu_/view_pyxel_agrimpex_conciliation_*`); defaults `provider_import_name="Agrimpex"`, título Excel "ACTA DE CONCILIACIÓN ... AGRIMPEX". Genera Excel 3 hojas (USD/CUP/Resumen CE-PCT 70/30 y PCT/PYXEL 10/90).
4. `pyxel_agrimpex_custom_web_theme` (**CRÍTICO, ~80% del esfuerzo, 100+ cambios**): 19 XML (home/navbar/footer/shop/product/cart/about/portal), ~18 ids con `agrimpex_`, clases CSS prefijo `.ag-*`, variables SCSS `$cx-*`, ~50 imágenes con marca, textos "Agrimpex Caribe"/"Mi Agrimpex", datos de contacto del footer, paleta verde+lima. **El usuario pidió ESPERAR mockups/paleta de ENETEC antes de rediseñar esta capa.**

**Estrategia recomendada:** (1) copiar proyecto y rebrandear infra (BD/contenedores/puertos/manifests + los 3 módulos de marca de bajo/medio impacto + modelos conciliation), (2) dejar el tema web `custom_web_theme` con estructura provisional hasta tener identidad visual ENETEC. Nota de negocio: ENETEC es de COMBUSTIBLES, no agro — los textos/sectores del home de Agrimpex (agricultura, productor) NO aplican.
