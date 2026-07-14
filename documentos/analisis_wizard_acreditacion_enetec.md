# Análisis del wizard de acreditación/importación — ENETRADEX

Fecha: 2026-07-10, actualizado 2026-07-14. Verificado contra el código **realmente desplegado** en `localhost:8469`.

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

### Camino PROVEEDOR (5 pasos, sin embarque)
1. **Rol** → Proveedor
2. **Mis datos** → empresa extranjera + 5 documentos.
3. **Oferta** → líneas producto/envase/cantidad/precio (productos reales), flete, seguro, total.
4. **Clientes** → 3 vías: "ya tengo", "sumar nuevos", "difundir oferta".
5. **Resumen** → Enviar.

### "Ya estoy acreditado" — ahora simétrico
- **Sin `?op=1`**, cualquier rol con lead activo → 303 a `/my/seguimiento`.
- **Con `?op=1`**:
  - **CLIENTE** → arranca en Solicitud → Proveedor → (Embarque) → Resumen.
  - **PROVEEDOR** → arranca en Oferta → Clientes → Resumen (ya arreglado).
- Sigue existiendo la plantilla huérfana `en_already_accredited` (`en_accredited.xml`), no la llama ninguna ruta.

### Después de enviar
Enviar → crea lead(s) en CRM → abogado acredita cada empresa → `importation.process` en "Pendiente de acreditación" hasta que ambas partes estén acreditadas → "Solicitudes para atender".

---

## 2. La duplicidad "dos formularios" (cliente vs backend) — resuelto el porqué

Hay **dos estructuras de datos separadas** para "productos solicitados" del mismo `importation.process`:

1. **`en_request_line_ids`** (`en.import.request.line`) — la que llena el **wizard público**. Producto, Cantidad, Tipo de envase. **Sin Unidad de medida.**
2. **`en_request_client_ids` → `product_line_ids`** (`en.import.request.client` / `.client.line`) — la que llena el **equipo manualmente** desde el backend ("Crear Clientes del envío"). Soporta varios clientes por envío y **sí tiene Unidad** (litro/galón, ids 11/25).

No es un accidente: `action_en_approve_request()` en `importation_process.py` dice explícitamente *"por cada bloque de cliente genera OC+OV; si no hay bloques de cliente usa el flujo legado (customer_id único)"*. El wizard público nunca crea bloques de cliente → siempre cae al flujo legado → nunca pasa por el modelo que tiene Unidad. Las dos estructuras **no se sincronizan entre sí**.

**Implicación:** si se quiere que las solicitudes hechas desde el wizard público también tengan Unidad, hay que agregar el campo directamente a `en.import.request.line` (mismo patrón: `product_uom_id` con dominio restringido a litro/galón) — no tiene sentido intentar rutear el wizard hacia el sistema de bloques de cliente, que está pensado para uso interno del equipo con envíos consolidados de varios compradores.

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

## 4. Validaciones — confirmado, ninguna existe en el back

Auditoría completa de `wizard_submit`: **cero** `raise`/`ValidationError`/chequeo de negocio para cantidad, nombre, NIT, vía de proveedor u oferta vacía. Todo el bloqueo vive únicamente en `next.disabled` del JavaScript (`stepBad()`). Quien desactive JS, o mande el POST directo a `/en/wizard/submit`, se salta las 5 validaciones sin ningún obstáculo del servidor.

**Riesgo real:** bajo — es el mismo nivel de protección que ya tenía el resto del wizard antes de esta ronda (todo el diseño actual confía en JS del lado cliente). Pero es una brecha de integridad de datos: nada impide que llegue una solicitud con cantidad 0 o sin proveedor por una vía distinta al formulario normal.

**Pendiente de decidir:** ¿se agregan también validaciones espejo en `wizard_submit` (rechazar con `{'ok': False, 'error': '...'}` si falta algo crítico), o se acepta que el JS es suficiente por ahora?

## 5. Pendientes de reproducir/decidir

