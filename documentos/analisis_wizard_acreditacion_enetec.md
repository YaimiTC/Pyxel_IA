# Análisis del wizard de acreditación/importación — ENETRADEX

Fecha: 2026-07-10, actualizado 2026-07-14, actualizado 2026-07-15. Verificado contra el código **realmente desplegado** en `localhost:8469` y en el servidor real (`192.168.1.247:8469`).

**Repo correcto:** `D:\trabajo\Pyxel\IA\ENETEC_traspaso\ENETEC_traspaso\odoo-enetradex\addons` (confirmado con `docker inspect enetradex_odoo` → los volúmenes montan desde ahí, NO desde `enetradex-git`).

Archivos clave:
- Controlador: `pyxel_enetradex_website/controllers/wizard.py`
- Frontend del wizard (JS + plantilla): `pyxel_enetradex_website/views/en_wizard.xml`
- Página de confirmación final: `pyxel_enetradex_website/views/en_invited.xml` (template `en_wizard_done`)
- Modelo de la operación: `pyxel_import_backend/models/importation_process.py` (+ extensión en `pyxel_enetradex_backend`)
- Línea de solicitud (la que llena el wizard): `pyxel_enetradex_backend/models/en_import_request_line.py`
- Arquitectura paralela (solo backend, NO conectada al wizard): `pyxel_enetradex_backend/models/en_import_request_client.py` — multi-cliente por envío, con Unidad de medida.

---

## 0. Estado de implementación (actualizado 2026-07-10, sesión de implementación)

Ya implementado, actualizado en Docker (`-u pyxel_enetradex_website`) y **verificado con `odoo shell`** (sin necesidad de sesión web):

| Fix | Verificación |
|---|---|
| Botón "Omitir" oculto en modo importOnly | Código: `panelSolCli()` ahora solo lo muestra si `!S.importOnly` |
| Atajo `?op=1` también para proveedor (arranca en Oferta, no en Rol) | Código: nuevo flag `S.offerOnly`, `steps()` actualizado, mensaje de confirmación propio ("Oferta enviada") |
| Proveedor placeholder cuando no se resuelve ninguno (sin elegir vía, o "que me coticen") | **Probado en shell**: crea "Proveedor por designar" una sola vez, se reutiliza en envíos siguientes, el proceso queda correctamente en gate (`en_both_accredited=False`, etapa "PENDIENTE DE ACREDITACIÓN") |
| Mensaje informativo de visibilidad del proveedor (necesita oferta publicada) | Código: nota agregada bajo el checkbox en Mis datos |
| Validaciones de "Siguiente" (cantidad>0, nombre obligatorio, NIT 11 dígitos conectado al botón, elegir vía en Proveedor/Clientes, ≥1 línea en Oferta) | Código: función `stepBad()` centralizada — **solo del lado del navegador, ver sección 6** |
| Productos reales en los desplegables (Solicitud y Oferta) — antes lista fija en el JS que no coincidía con la base | **Probado en shell**: endpoint nuevo `/en/wizard/fuel_products` devuelve los 6 combustibles reales con su id (Diésel=16, Gasolina-91=15, Gasolina-83=19, Jet A-1=4, Fuel oíl=5, GLP=6). El backend ahora resuelve producto por id (`_resolve_product`), ya no por nombre a ciegas |
| Puertos no cargaban al crear el proceso desde el wizard | **Probado en shell**: `filtered_port` pasó de `[]` a `[["country_id","=",51],["hub_type","=","Port"]]` al llamar `proc._compute_filtered_hubs()` tras crear el proceso |

Todo pasó validación de sintaxis (Python, XML, JS) y el módulo cargó en Odoo sin errores nuevos.

**Pendiente de verificar en vivo (necesita sesión de navegador autenticada, no se puede probar por API):** que los botones realmente se vean deshabilitados en pantalla, que el desplegable de producto muestre bien las opciones, que el mensaje de "Oferta enviada" se vea correcto para un proveedor que reingresa.

### 0bis. Estado de implementación — sesión 2026-07-14: proveedor multi-cliente + OC + embarque por bloque

Implementado, actualizado en Docker (`-u pyxel_enetradex_website,pyxel_enetradex_backend`) y **verificado con `odoo shell` Y con sesión real de navegador** (login como proveedor de prueba, clic a clic hasta enviar):

| # | Fix | Verificación |
|---|---|---|
| A | Botón "Omitir" oculto también en modo `offerOnly` (antes solo en importOnly) | Confirmado en navegador: el botón no aparece al reingresar como proveedor acreditado |
| F | "Ya tengo clientes" (paso Clientes del proveedor) usa cartera real, vía nuevo endpoint `/en/wizard/my_clients` — antes eran 3 filas inventadas en el JS | Confirmado en navegador: aparece el cliente real de `en.counterparty.relation`, con su NIT y estado de acreditación reales |
| G | Nueva opción **"Es consignación"** en Clientes — mercancía sin cliente final definido, se le asigna un partner fijo `Enetec_Consignacion` (mismo patrón que "Proveedor por designar" del lado cliente) | Confirmado en navegador de punta a punta |
| H | Paso "Documentos del embarque" ahora también aparece para proveedor (antes `showEmbarque()` lo bloqueaba siempre con `if(S.role==='proveedor')return false`), condicionado a tener al menos un cliente resuelto (cartera, nuevos o consignación) — oculto si es "Difundir" | Confirmado en navegador: el stepper pasa de 3 a 4 pasos al marcar un cliente |
| B | `panelEmbarque` reescrito para proveedor: certificados compartidos a nivel de todo el proceso (calidad/exportación/origen) + un bloque por cada cliente con BL/AWB y 4 documentos (oferta firmada, factura, lista de empaque, permisos) | Confirmado en navegador, datos correctos en `en.import.request.document` |
| C | Al enviar, además de crear la `importation.process` con bloques, se crea **una Orden de Compra por cliente en estado borrador**, con el precio real tomado de la oferta (antes se perdía, quedaba en 0.0) y el BL/AWB | **Probado en shell y en navegador**: `purchase.order` en `draft`, `price_unit` = precio de la oferta |
| D | `action_en_approve_request` ya no duplica la OC si el proveedor ya la generó desde el wizard — la reutiliza y solo genera la oferta de venta | Probado en shell: 2 OC antes de aprobar, 2 OC después (no 4) |
| E | Documentos subidos por cliente/OC en el paso de embarque se pre-enlazan al expediente de esa OC (`pyxel.import.document`, vía `build_oc_expediente`) | Probado en shell: expediente de 6 slots por OC, se generan solos al crear la OC |
| I | Deduplicación por NIT (cliente) / MINCEX (`license_holder`, proveedor) antes de crear un partner nuevo — evita duplicar un cliente/proveedor ya acreditado y dejar la operación bloqueada sin explicación. Aplicado en: "Sumar clientes nuevos" del proveedor, "Difundir oferta", y "Ya tengo proveedor → Info" del cliente (este último no enviaba el MINCEX al backend, ya se corrigió) | Probado en shell: reutiliza el partner existente, no crea duplicado |

