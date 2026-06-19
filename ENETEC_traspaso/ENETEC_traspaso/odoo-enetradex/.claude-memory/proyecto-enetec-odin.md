---
name: proyecto-enetec-odin
description: "Nuevo proyecto Odoo \"ENETEC / ODIN 2.0\" — clon/rebrand del sistema Agrimpex/Ceimpex para importadora de combustibles"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4c1918a5-33b6-4251-837d-dc0bfe097d44
---

Se va a crear un proyecto Odoo nuevo en `C:\odoo_enetradex`, como **clon/rebrand** del proyecto base Agrimpex (`C:\odoo_agrimpex`), igual que Agrimpex se clonó de Ceimpex.

- **Cliente:** Sociedad Mercantil ENETEC S.A. (100% capital cubano, NIT 30004148361). Importadora/exportadora vinculada a CUPET. Domicilio: Calle 30 Nº 512 e/ 5ta y 7ma, Miramar, Playa, La Habana. Gerente General: Ivelisse Silva García.
- **Proveedor/Propietario del software:** PCT de La Habana S.A. (3CE) / PYXEL Solutions SRL — el mismo vendor que hizo Ceimpex/Agrimpex. Modalidad SaaS.
- **Nombre del sistema:** "Sistema de Gestión Comercial **ODIN 2.0**".
- **Giro específico (diferencia clave vs Agrimpex):** ENETEC importa **COMBUSTIBLES** (gasolinas, diésel, Jet A-1, fuel oíl, GLP). Cadena logística cubana: depósito/custodia = ENCC; transporte = EPEP/EPEPG; distribución por servicentros = CIMEX y KM0/KMCERO. Tarifas por litro (ENCC 0.0529 USD/L, CIMEX 0.060 USD/L, KM0 0.050 USD/L).
- **Alcance ODIN 2.0 (3 servicios):** (1) Importación Online, (2) Tienda Online con pago en el exterior, (3) Gestión de actividades comerciales (módulos Odoo: Contactos, CRM, Compras, Ventas, Inventario, POS, Facturación).
- **Tarifas del software a ENETEC:** Importación Online 0.3% del valor AWB/CIF/CFR; Comercialización Online 0.01 USD por litro de combustible en consignación; plataforma de gestión comercial incluida sin costo.
- **Docs fuente:** `C:\odoo_enetradex\ENETEC SA\` (contratos marco/específico, bases permanentes, procedimientos combustibles, manual PDF del proceso de importación Ceimpex de 37 pág/51 pasos, logo `Logo ENETEC S.A..jpg`). Texto extraído en `ENETEC SA\_txt\`.

**Decisiones tomadas (2026-06-13):** prefijo de módulos del clon = **`pyxel_enetradex_*`** (los 4 módulos de marca; el resto conserva nombre). Identidad visual web: **esperar mockups/paleta** del usuario antes de rediseñar (mantener estructura Agrimpex de momento). Hay logo provisional `Logo ENETEC S.A..jpg`.

**Infra confirmada (2026-06-13):** contenedores `enetradex_odoo` / `enetradex_postgres` · imagen `enetradex/odoo:17` · BD `enetradex_dev` · puerto HTTP host **8469**→8069 · longpolling host **8472**→8072. (Otros proyectos: avilmat 8069, ceimpex 8169, scem 8269, agrimpex 8369 — NO chocan.)

**CLON BASE COMPLETADO (2026-06-13):** rebrand ejecutado y **funcionando**. Hecho: infra (docker-compose/Dockerfile → enetradex_odoo/enetradex_postgres, imagen enetradex/odoo:17, puertos 8469/8472, BD enetradex_dev); 4 módulos de marca renombrados a `pyxel_enetradex_*` (63 reemplazos de tokens `pyxel_agrimpex_`→`pyxel_enetradex_` y `pyxel.agrimpex.`→`pyxel.enetradex.` en 22 archivos); modelos conciliation → `pyxel.enetradex.conciliation.*`; fix "Frutas Selectas"→"ENETEC S.A." en scheduled_task.py; CLAUDE.md reescrito; sueltos del origen movidos a `backup/_leftovers_origen/`. BD nueva limpia: se descartaron las copias de Agrimpex (movidas a `backup/_old_*_agrimpexcopy/`) y se inicializó cluster vacío + 15 módulos custom (122 módulos, exit 0, sin errores). Verificado: http://localhost:8469 → login y home HTTP 200; agrimpex real intacto. Backups: `backup/enetradex_dev_post_clon_20260613.dump` + `addons_post_clon_20260613.zip`.

**PENDIENTE — residual cosmético del tema web** (`pyxel_enetradex_custom_web_theme`): aún tiene identidad visual Agrimpex (textos "Agrimpex Caribe"/"Mi Agrimpex", clases `.ag-*`, imágenes `logo_agrimpex*.png` y del agro, email info@agrimpexcaribe.com.cu, copyright). Es PROVISIONAL — se rehace en la fase de rediseño web con los mockups de ENETEC. No bloquea la carga. Ver [[rebrand-agrimpex-a-enetradex]] y [[requisitos-enetec-cliente]].

Primer paso de trabajo acordado: **estudiar a fondo el código base** de `C:\odoo_agrimpex` (16 módulos) y dar un mapa técnico antes de planear el clonado.
