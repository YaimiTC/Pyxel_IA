---
name: optimizacion-rendimiento-web
description: "Optimizaciones de rendimiento aplicadas al sitio ENETRADEX (eliminación de recursos externos, workers)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4c1918a5-33b6-4251-837d-dc0bfe097d44
---

Optimización de la lentitud del sitio ENETRADEX (2026-06-13). Causa raíz: **recursos externos de CDN internacionales bloqueando el render en cada página** (crítico desde Cuba por el ancho de banda internacional). Ver [[identidad-web-enetradex]].

**Cambios aplicados:**
- **Font Awesome:** se eliminó el `<link>` a `cdnjs.cloudflare.com/.../fontawesome 5.15.4` del `base_layout.xml`. Ahora se usa el **FA 4.7 que Odoo ya incluye local** en su bundle (sin CDN, sin conflicto). Único icono FA5-only que se usaba (`fa-microchip`) → cambiado a `fa-cogs` en home.xml. El resto (fa-ship, fa-th-large, etc.) existen en FA4.7.
- **jQuery:** se quitó el segundo jQuery (CDN `code.jquery.com`) del manifest de `pyxel_import_website`. Odoo 17 ya trae jQuery. **Bonus:** el jQuery duplicado rompía el plugin `zoomOdoo` de website_sale (error "TypeError: this.$(...).zoomOdoo is not a function" + modal "Odoo Client Error"). Al quitarlo: `$.fn.zoomOdoo` vuelve a ser función y `$.fn.select2` queda presente.
- **Select2:** descargado LOCAL en `pyxel_import_website/static/lib/select2/` y referenciado en el manifest (antes CDN jsdelivr). Se engancha al jQuery de Odoo.
- **Google Fonts:** se eliminó el `<link>` a `fonts.googleapis.com` (Inter/Poppins). Ahora **fuentes del sistema** (system-ui/Segoe UI, ya estaban como fallback en el SCSS). Queda solo un `preconnect` a gstatic de Odoo core (NO bloqueante, despreciable).
- **odoo.conf:** añadido bloque de rendimiento — `workers = 2`, `max_cron_threads = 0`, `limit_time_cpu = 120`, `limit_time_real = 300`, `limit_request = 8192`, `limit_memory_soft = 805306368` (768MB), `limit_memory_hard = 1073741824` (1GB). Se aplica al reiniciar el contenedor.
- **Imagen hero:** `en_hero.jpg` optimizada de 282KB → 184KB (1440px, q82, progresivo).

**Resultado medido:** carga del home en estado estable **~0.1–0.24s** (la primera carga ~5–9s es la compilación del bundle de assets, una sola vez tras reinicio/-u).

**Nota operativa importante:** NO lanzar múltiples `docker exec ... odoo -u ...` en paralelo — causan `psycopg2 LockNotAvailable` (lock de `ir_module_module_dependency`) y matan el update. Hacer SIEMPRE un `-u` único y secuencial, esperar a que termine, luego reiniciar.