**Dos bugs adicionales encontrados durante la prueba en navegador (no se habían detectado con las pruebas por `odoo shell`) y ya corregidos:**

| # | Bug | Causa | Fix |
|---|---|---|---|
| 17 | País de origen del paso de embarque, elegido por el proveedor, se ignoraba — el proceso quedaba siempre con Cuba por defecto | El backend nunca leía `payload.shipData.country_id` para el rol proveedor (sí lo hacía para cliente) | `wizard.py`: la resolución de `origin` ahora prioriza `shipData.country_id`, igual que el lado cliente |
| 18 | **Bug preexistente, no introducido esta sesión pero expuesto por la nueva feature**: al enviar un proveedor con "Es consignación" (o cualquier bloque con cliente no acreditado), el envío fallaba con `ValidationError`: *"No se puede avanzar la operación... todavía falta acreditar ."* | `importation.process.create()` decide la etapa inicial mirando solo el campo legado `customer_id` — nunca `en_request_client_ids`. Como los procesos nuevos (cartera, nuevos, consignación) solo usan bloques, `customer_id` queda vacío y el código lo interpretaba como "sin cliente = vacuamente acreditado", saltando el gate directo a "Solicitud" — lo cual el `@api.constrains` de acreditación (que sí mira los bloques correctamente) rechazaba | `importation_process.py`: `create()` ahora también mira `en_request_client_ids` para decidir la etapa inicial; el mensaje de error del constraint también se corrigió para nombrar a los clientes reales de los bloques, no solo al `customer_id` legado |

Consecuencia esperada (no es un bug, es diseño consistente con "Proveedor por designar"): un proceso de **consignación** queda en la etapa "Pendiente de acreditación" para siempre hasta que un comercial acredite a `Enetec_Consignacion` o reemplace el bloque por un cliente real — la OC en borrador ya existe y es editable mientras tanto.

---

### 0ter. Estado de implementación — sesión 2026-07-15: 10 incidencias + reestructuración Oferta/Solicitud + unidad de medida

Implementado, actualizado en Docker (`-u pyxel_enetradex_backend,pyxel_enetradex_website`) y **verificado con pruebas E2E de punta a punta tanto en local como en el servidor real** (192.168.1.247, con verificación directa en su base de datos).

#### Bugs de registro encontrados y corregidos (previos a esta sesión, no introducidos hoy)

Antes de poder tocar nada de lo de abajo hubo que arreglar el arranque del módulo backend, que llevaba tiempo con piezas nuevas creadas pero nunca conectadas:

| Archivo | Problema | Fix |
|---|---|---|
| `pyxel_enetradex_backend/models/__init__.py` | No importaba `en_import_request_client`, `en_import_request_document` ni `crm_lead_wizard` — esos modelos existían en disco pero Odoo nunca los cargaba | Se agregaron los `from . import` faltantes |
| `pyxel_enetradex_backend/security/ir.model.access.csv` | Sin permisos para `en.import.request.client`, `.client.line`, `en.import.request.document`, `crm.lead.create.wizard`, `crm.lead.wizard.doc` — al activarse los modelos, cualquier intento de abrirlos daba "Error de acceso" | Filas nuevas siguiendo el mismo patrón que `en.import.request.line` (user: CRUD completo, portal: según el modelo) |
| `pyxel_enetradex_backend/__manifest__.py` | `views/crm_lead_wizard_views.xml`, `views/purchase_order_views.xml` y `views/menu_access.xml` existían en disco pero no estaban en la lista `data` — nunca se cargaban | Se agregaron las 3 rutas |
| `pyxel_enetradex_backend/security/groups.xml` | `menu_access.xml` referenciaba un grupo `group_comercial` que nunca se creó (solo existía `group_commercial`, "Inteligencia Comercial") — habría roto la carga del módulo al agregar `menu_access.xml` al manifest | Se creó `group_comercial` ("Comercial", superset de `group_commercial` vía `implied_ids`) |

**Hallazgo importante post-fix:** al comparar el código local contra el servidor real antes de desplegar, se confirmó que **el servidor tenía código más completo que el local** en `crm_lead.py` y `en_backend_views.xml` (vistas de acreditación multi-cliente en el backend — `en_customer_ids`, árbol/formulario detallado por cliente, vista de lista de Importaciones) — el local había perdido ese trabajo en algún momento (sospecha de la usuaria: al liberar espacio en Docker). No se sobrescribieron esos 2 archivos al desplegar.

#### Las 10 incidencias de la lista de la usuaria

| # | Incidencia | Fix |
|---|---|---|
| 1 | Unidad de medida del volumen de combustible no visible en el front | Selector real Litro/Galón (ids 11/25) agregado como columna "Unidad" en las 3 tablas de líneas (Solicitud del cliente, Oferta del proveedor, Solicitud/costos del proveedor). Requirió agregar el campo `product_uom_id` a `en.import.request.line` y `en.supply.offer.line` (que no lo tenían); `en.import.request.client.line` ya lo tenía. El backend ahora respeta la elección del usuario en vez de forzar siempre la unidad por defecto del producto |
| 2 | No dejaba seleccionar el país al acreditar un proveedor | No era un bug de lógica — era consecuencia de los bugs de registro de arriba (el modelo `en.import.request.client` daba error de acceso, lo cual rompía el flujo). Se resolvió al arreglar el registro |
| 3 | Documentos del proveedor se mezclaban con los del cliente al acreditar | El backend adjuntaba TODO lo que llegara con prefijo `doc:` al lead/partner del que envía el formulario, sin distinguir para quién era cada documento. Ahora se filtra por prefijo (`Proveedor\|` se salta cuando el que envía es un cliente, y viceversa con los tipos de cliente cuando el que envía es un proveedor) y se adjunta al partner correcto. Se revisó también el sentido inverso (proveedor acreditando cliente): el flujo normal ya separaba bien; se cerró un caso límite (edición de cliente abandonada a medias) |
| 4 | Nota de antigüedad máxima (1 año) en documentos del proveedor | Aviso agregado arriba de la cuadrícula de documentos del proveedor, en `docGrid()` |
| 5 | Certificado de no adeudo del cliente no aceptaba comprobante ONAT | Etiqueta de la tarjeta actualizada a "Certifico de no adeudo (o último comprobante de pago a la ONAT)" — solo el texto visible, la clave interna se mantuvo igual para no romper el expediente de acreditación que ya distingue ese documento por su nombre original |
| 6 | Envase de gasolina permitía Isomódulo (no puede entrar así al país) | Filtrado en las 3 tablas de líneas (front, dinámico según producto elegido) + corrección de respaldo en el backend (`_safe_packaging()`, aplica a oferta, solicitud del cliente y costos por cliente) |
| 7 | Campo de documento de MINCEX (no existe ese documento) | Se quitó "Código MINCEX" de la lista `DOCS.Proveedor` (era una tarjeta de subida de archivo). El campo de texto "Código MINCEX" (el número, no un documento) se mantuvo intacto |
| 8 | Agregar Perfil de compañía y Solvencia/reporte financiero a docs del proveedor | Agregados a `DOCS.Proveedor` |
| 9 | Notificar el error exacto en el llenado de información | `wizard_submit` ahora envuelve toda la lógica en un wrapper `_wizard_submit_impl` con try/except: si algo falla a mitad de proceso, hace rollback de la transacción y devuelve `{'ok': false, 'error': '<mensaje real>'}` en JSON en vez de dejar que Odoo devuelva una página de error HTML que el front no puede leer. El front ahora muestra ese mensaje específico en vez de "Inténtalo de nuevo" genérico |
| — | (la 10ª incidencia, la reestructuración Oferta/Clientes/Solicitud del proveedor) | ver más abajo |