- Causa exacta de por qué `has_active_lead` a veces da falso en visitas repetidas (bug #7) — único punto que sigue sin explicación confirmada tras la validación E2E.
- Confirmar visualmente en navegador (no solo por shell): desplegables de producto, botones bloqueados.
- Decidir si se agregan validaciones espejo en el backend (sección 4).
- Decidir si se agrega Unidad de medida a `en.import.request.line` (sección 2).
- Consignación (cliente vacío, solo proveedor+país) — sigue sin decidir si se implementa como funcionalidad nueva.

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
| Cantidad por línea | > 0 | 0 o vacía | Dejar en blanco | Bloquear | ARREGLADO (front) — sin réplica en back |
| Forma de pago | Seleccionada | Vacía | No elegir | Bloquear | OK |
| Presupuesto | > 0 | ≤0 o vacío | Dejar vacío | Bloquear | OK |
| Botón "Omitir" visible | Solo si NO importOnly | En importOnly | Entrar con `?op=1` acreditado | No debería aparecer | ARREGLADO |

### Proveedor (paso cliente)

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Elección de vía | Una de las 3 tarjetas | Ninguna | Avanzar sin elegir | Bloquear | ARREGLADO (front) — sin réplica en back |
| "Ya tengo" → cartera | Proveedor marcado | Ninguno | No marcar y avanzar | Bloquear | revisar en vivo |
| "Buscar en catálogo" | Oferta seleccionada | Ninguna | No elegir y avanzar | Bloquear | revisar en vivo |
| Envío con "cotiza" o sin vía | Crea proceso con placeholder | — | Completar y enviar | Proceso visible, en gate | ARREGLADO — probado en shell (placeholder + gate confirmados) |

### Oferta (proveedor)

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Producto de la línea | Producto real seleccionado | — | Elegir del desplegable | Coincide con id real | ARREGLADO |
| Líneas de producto | ≥1 con cantidad y precio >0 | 0 líneas o en 0 | No agregar y avanzar | Bloquear | ARREGLADO (front) — sin réplica en back |

### Clientes (paso proveedor) — actualizado 2026-07-14, ahora 4 vías

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Elección de vía | Una de las 4 tarjetas | Ninguna | Avanzar sin elegir | Bloquear | OK (front) — sin réplica en back |
| "Ya tengo clientes" (cartera real) | ≥1 marcado, de la cartera real (`/en/wizard/my_clients`) | Ninguno | No marcar y avanzar | Bloquear | **Confirmado en navegador** — carga el cliente real con NIT y estado de acreditación |
| "Sumar clientes nuevos" | ≥1 con datos completos | Ninguno | No agregar y avanzar | Bloquear | OK — dedup por NIT confirmado (no duplica cliente existente) |
| "Es consignación" (nueva) | Se selecciona, no requiere datos | — | Elegir y avanzar | Crea bloque con `Enetec_Consignacion`, proceso queda en gate | **Confirmado en navegador** de punta a punta |
| "Difundir mi oferta" | ≥1 marcado | Ninguno | No marcar y avanzar | Bloquear | revisar en vivo — dedup por nombre confirmado en shell |
| Paso "Documentos del embarque" tras Clientes | Aparece si hay ≥1 cliente resuelto (cartera/nuevos/consignación) | "Difundir" o ningún cliente | Marcar un cliente | Stepper pasa de 3 a 4 pasos | **Confirmado en navegador** |
| Envío con cartera/nuevos/consignación | Crea `importation.process` + bloques + **1 OC en borrador por bloque**, precio real de la oferta | — | Completar y enviar | Proceso + N OC visibles en el back | **Confirmado en navegador y shell** |

### Documentos del embarque (opcional)

| Decisión | Clase válida | Clase inválida | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| Visibilidad del paso | Solo si `cpHas≠cotiza` y NO("ya tengo"+"invitar") | Fuera de esa regla | Probar las 5 combinaciones | Coincide con `showEmbarque()` | OK en código, confirmar en vivo |

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
4. En "Mis datos", elige tu tipo de empresa (Pymes, Estatal, CNA o Sucursal Extranjera) — al elegirlo aparece la lista de documentos que te corresponde subir. Escribe el nombre de tu empresa (obligatorio) y, si tienes NIT a mano, escríbelo — debe tener exactamente 11 números.
   - *Si solo quieres acreditarte y todavía no vas a pedir una importación*, hay un botón **"Omitir → Solo quiero acreditarme"** que te salta directo al resumen.
5. En "Solicitud", indica qué combustible necesitas, cuánto, y elige forma de pago y presupuesto disponible. Puedes agregar varios productos con el botón "+ Agregar producto".
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
2. En "Mis datos" completa el nombre de tu empresa, país, clasificación (Productor/Comerciante) y los 5 documentos requeridos.
3. En "Oferta", arma tu cotización: elige el producto real del desplegable (ya no hace falta adivinar el nombre, se cargan los productos verdaderos del catálogo), cantidad, envase, precio; agrega flete y seguro — el total se calcula solo.
4. En "Clientes", dinos a quién le ofreces (4 opciones):
   - **"Ya tengo clientes"** — marca uno o varios de tu cartera real (los clientes con los que ya tienes una relación registrada).
   - **"Sumar clientes nuevos"** — acredítalos con sus datos completos (nombre, NIT, dirección, contacto) o invítalos por correo. Si el NIT que escribes ya pertenece a un cliente existente, el sistema lo reconoce y no crea uno duplicado.
   - **"Es consignación"** — úsala cuando la mercancía viaja sin un cliente final definido todavía; ENETEC queda como responsable temporal del envío hasta que se asigne un comprador.
   - **"Difundir mi oferta"** — se la mandamos a los clientes que aceptan recibir ofertas de proveedores (esta opción no genera una importación, solo publicidad de tu oferta).

   Si elegiste cartera, clientes nuevos o consignación, aparece un paso más:
5. **"Documentos del embarque"** (opcional): país de origen, certificados que aplican a todo el envío (calidad/exportación/origen), y — por cada cliente que agregaste — el número de BL/AWB y sus documentos propios (oferta firmada, factura comercial, lista de empaque, permisos). Puedes dejarlo en blanco y completarlo después.
6. Revisa en "Resumen" y pulsa **Enviar**.

**Qué pasa al enviar con clientes reales:** además de tu oferta, se crea una importación real con una Orden de Compra en borrador por cada cliente (con el precio de tu oferta ya cargado) — el equipo comercial la revisa, la completa y la aprueba; tú no tienes que volver a escribir esos datos.

**Si ya estás acreditado y quieres actualizar tu oferta:**
- Pulsa **"Importar"** igual que el cliente — ahora también te lleva directo a "Oferta", sin repetir Rol/Mis datos (antes tenías que volver a empezar desde cero; ya se corrigió). El paso de Clientes y Documentos del embarque funcionan exactamente igual que la primera vez.

**Para que tu empresa aparezca en el catálogo público** (donde los clientes te buscan sin que tú los invites), marca la casilla "Mis datos pueden ser visibles para clientes" en Mis datos — pero recuerda: además de marcar esa casilla, necesitas tener al menos una oferta publicada con productos y precios; si no, aunque seas visible, no vas a aparecer con nada que ofrecer.

### Preguntas frecuentes

- **¿Qué pasa si no tengo proveedor todavía y quiero que ENETEC me cotice?** Tu solicitud se registra igual, con un proveedor "por designar" mientras se consigue uno real — no se pierde tu información, y en cuanto el comercial encuentre proveedor, lo asigna sin que tengas que volver a enviar nada.
- **¿Tengo que llenar todo en Mis datos?** El nombre de tu empresa sí es obligatorio. Los documentos no son obligatorios para avanzar — se revisan igual cuando el abogado evalúa tu acreditación.
- **¿Puedo cambiar de opinión después de omitir la solicitud?** Sí, desde el Resumen hay un enlace "¿Quieres añadir solicitud?" que te regresa al paso Solicitud.
