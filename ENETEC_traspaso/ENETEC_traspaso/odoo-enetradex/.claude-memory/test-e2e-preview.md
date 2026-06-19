---
name: test-e2e-preview
description: Cómo correr el test E2E del flujo de acreditación+importación por el panel de preview (login y conducción)
metadata:
  node_type: memory
  type: reference
---

Para recorrer el flujo ENETEC de punta a punta en el panel de preview (proxy
`.claude/preview_proxy.py`, 8470→8469) ver [[proyecto-enetec-odin]].

**Login en el navegador headless del preview:** el submit del formulario de
`/web/login` NO persiste la cookie de sesión (el headless no guarda la cookie
`HttpOnly` que llega en el 303 de navegación). SÍ funciona loguear con `fetch`
dentro de la página (guarda la cookie en su jar):
```js
const p=await (await fetch('/web/login')).text();
const csrf=p.match(/name="csrf_token"[^>]*value="([^"]+)"/)[1]; // ¡token completo, tiene una 'o' separadora!
await fetch('/web/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
  body:new URLSearchParams({login,password,csrf_token:csrf,redirect:''}).toString(),credentials:'include',redirect:'manual'});
```
Backend en `/web` (no `/odoo`, da 404). Statusbar OWL: el click DOM no persiste;
usar `call_kw` (`/web/dataset/call_kw`) para transiciones de etapa/estado — son
las mismas acciones del ORM que dispara la UI. Ensanchar viewport (1400px) para
que la statusbar muestre las etapas como pills.

**Credenciales:** admin `admin@enetec.test` / `Enetec2026`. PyME de prueba sin
acreditar creada en el test: `pyme.caribe@test.cu` / `pyme123`.

**Flujo verificado (2026-06-15):** wizard `/en/wizard?op=1` (rol Cliente → Mis
datos Pymes + docs → Solicitud Diésel → Proveedor "Acreditar nuevo") crea lead
PyME (self) + lead proveedor (counterparty) + relación contraparte +
`importation.process` en el gate. El abogado mueve ambos leads a "APROBADOS EN
CARTERA" (is_accreditation_stage) → `is_accredited` y auto-avance del proceso
fuera del gate a "SOLICITUDES PARA ATENDER". Comercial avanza etapas hasta
"DEVOLUCIÓN DEL CONTENEDOR"; contenedor `importation.load` con fechas
arrival/release(precinta)/extraction/return → estado `returned`.

**Hallazgos abiertos (a pulir):** (1) `en.counterparty.relation` queda `pending`
tras acreditar ambas partes (debería pasar a `active`). (2) `country_origin_id`
del proceso se fija a Cuba en el wizard (debería ser el país del proveedor).
(3) docs del proveedor subidos en el wizard se adjuntan al lead del cliente, no
al del proveedor. (4) NIT en "Mis datos" del wizard no se captura (input sin id).
Ver [[requisitos-enetec-cliente]] y [[patron-grancomerx-dual-servicio]].