#### Reestructuración Oferta → Clientes → Solicitud (proveedor, corrección de fondo)

**Antes:** el proveedor llenaba UNA sola tabla de Oferta (productos/cantidad/precio), y esa misma tabla se copiaba sin cambios a la Orden de Compra de **cada** cliente elegido — imposible vender productos o cantidades distintas a cada uno.

**Ahora:**
- **Oferta** se queda como estaba, pero su propósito se acotó explícitamente a catálogo/difusión pública (opciones "Difundir mi oferta" y "Publicar oferta").
- **Clientes** sin cambios (cartera, sumar nuevos, consignación, difundir).
- Nuevo paso **"Solicitud"** (reemplaza a "Documentos del embarque" solo para el rol proveedor) — un bloque por cada cliente elegido, con:
  - **Costos**: su propia tabla de producto/cantidad/unidad/precio (mismo patrón de validación y de bloqueo de gasolina+isomódulo que la Oferta).
  - **Embarque**: lo que ya existía (BL/AWB + documentos por cliente), ahora dentro del mismo bloque.
- Backend: `resolved_lines_by_key` (construido desde `payload.reqByClient`) reemplaza al `resolved_lines` compartido — cada Orden de Compra y cada bloque de `en.import.request.client` ahora usa las líneas de **su propio** cliente. El gate de creación pasó de exigir "clientes Y oferta con líneas" a solo "clientes" (los costos son opcionales, se completan después si hace falta, igual que el embarque).

#### Validación de cantidades y precios (no negativos, no cero)

- HTML: `min` en todos los campos numéricos de cantidad/precio (0.01 en líneas de producto, 0 en flete/seguro).
- JS: no se puede escribir un número negativo en la Solicitud del cliente (se limpia el campo al instante); el botón "+ Agregar" de Oferta y de Costos por cliente rechaza con aviso si cantidad o precio no son mayores que cero.
- Backend: mismas reglas replicadas como respaldo en las 3 rutas (oferta, solicitud del cliente, costos por cliente) — una línea con cantidad o precio ≤0 se descarta silenciosamente en vez de crearse.

#### Número de BL en mayúsculas

Aviso "Se guarda en mayúsculas" bajo el campo, con `text-transform:uppercase` visual y conversión real a mayúsculas del valor guardado (`S.provBl[k] = b.value.toUpperCase()`), sin importar cómo lo escriba el usuario.

#### Campos nuevos en `purchase.order`

`en_purchase_order.py` no tenía `customer_id` (real, escribible) ni `bl_number` — el código del wizard llevaba tiempo intentando escribirlos y fallando con `Invalid field`. Se agregaron ambos; el campo legado `en_customer_id` (related, solo lectura, apuntaba al `customer_id` único del proceso — vacío en multi-cliente) se dejó intacto por compatibilidad, ya no se usa para nada nuevo.

#### Despliegue y validación en el servidor real (192.168.1.247)

Dos rondas de despliegue esta sesión, cada una con: backup de BD (`pg_dump`) antes de tocar nada, comparación de código servidor-vs-local archivo por archivo antes de sobrescribir (para no pisar trabajo que solo existiera en el servidor), `-u` del módulo, reinicio del contenedor, verificación de salud (`/web/health`).

Prueba E2E completa en el servidor (usuarios de prueba `QA-SRV *`, verificado por consulta SQL directa):
- Proveedor con 2 clientes: cada Orden de Compra con su propio producto/cantidad/precio/unidad (uno en litros, otro en galones), BL guardado en mayúsculas, gasolina bloqueó Isomódulo, cantidad negativa rechazada con aviso.
- Cliente: unidad de medida en la tabla de Solicitud, cantidad negativa se limpia sola, país seleccionable al registrar un proveedor nuevo, comprobante ONAT visible, envío completo generó el proveedor y la solicitud con la unidad correcta.

---

## 1. Flujo verificado

### Entrada — usuario no autenticado
Cualquier botón "Acreditarme"/"Importar" del sitio apunta a `/en/wizard`. Sin sesión: 303 → `/web/login?redirect=/en/wizard`. Tras entrar, aterriza directo en el paso "Rol", no en "Mi cuenta".

### Elegir rol
Tarjetas **Cliente** / **Proveedor**.

### Camino CLIENTE (5-6 pasos)
1. **Rol** → Cliente
2. **Mis datos** → tipo (Pymes/Estatal/CNA/Sucursal) + documentos según tipo. Botón "Omitir → Solo quiero acreditarme" (oculto ahora si es importOnly).
3. **Solicitud** → productos (línea por producto, ahora con productos reales), forma de pago, presupuesto.
4. **Proveedor** (`panelCp`) → 3 vías: "ya tengo" (cartera/acreditar/invitar), "buscar en catálogo", "que me coticen".
5. **Documentos del embarque** (opcional) — solo si `showEmbarque()`.
6. **Resumen** → Enviar.

### Camino PROVEEDOR (5-6 pasos — actualizado 2026-07-15)
1. **Rol** → Proveedor
2. **Mis datos** → empresa extranjera + documentos (5 + Perfil de la compañía + Solvencia/reporte financiero, ya sin el documento de MINCEX que no existe).
3. **Oferta** → líneas producto/envase/cantidad/unidad/precio (productos reales), flete, seguro, total. **Alcance acotado**: es para catálogo/difusión pública, no para la operación puntual con clientes.
4. **Clientes** → 4 vías: "ya tengo" (cartera real), "sumar nuevos", "es consignación", "difundir oferta".
5. **Solicitud** (opcional, solo si hay ≥1 cliente resuelto — cartera/nuevos/consignación, no "difundir") → un bloque por cada cliente, con su propia tabla de costos (producto/cantidad/unidad/precio) **y** sus documentos de embarque (BL/AWB en mayúsculas + 4 documentos), reemplaza al viejo paso "Documentos del embarque" para este rol.
6. **Resumen** → Enviar.

### "Ya estoy acreditado" — ahora simétrico
- **Sin `?op=1`**, cualquier rol con lead activo → 303 a `/my/seguimiento`.
- **Con `?op=1`**:
  - **CLIENTE** → arranca en Solicitud → Proveedor → (Embarque) → Resumen.
  - **PROVEEDOR** → arranca en Oferta → Clientes → (Solicitud) → Resumen (ya arreglado).
- Sigue existiendo la plantilla huérfana `en_already_accredited` (`en_accredited.xml`), no la llama ninguna ruta.

### Después de enviar
Enviar → crea lead(s) en CRM → abogado acredita cada empresa → `importation.process` en "Pendiente de acreditación" hasta que ambas partes estén acreditadas → "Solicitudes para atender".

---

## 2. La duplicidad "dos formularios" (cliente vs backend) — resuelto el porqué (actualizado 2026-07-15)

Hay **dos estructuras de datos separadas** para "productos solicitados" del mismo `importation.process`:

1. **`en_request_line_ids`** (`en.import.request.line`) — la que llena la **Solicitud del wizard público del cliente**. Producto, Cantidad, Tipo de envase y, **desde 2026-07-15, también Unidad de medida** (`product_uom_id`, litro/galón, ids 11/25 — se agregó el campo que faltaba).
2. **`en_request_client_ids` → `product_line_ids`** (`en.import.request.client` / `.client.line`) — la que llena el **equipo manualmente** desde el backend ("Crear Clientes del envío"), y **desde 2026-07-15 también la Solicitud del wizard público del proveedor** (el nuevo paso "Solicitud" por cliente, ver sección 0ter). Soporta varios clientes por envío y ya tenía Unidad.

No es un accidente que sigan siendo dos modelos distintos: `action_en_approve_request()` en `importation_process.py` dice explícitamente *"por cada bloque de cliente genera OC+OV; si no hay bloques de cliente usa el flujo legado (customer_id único)"*. La Solicitud del **cliente** sigue sin crear bloques → sigue cayendo al flujo legado de un solo `customer_id`. La Solicitud del **proveedor**, en cambio, desde esta sesión sí crea bloques reales por cada cliente (ese era justamente el problema de fondo que motivó la reestructuración de la incidencia #10). Las dos estructuras siguen sin sincronizarse entre sí, pero **ya ninguna de las dos carece de Unidad de medida** — ese pendiente quedó resuelto.

---

## 3. Bugs y hallazgos

| # | Hallazgo | Estado |
|---|---|---|
| 1 | Cantidad de producto en Solicitud podía quedar en 0 | **Arreglado (front)** — bloquea "Siguiente"; **sin réplica en el back** |
| 2 | NIT — formato (11 dígitos) | **Arreglado (front)** — ahora si bloquea "Siguiente" (antes solo avisaba); **sin réplica en el back** |
| 3 | NIT — duplicado | Aviso visual solamente, no bloquea. No decidido si debe bloquear |
| 4 | Botón "Omitir" en modo importOnly | **Arreglado** |
| 5 | Proveedor sin atajo al volver ya acreditado (`?op=1`) | **Arreglado** — nuevo modo `offerOnly` |
| 6 | Sin proveedor / "que me coticen" → solicitud perdida | **Arreglado** — placeholder "Proveedor por designar", probado en shell |
| 7 | Mensaje de confirmación cruzado (acreditación↔importación) | Causa raíz sigue siendo la asimetría del bug #5 en visitas repetidas — con el fix del atajo de proveedor debería reducirse mucho, pero la pregunta de fondo (por qué `has_active_lead` a veces da falso) sigue sin reproducir en vivo |
| 8 | Botón "Acreditarme" visible con cliente ya acreditado | Sin tocar — es de navbar/tema, fuera del alcance de esta ronda |
| 9 | Oferta sin ninguna línea | **Arreglado (front)** — bloquea; **sin réplica en el back** |
| 10 | Clientes (paso proveedor) sin elegir vía | **Arreglado (front)** — bloquea; **sin réplica en el back** |
| 11 | Proveedor (paso cliente) sin elegir vía | **Arreglado (front)** — bloquea; **sin réplica en el back** |
| 12 | Falla de acreditación de proveedor por NIT existente | Sin reproducir — el form de proveedor no tiene campo NIT visible, causa exacta pendiente |
| 13 | Puertos no cargan tras crear proceso desde el wizard | **Arreglado** — `proc._compute_filtered_hubs()` tras crear, probado en shell |
| 14 | Diésel (y el resto de combustibles) no aparecían en las líneas | **Arreglado** — desplegables ahora usan productos reales por id (`/en/wizard/fuel_products`), ya no listas de texto que no coincidían con la base |
| 15 | Nombre de empresa y documentos no obligatorios en Mis datos | Documentos: **intencional** (decisión "todo opcional" del cliente). Nombre: ahora sí es obligatorio (front) |
| 16 | Dos estructuras paralelas de "productos solicitados" (wizard vs backend), nunca sincronizadas | Documentado en sección 2 — no es bug, es arquitectura a tener en cuenta |
| 17 | País de origen del paso de embarque del proveedor se ignoraba (siempre caía a Cuba) | **Arreglado 2026-07-14** — ver sección 0bis |
| 18 | Proceso con bloque de cliente no acreditado fallaba al crearse (`ValidationError` en el constraint de acreditación) porque `create()` no miraba los bloques para decidir la etapa inicial | **Arreglado 2026-07-14** — bug preexistente, no de esta feature; ver sección 0bis |
| 19 | Botón "Omitir" del paso Oferta (proveedor) visible incluso en modo `offerOnly`, donde no tiene sentido ("Omitir → Solo quiero acreditarme" para alguien ya acreditado) | **Arreglado 2026-07-14** — ver sección 0bis, punto A |
| 20 | "Ya tengo clientes" (proveedor) mostraba 3 filas inventadas en el JS, sin conexión real a la cartera; "Difundir oferta" y "Sumar clientes nuevos" creaban partners por nombre sin buscar si ya existían (mismo patrón que el bug #12, ahora confirmado y arreglado también del lado proveedor) | **Arreglado 2026-07-14** — ver sección 0bis, puntos F e I |
| 21 | Unidad de medida del volumen (litro/galón) no existía como selector en ninguna de las 3 tablas de líneas | **Arreglado 2026-07-15** — ver sección 0ter |
| 22 | País no seleccionable al acreditar un proveedor | **Arreglado 2026-07-15** — no era un bug de lógica, era el modelo `en.import.request.client` dando "Error de acceso" por falta de permisos (bug de registro, ver sección 0ter) |
| 23 | Documentos del proveedor se mezclaban con los del cliente (y viceversa) al acreditar una contraparte | **Arreglado 2026-07-15** — filtrado por prefijo en el backend, ver sección 0ter |
| 24 | Sin nota de antigüedad máxima en documentos del proveedor | **Arreglado 2026-07-15** |
| 25 | Certificado de no adeudo (cliente) no aceptaba comprobante de pago ONAT como alternativa | **Arreglado 2026-07-15** — solo cambio de etiqueta visible |
| 26 | Envase Isomódulo disponible para gasolina (no puede entrar así al país) | **Arreglado 2026-07-15** — front + respaldo en backend |
| 27 | Documento de MINCEX en la lista de documentos del proveedor (ese documento no existe, solo el código como texto) | **Arreglado 2026-07-15** |
| 28 | Faltaban Perfil de la compañía y Solvencia/reporte financiero en documentos del proveedor | **Arreglado 2026-07-15** |
| 29 | Errores del envío del wizard mostraban siempre "Inténtalo de nuevo" sin el motivo real | **Arreglado 2026-07-15** — backend ahora captura la excepción, hace rollback y devuelve el mensaje real en JSON |
| 30 | Oferta compartida entre todos los clientes del proveedor — imposible vender productos/cantidades/precios distintos a cada uno | **Arreglado 2026-07-15** — reestructuración Oferta(catálogo)/Clientes/Solicitud(costos por cliente), ver sección 0ter |
| 31 | Cantidad y precio de las líneas de producto aceptaban valores negativos o cero | **Arreglado 2026-07-15** — bloqueado en front (HTML + JS) y como respaldo en el backend |
| 32 | Número de BL/AWB se guardaba tal cual lo escribiera el usuario (mayúsculas/minúsculas mezcladas) | **Arreglado 2026-07-15** — se normaliza a mayúsculas siempre |

## 4. Validaciones — actualizado 2026-07-15, ya hay algunas del lado del servidor

Auditoría original de `wizard_submit`: **cero** `raise`/`ValidationError`/chequeo de negocio para cantidad, nombre, NIT, vía de proveedor u oferta vacía. Todo el bloqueo vivía únicamente en `next.disabled` del JavaScript (`stepBad()`). Quien desactivara JS, o mandara el POST directo a `/en/wizard/submit`, se saltaba esas validaciones sin ningún obstáculo del servidor.

**Actualizado 2026-07-15 — ya hay 3 validaciones espejo en el backend:**
- Cantidad y precio de cada línea de producto deben ser mayores que cero (oferta, solicitud del cliente, costos por cliente) — una línea que no cumpla se descarta silenciosamente en vez de crearse.
- Envase Isomódulo se corrige a Isotanque si el producto es gasolina, sin importar lo que llegue en el payload (`_safe_packaging()`).
- Cualquier excepción no controlada durante el envío ya no revienta con una página de error HTML — se captura, se hace rollback de la transacción, y se devuelve `{'ok': false, 'error': '<mensaje real>'}` en JSON (bug #29/incidencia #9 de la lista de la usuaria).

**Sigue sin réplica en el back** (queda igual que antes): nombre de empresa obligatorio, NIT con 11 dígitos, elegir una vía de proveedor/clientes, al menos una línea en Oferta. Riesgo real sigue siendo bajo por la misma razón de siempre (nivel de protección históricamente aceptado en este wizard), pero sigue siendo una brecha de integridad de datos pendiente de decisión.

## 5. Pendientes de reproducir/decidir

- Causa exacta de por qué `has_active_lead` a veces da falso en visitas repetidas (bug #7) — único punto que sigue sin explicación confirmada tras la validación E2E.
- Confirmar visualmente en navegador (no solo por shell): desplegables de producto, botones bloqueados. *(Actualizado: ya se hizo para las incidencias de 2026-07-15, en local y en servidor real — pendiente solo para lo de sesiones anteriores a esa fecha.)*
- Decidir si se agregan validaciones espejo en el backend para lo que falta (nombre, NIT, elegir vía) — sección 4.
- ~~Decidir si se agrega Unidad de medida a `en.import.request.line`~~ — hecho 2026-07-15, sección 2.
- Consignación (cliente vacío, solo proveedor+país) — sigue sin decidir si se implementa como funcionalidad nueva (nota: ya existe como una de las 4 vías del paso Clientes del proveedor desde 2026-07-14, esto se refiere a si también debe existir del lado cliente).
- Decidir si conviene limpiar el campo legado `en_customer_id` de `purchase.order` (related, solo lectura) ahora que existe `customer_id` real — no se tocó esta sesión por prudencia, ver sección 0ter.

## 5bis. Validación E2E en el servidor real (192.168.1.247) — 2026-07-13

Hecha por `odoo shell` vía SSH (sin login web), en una sola transacción con limpieza de todos los registros de prueba al final (`ZZTEST_E2E_*`, eliminados; no queda residuo en producción). Confirmado:

- Cliente y proveedor nuevos quedan con `contact_type_id` asignado (antes vacío).
- MINCEX del proveedor se guarda (`license_holder`).
- Búsqueda por NIT (cliente) / MINCEX (proveedor) no duplica al repetir.
- Proveedor sin MINCEX se crea sin error.
- Aviso de NIT inválido (≠11 dígitos) se dispara correctamente (`_onchange_company_vat_check_length`).
- Aprobar en cartera (mover a etapa de acreditación) ya no falla — partner queda `is_accredited=True` con `contact_type_id` correcto.
- Bug `NewId` reproducido con `env['crm.lead'].new(...)` (registro virtual, sin guardar) — los campos que antes rompían (`en_origin_label`, `en_also_registered`, `en_timeline_html`) ya no fallan. Causa raíz: `lead.id` (NewId) se pasaba a un dominio SQL; el fix usa `lead._origin.id or (lead.id if isinstance(lead.id, int) else False)`.
- Oferta completa de proveedor (líneas, flete, seguro, total) creada y calculada correctamente.
- Columna "Cliente" del expediente confirmada con datos **reales** de producción: IMP00036, IMP00150, IMP00151 (todas con cliente "Pam Panly S.U.R.L" por bloque).

País que no carga (bug #13) y falla de NIT existente en proveedor (bug #12): no se volvieron a reproducir ni mencionar durante esta ronda — posible que fueran síntomas ya cubiertos por los fixes de puertos/productos, pero no confirmado explícitamente.

---

## 5ter. Arquitectura solicitud / OC / documentación (analizada 2026-07-13/14)

Antes de implementar la multi-cliente del proveedor se investigó cómo encajan estos conceptos en el back, porque cada cliente de un mismo envío genera su propia Orden de Compra (OC) y su propia documentación:

- **"Solicitud"** = el registro `importation.process` en sí (uno por operación), con uno o varios **bloques de cliente** (`en.import.request.client`, uno por cliente/BL dentro del mismo envío).
- **OC (`purchase.order`)** — una por bloque de cliente. Antes de esta sesión, la OC **solo** se creaba manualmente por un comercial (botón "Aprobar solicitud" → `action_en_approve_request()`), nunca desde el wizard público — ni para cliente ni para proveedor. Desde esta sesión, el proveedor la genera ya en **borrador** al enviar el wizard (con precio real de su oferta); el comercial la revisa y decide.
- **Documentación de la importación** (`pyxel.import.document` con `purchase_order_id=False`) — certificados que aplican a **todo el proceso**, no a un cliente en particular (calidad, exportación, origen). Catálogo `IMPORT_DOCS`.
- **Documentación por OC** (`pyxel.import.document` con `purchase_order_id` puesto) — BL/AWB, oferta firmada, factura comercial, lista de empaque, permisos, DM. Catálogo `OC_DOCS`. Se genera automáticamente al crear cada OC (`build_oc_expediente`, disparado por el `create()` de `purchase.order`).
- **Antes de que exista la OC** (durante el wizard, antes de aprobar), el lugar correcto para subir estos mismos documentos por cliente es `en.import.request.document` (`client_block_id`) — modelo que ya existía en el back pero nunca se conectaba al wizard público. Esta sesión lo conectó: el proveedor sube ahí sus documentos por cliente en el paso "Documentos del embarque", y al generarse la OC, esos archivos se pre-enlazan automáticamente al expediente de esa OC (punto E).

En resumen, la jerarquía queda:

```
importation.process (la "solicitud")
 ├─ documentación de la importación (compartida, sin OC)
 └─ en_request_client_ids (un bloque por cliente)
     ├─ bl_number, product_line_ids
     ├─ en.import.request.document (documentos subidos antes de aprobar)
     └─ purchase_order_id → purchase.order (la OC de ese cliente)
          └─ pyxel.import.document con purchase_order_id (expediente de esa OC,
             pre-enlazado desde en.import.request.document si hay archivo)
```

---

## 6. Tabla de partición de equivalencia — casos de prueba

Leyenda: **OK** = bloquea correctamente · **ARREGLADO** = corregido y verificado esta sesión · **BUG** = confirmado, no bloquea · **revisar en vivo** = no se pudo verificar solo con el código.

### Entrada y rol

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Elegir Rol | Cliente o Proveedor marcado | Ningún rol marcado | Pulsar Siguiente sin elegir tarjeta | Botón bloqueado | OK |
| Entrada `?op=1`, cliente con oportunidad activa | rol=cliente + lead activo | — | Cliente acreditado entra por "Importar" | Arranca en Solicitud | OK |
| Entrada `?op=1`, proveedor con oportunidad activa | rol=proveedor + lead activo | — | Proveedor acreditado entra por `?op=1` | Arranca en Oferta | ARREGLADO — revisar en vivo |
| Entrada sin `?op=1`, con oportunidad activa | Cualquier rol, lead activo, sin op | — | Clic en "Acreditarme" ya con lead | Redirige a `/my/seguimiento` | revisar en vivo — a veces no se activó en 2ª visita (causa raíz pendiente) |

### Mis datos

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Tipo de cliente | Elegido | Sin elegir | Avanzar sin tipo | No bloquea (intencional) | OK intencional |
| Nombre de la empresa | No vacío | Vacío | Avanzar en blanco | Bloquear | ARREGLADO (front) — sin réplica en back |
| NIT — formato | Vacío, o 11 dígitos | Longitud≠11 o no numérico | Escribir "123ABC" | Bloquear | ARREGLADO (front) — sin réplica en back |
| NIT — duplicado | No usado por otra empresa | Ya existe | NIT de empresa acreditada | Bloquear o advertir | no bloquea, solo aviso |
| Documentos obligatorios | Todos subidos | Faltan | Avanzar sin subir | No bloquea (intencional) | OK intencional |
| Documento rechazado por IA | Ninguno rechazado presente | Hay uno sin reemplazar | Subir, esperar "rechazado" | Bloquear | OK |

### Solicitud (cliente)

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Producto de la línea | Producto real seleccionado | — | Elegir del desplegable | Coincide con el id real en la base | ARREGLADO — probado en shell (6/6 productos resuelven) |
| Envase gasolina | Isotanque | Isomódulo | Elegir gasolina, revisar envase | Isomódulo no aparece | **ARREGLADO 2026-07-15**, confirmado |
| Unidad por línea | Litro o Galón | — | Elegir Galón | Se guarda esa unidad (antes el modelo ni tenía el campo) | **ARREGLADO 2026-07-15**, confirmado en BD (servidor) |
| Cantidad por línea | > 0 | 0, vacía o negativa | Escribir -30 | El campo se limpia solo al escribir un negativo; 0/vacío bloquea "Siguiente" | **ARREGLADO 2026-07-15** — ahora también limpia negativos en vivo, confirmado en servidor; validación de 0/vacío sigue solo en front |
| Forma de pago | Seleccionada | Vacía | No elegir | Bloquear | OK |
| Presupuesto | > 0 | ≤0 o vacío | Dejar vacío | Bloquear | OK |
| Botón "Omitir" visible | Solo si NO importOnly | En importOnly | Entrar con `?op=1` acreditado | No debería aparecer | ARREGLADO |

### Proveedor (paso cliente)

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Elección de vía | Una de las 3 tarjetas | Ninguna | Avanzar sin elegir | Bloquear | ARREGLADO (front) — sin réplica en back |
| "Ya tengo" → cartera | Proveedor marcado | Ninguno | No marcar y avanzar | Bloquear | revisar en vivo |
| "Buscar en catálogo" | Oferta seleccionada | Ninguna | No elegir y avanzar | Bloquear | revisar en vivo |
| "Acreditar nuevo" → País del proveedor extranjero | Seleccionable y persiste | Bloqueado/no respondía | Elegir un país del desplegable | Se guarda y se mantiene seleccionado | **ARREGLADO 2026-07-15** — confirmado en local y servidor; causa real era el modelo `en.import.request.client` sin permisos (ver sección 0ter), no un bug de este selector en sí |
| Envío con "cotiza" o sin vía | Crea proceso con placeholder | — | Completar y enviar | Proceso visible, en gate | ARREGLADO — probado en shell (placeholder + gate confirmados) |

### Oferta (proveedor) — actualizado 2026-07-15, alcance acotado a catálogo/difusión

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Producto de la línea | Producto real seleccionado | — | Elegir del desplegable | Coincide con id real | ARREGLADO |
| Envase gasolina | Isotanque | Isomódulo | Elegir gasolina, revisar opciones de envase | Isomódulo no aparece en la lista | **ARREGLADO 2026-07-15**, confirmado en local y servidor |
| Unidad de la línea | Litro o Galón, elegido por el usuario | — | Elegir Galón y agregar línea | Se guarda esa unidad, no la del producto por defecto | **ARREGLADO 2026-07-15**, confirmado en BD (servidor) |
| Cantidad y precio de la línea | Ambos > 0 | Alguno ≤0 (incluye negativos) | Escribir -50 o 0 y pulsar "+ Agregar" | Bloquear con aviso, no agregar la línea | **ARREGLADO 2026-07-15 (front + backend)** — confirmado: rechazo con aviso probado en servidor |
| Líneas de producto | ≥1 | 0 líneas | No agregar y avanzar | Bloquear | ARREGLADO (front) — sin réplica en back |

### Clientes (paso proveedor) — 4 vías desde 2026-07-14

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Elección de vía | Una de las 4 tarjetas | Ninguna | Avanzar sin elegir | Bloquear | OK (front) — sin réplica en back |
| "Ya tengo clientes" (cartera real) | ≥1 marcado, de la cartera real (`/en/wizard/my_clients`) | Ninguno | No marcar y avanzar | Bloquear | **Confirmado en navegador** — carga el cliente real con NIT y estado de acreditación |
| "Sumar clientes nuevos" | ≥1 con datos completos | Ninguno | No agregar y avanzar | Bloquear | OK — dedup por NIT confirmado (no duplica cliente existente) |
| "Es consignación" | Se selecciona, no requiere datos | — | Elegir y avanzar | Crea bloque con `Enetec_Consignacion`, proceso queda en gate | **Confirmado en navegador** de punta a punta |
| "Difundir mi oferta" | ≥1 marcado | Ninguno | No marcar y avanzar | Bloquear | revisar en vivo — dedup por nombre confirmado en shell |
| Paso "Solicitud" tras Clientes (renombrado desde "Documentos del embarque", 2026-07-15) | Aparece si hay ≥1 cliente resuelto (cartera/nuevos/consignación), aunque sea uno solo | "Difundir" o ningún cliente | Marcar un solo cliente | Stepper muestra el paso "Solicitud" y se puede entrar | **ARREGLADO/confirmado 2026-07-15 en local y servidor** — se probó explícitamente que con un solo cliente ya alcanza (reporte inicial de la usuaria sugería que hacían falta 2, no se pudo reproducir con el código actual) |

### Solicitud — costos + embarque por cliente (proveedor, nuevo 2026-07-15)

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Costos de cada cliente | Independientes entre sí (producto/cantidad/unidad/precio propios) | Copiados de otro cliente o de la Oferta | Cargar productos distintos a 2 clientes | Cada Orden de Compra queda con SU producto/cantidad/precio | **ARREGLADO 2026-07-15** — confirmado en BD (local y servidor): 2 OC con productos y precios distintos |
| Envase gasolina (bloque de costos) | Isotanque | Isomódulo | Elegir gasolina en un bloque de cliente | Isomódulo no aparece | **ARREGLADO 2026-07-15**, confirmado |
| Unidad por línea de costos | Litro o Galón, por cliente | — | Cliente A en litros, Cliente B en galones | Cada OC guarda su propia unidad | **ARREGLADO 2026-07-15**, confirmado en BD |
| Cantidad y precio de costos | Ambos > 0 | ≤0 | Escribir negativo y agregar | Bloquear con aviso | **ARREGLADO 2026-07-15**, confirmado |
| Número de BL/AWB | Cualquier texto | — | Escribir en minúscula | Se guarda en MAYÚSCULAS | **ARREGLADO 2026-07-15**, confirmado en BD (servidor) |
| Costos vacíos al enviar | Se permite (paso opcional) | — | Avanzar sin cargar costos de un cliente | Proceso y OC se crean igual, sin líneas, para completar después | OK por diseño |

### Documentos del embarque (opcional, cliente) / documentos dentro de Solicitud (proveedor)

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Visibilidad del paso (cliente) | Solo si `cpHas≠cotiza` y NO("ya tengo"+"invitar") | Fuera de esa regla | Probar las 5 combinaciones | Coincide con `showEmbarque()` | OK en código, confirmar en vivo |
| Documentos del proveedor no se mezclan con los del cliente al acreditar una contraparte | Cada documento va al partner correcto | Mezclados en el mismo lead/partner | Cliente acredita proveedor con documentos, y viceversa | Cada set de documentos queda en su propio partner/expediente | **ARREGLADO 2026-07-15** — ambos sentidos revisados, incluyendo caso límite de edición abandonada |

### Envío final

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Con proveedor resuelto | Crea proceso completo | — | Elegir proveedor real y enviar | Proceso visible en operaciones y back | OK |
| Sin proveedor resuelto | Crea proceso con placeholder | — (ya no hay clase inválida real) | Enviar con "cotiza" o sin vía | Proceso rastreable, en gate | ARREGLADO — probado en shell |
| Puerto tras crear | `filtered_port` calculado desde el inicio | Vacío hasta reseleccionar país | Crear proceso, abrir en el back | Puerto con opciones ya cargadas | ARREGLADO — probado en shell (`[]` → dominio correcto) |
| Mensaje de confirmación | Coincide con el modo real | Texto cruzado | Repetir secuencia de Annia | Siempre coincide | Mejorado con el fix del atajo; causa raíz de fondo (bug #7) aún pendiente |

---

## 7. Manual de usuario — cómo usar el wizard de acreditación

Esta sección explica el wizard en lenguaje sencillo, como guía para quien lo use o dé soporte — no es un reporte técnico, es "así se usa".

### Si eres CLIENTE (empresa cubana que quiere importar combustible)

**Para acreditarte por primera vez:**
1. Entra a la web y pulsa **"Acreditarme"**.
2. Si no tienes cuenta, el sistema te pide crearla primero (o iniciar sesión si ya la tienes) — después te lleva directo al asistente.
3. Elige la tarjeta **"Cliente"**.
4. En "Mis datos", elige tu tipo de empresa (Pymes, Estatal, CNA o Sucursal Extranjera) — al elegirlo aparece la lista de documentos que te corresponde subir. Escribe el nombre de tu empresa (obligatorio) y, si tienes NIT a mano, escríbelo — debe tener exactamente 11 números. *(Para el certificado de no adeudo puedes subir el certificado en sí, o en su lugar el último comprobante de pago a la ONAT.)*
   - *Si solo quieres acreditarte y todavía no vas a pedir una importación*, hay un botón **"Omitir → Solo quiero acreditarme"** que te salta directo al resumen.
5. En "Solicitud", indica qué combustible necesitas, cuánto (con su unidad: litro o galón, según lo que diga tu factura), y elige forma de pago y presupuesto disponible. Puedes agregar varios productos con el botón "+ Agregar producto". La gasolina solo admite envase Isotanque. Las cantidades no pueden ser cero ni negativas.
6. En "Proveedor", dinos cómo prefieres conseguirlo:
   - **"Ya tengo un proveedor"** — lo buscas en tu cartera, lo registras si aún no está en el sistema, o lo invitas por correo.
   - **"Buscar en el catálogo"** — te mostramos ofertas ya publicadas de proveedores acreditados para el producto que pediste.
   - **"Que me coticen"** — ENETEC sale al mercado por ti y te trae la mejor oferta (pliego de concurrencia).
7. Si tu solicitud lo amerita, puedes adjuntar documentos del embarque (opcional, se pueden aportar después).
8. Revisa todo en "Resumen" y pulsa **Enviar**.

Después de enviar: un abogado revisa tus documentos y te acredita. Tu solicitud queda **"Pendiente de acreditación"** hasta que tú y tu proveedor estén ambos acreditados — no hace falta que esperes, la solicitud sigue su curso sola y se activa apenas se completen ambas acreditaciones.

**Si ya estás acreditado y quieres pedir otra importación:**
- Pulsa **"Importar"** (no "Acreditarme") — el sistema ya sabe quién eres y te lleva directo a "Solicitud", sin repetirte los pasos de Rol y Mis datos.
- Si en cambio pulsas "Acreditarme" estando ya acreditado, te manda a tu página de seguimiento — no hace falta que vuelvas a acreditarte.

### Si eres PROVEEDOR (empresa extranjera que quiere vender combustible en Cuba)

**Para acreditarte por primera vez:**
1. Entra y pulsa **"Acreditarme"** → elige la tarjeta **"Proveedor"**.
2. En "Mis datos" completa el nombre de tu empresa, país, clasificación (Productor/Comerciante) y los documentos requeridos: escritura de constitución, inscripción en registro mercantil, poder acreditativo, certificado de cuenta bancaria, perfil de la compañía y solvencia/reporte financiero. *(El código MINCEX se pide como dato de texto, no hace falta subir ningún documento para eso. Los documentos no deben tener más de un año de antigüedad — si son más viejos, hay que actualizarlos.)*
3. En "Oferta", registra tu catálogo público: producto real del desplegable, envase (para gasolina solo se permite Isotanque, Isomódulo no está disponible), cantidad, **unidad (litro o galón)**, precio; agrega flete y seguro — el total se calcula solo. *Esta oferta es para el catálogo/difusión pública — el detalle real de cada venta a un cliente concreto se completa más adelante, en "Solicitud".*
4. En "Clientes", dinos a quién le ofreces (4 opciones):
   - **"Ya tengo clientes"** — marca uno o varios de tu cartera real (los clientes con los que ya tienes una relación registrada).
   - **"Sumar clientes nuevos"** — acredítalos con sus datos completos (nombre, NIT, dirección, contacto) o invítalos por correo. Si el NIT que escribes ya pertenece a un cliente existente, el sistema lo reconoce y no crea uno duplicado.
   - **"Es consignación"** — úsala cuando la mercancía viaja sin un cliente final definido todavía; ENETEC queda como responsable temporal del envío hasta que se asigne un comprador.
   - **"Difundir mi oferta"** — se la mandamos a los clientes que aceptan recibir ofertas de proveedores (esta opción no genera una importación, solo publicidad de tu oferta).

   Si elegiste cartera, clientes nuevos o consignación (con al menos un cliente marcado), aparece un paso más:
5. **"Solicitud"** (opcional): país de origen y certificados que aplican a todo el envío (calidad/exportación/origen), y — por cada cliente que agregaste, con un solo cliente ya es suficiente — un bloque con:
   - **Costos**: los productos, cantidades, unidad (litro/galón) y precios que le vendes específicamente a ESE cliente (no se repite la oferta del catálogo, cada cliente tiene lo suyo).
   - **Embarque**: el número de BL/AWB (se guarda siempre en mayúsculas, sin importar cómo lo escribas) y sus documentos propios (oferta firmada, factura comercial, lista de empaque, permisos).

   Puedes dejar los costos y/o los documentos en blanco y completarlos después.
6. Revisa en "Resumen" y pulsa **Enviar**.

**Qué pasa al enviar con clientes reales:** además de tu oferta de catálogo, se crea una importación real con una Orden de Compra en borrador **por cada cliente**, ya con los productos, cantidades y precios que le cargaste a ese cliente en "Solicitud" — el equipo comercial la revisa, la completa y la aprueba; tú no tienes que volver a escribir esos datos.

**Si ya estás acreditado y quieres actualizar tu oferta:**
- Pulsa **"Importar"** igual que el cliente — ahora también te lleva directo a "Oferta", sin repetir Rol/Mis datos (antes tenías que volver a empezar desde cero; ya se corrigió). El paso de Clientes y Solicitud funcionan exactamente igual que la primera vez.

**Para que tu empresa aparezca en el catálogo público** (donde los clientes te buscan sin que tú los invites), marca la casilla "Mis datos pueden ser visibles para clientes" en Mis datos — pero recuerda: además de marcar esa casilla, necesitas tener al menos una oferta publicada con productos y precios; si no, aunque seas visible, no vas a aparecer con nada que ofrecer.

### Preguntas frecuentes

- **¿Qué pasa si no tengo proveedor todavía y quiero que ENETEC me cotice?** Tu solicitud se registra igual, con un proveedor "por designar" mientras se consigue uno real — no se pierde tu información, y en cuanto el comercial encuentre proveedor, lo asigna sin que tengas que volver a enviar nada.
- **¿Tengo que llenar todo en Mis datos?** El nombre de tu empresa sí es obligatorio. Los documentos no son obligatorios para avanzar — se revisan igual cuando el abogado evalúa tu acreditación.
- **¿Puedo cambiar de opinión después de omitir la solicitud?** Sí, desde el Resumen hay un enlace "¿Quieres añadir solicitud?" que te regresa al paso Solicitud.
