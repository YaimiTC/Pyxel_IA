# Manual de usuario — Apoderado de aduana
## Sistema ODIN 2.0 · ENETEC S.A.

---

## ¿Qué hace el apoderado de aduana en ODIN 2.0?

El apoderado de aduana es el responsable de gestionar la **Declaración de Mercancía (DM)**
una vez que el expediente de documentos de entrada ha sido aprobado por el área comercial.

Su trabajo en el sistema consiste en:

1. Ver qué procesos de importación están listos para despacho aduanero
2. Asignarse el proceso que va a trabajar
3. Consultar los documentos de entrada (BL/AWB, facturas, listas de empaque)
4. Subir el PDF de la DM por cada orden de compra
5. Revisar y confirmar los datos que extrae la IA del PDF
6. Marcar la DM como confirmada cuando los datos son correctos

---

## Acceso al módulo

1. Iniciar sesión en ODIN 2.0: `http://[servidor]:8469`
2. En el menú superior hacer clic en **Importación**
3. Seleccionar **Trámites de aduana**

> Solo aparecen los procesos que ya están **en tránsito hacia el puerto de destino
> o en una etapa posterior** (es decir, desde EN TRÁNSITO A PUERTO DE DESTINO en
> adelante — ya no hace falta esperar a que llegue exactamente a TRÁMITES EN
> DESTINO) y que tienen al menos una Orden de Compra lista (BL/AWB, factura y
> lista de empaque aprobados). Si un proceso no aparece, significa que aún no
> alcanzó esa etapa o que el área comercial no ha aprobado los documentos de
> ninguna OC todavía.
>
> **Importante — envíos con varios clientes:** un mismo proceso puede tener más
> de un cliente (un bloque/Orden de Compra por cliente dentro del mismo envío).
> El proceso aparece en la lista en cuanto **una sola** de esas OC cumple los
> requisitos, aunque las demás sigan con documentos pendientes. El apoderado
> puede empezar a tramitar la DM de esa OC mientras el área comercial sigue
> revisando a los otros clientes.

---

## Pantalla principal — Lista de trámites

Al entrar verá una lista con todos los procesos listos para trabajar:

| Columna | Descripción |
|---------|-------------|
| Referencia | Código del proceso (ej. IMP00003) |
| Proveedor | Empresa que envía la mercancía |
| Cliente | Empresa(s) receptora(s) — se muestra como una o varias etiquetas si el envío tiene más de un cliente |
| Apoderado asignado | Quién está trabajando ese proceso (foto de perfil) |
| DM lista | Indica si todas las DM del proceso están confirmadas |

**Colores de las filas:**
- **Fila normal** — sin apoderado asignado, disponible para tomar
- **Fila en gris** — ya tiene apoderado asignado, está siendo trabajado
- **Fila en verde** — todas las DM confirmadas (no debería aparecer en la lista normal)

> Cuando todas las DM de un proceso están confirmadas, el proceso desaparece
> automáticamente de esta lista. Si necesita volver a verlo, use el filtro
> "Mostrar DM completadas".

---

## Abrir un proceso

Hacer clic en cualquier fila de la lista para abrir el formulario del proceso.

---

## Formulario del proceso — cabecera

Arriba del todo, una **barra de estado** (statusbar) muestra la etapa actual del
proceso dentro de todo el flujo (SOLICITUD → TRÁMITES EN ORIGEN → EN TRÁNSITO A
PUERTO DE DESTINO → TRÁMITES EN DESTINO → …). Es de solo lectura: el apoderado no
la cambia, solo la consulta como referencia — para que el trámite sea visible
alcanza con que esté en EN TRÁNSITO A PUERTO DE DESTINO o cualquier etapa
posterior.

Debajo, la información general del proceso:

| Campo | Descripción |
|-------|-------------|
| Referencia | Código único del proceso |
| Proveedor | Empresa exportadora |
| Cliente | Empresa(s) importadora(s) — una etiqueta por cada cliente del envío |
| Lista para despacho aduanero | Indicador (toggle) activo cuando al menos una OC tiene sus documentos de entrada aprobados |
| **Apoderado asignado** | Aquí se asigna usted mismo |
| DM completadas | Se activa automáticamente cuando confirma todas las DM |

### Asignarse el proceso

1. En el campo **Apoderado asignado** hacer clic
2. Buscar su nombre de usuario y seleccionarlo (solo aparecen apoderados ya dados de alta en el sistema; no se pueden crear usuarios nuevos desde aquí)
3. Guardar con el botón **Guardar** o simplemente navegando a otra pestaña

Una vez asignado, su foto de perfil aparecerá en la lista principal para que
otros apoderados sepan que ese proceso ya está siendo trabajado.

---

## Pestaña 1 — Documentos de entrada

Esta pestaña es **solo de consulta**. El apoderado no puede modificar nada aquí.
Los documentos los sube el proveedor y los aprueba el área comercial. Está
dividida en dos listas.

### Sección Documentos de la importación

Documentos generales que aplican a **todo el proceso**, no a un cliente/OC en
particular: certificado de calidad, certificado de exportación y certificado de
origen.

| Columna | Descripción |
|---------|-------------|
| Documento | Nombre del documento |
| Dictamen IA | Resultado del análisis automático |
| Estado | Estado de aprobación comercial |
| Ver | Abre el PDF en una nueva pestaña |

**Estados posibles:**

| Estado | Significado |
|--------|-------------|
| Pendiente | Aún no se ha subido el documento |
| Validando | La IA lo está analizando |
| Opcional | No es obligatorio para este proceso |
| Aprobado | El comercial lo aprobó ✓ |
| Rechazado | El comercial lo rechazó, el proveedor debe reemplazarlo |

### Sección Documentos por Orden de Compra

Muestra los documentos de cada orden de compra (OC) vinculada al proceso — una
OC por cliente cuando el envío tiene varios. Ya no se agrupan como encabezados en
negrita: cada fila indica su propia **OC** y su **Cliente**, y las filas de una
misma OC se distinguen con un sombreado alterno. Por cada OC aparecen:

- **BL / AWB** (conocimiento de embarque o guía aérea — ahora es un documento por OC/cliente, no uno solo para todo el proceso)
- Oferta firmada
- Factura comercial
- Lista de empaque
- Permisos por entidades regulatorias
- Declaración de Mercancía (DM)

Usa los mismos estados de la tabla anterior (Pendiente / Validando / Opcional /
Aprobado / Rechazado).

> Para que el proceso esté disponible para el apoderado, el **BL/AWB**, la
> **Factura comercial** y la **Lista de empaque** de **al menos una** OC deben
> estar aprobados. No hace falta que todos los clientes del proceso tengan sus
> documentos completos — con que una sola OC cumpla los tres, el proceso ya es
> tramitable (y esa OC en particular queda lista para su DM).

---

## Pestaña 2 — Declaración de Mercancía (DM)

Aquí se realiza el trabajo principal del apoderado.

> Si ve un **aviso amarillo** que dice "Los documentos de entrada aún no están
> aprobados", significa que **ninguna** OC del proceso tiene todavía su BL/AWB,
> factura y lista de empaque aprobados (normalmente no debería ver este aviso,
> ya que el proceso solo aparece en la lista cuando al menos una OC está lista;
> puede pasar si el estado cambió justo mientras tenía el formulario abierto).
> En ese caso no puede gestionar ninguna DM todavía — recargue la página o vuelva
> más tarde.

### Tabla de DM por Orden de Compra

Hay una fila por cada orden de compra del proceso. Cada fila muestra:

| Columna | Descripción |
|---------|-------------|
| OC | Código de la orden de compra |
| PDF DM | Archivo de la DM subido |
| IA | Resultado del análisis automático del PDF |
| Extracción | Estado de extracción de datos (Sin DM / Extraído por IA / Datos manuales) |
| Nº DM | Número de la declaración |
| CIF (USD) | Valor estadístico en dólares (escaque 54 de la DM) |
| Aranceles (MN) | Total de aranceles en pesos cubanos |
| Servicio Aduana (MN) | Servicio de Aduana en pesos cubanos |
| Confirmado | Indica si el apoderado ya confirmó los datos |

> Los campos **Aranceles** y **Servicio de Aduana** están en **Moneda Nacional (MN)**
> porque así figuran en la DM cubana, no en dólares.

### Campos extraídos automáticamente por OCR

Al subir el PDF, el sistema extrae automáticamente, anclando cada dato a su
casilla real del formulario (no adivina por palabras sueltas, porque "CIF",
"Arancel" o "DM" aparecen repetidos en la DM con otros significados):

| Campo | Origen en la DM |
|-------|-----------------|
| Nº DM | Casilla 2 — "No. de declaración" (no confundir con "No. int. DM", un número de trámite interno distinto que aparece en la casilla 66) |
| CIF (USD) | Casilla 54 — "Valor estadístico" |
| Aranceles (MN) | Casilla 32 "Importe a pagar", fila "Arancel" |
| Servicio Aduana (MN) | Casilla 32 "Importe a pagar", fila "Servicio de aduana" |

> **Aranceles en 0,00 no siempre es un error.** Cuando la importación tiene una
> exoneración/estímulo fiscal, la casilla 32 "Importe a pagar" del Arancel
> queda en 0,00 legítimamente — el monto que sí aparece en la DM (casilla 33
> "Sacrificio fiscal") es solo informativo, no lo que se paga, y el sistema
> no lo usa. Si la DM no trae exoneración, revise que el 0,00 no sea un fallo
> de lectura.

> Si el PDF es una fotografía escaneada, el sistema usa OCR (reconocimiento óptico
> de caracteres). La calidad del escaneo afecta la precisión — revise siempre los
> valores antes de confirmar.

### Botones de acción por fila

| Botón | Cuándo aparece | Qué hace |
|-------|---------------|----------|
| **Subir DM** | Cuando no hay PDF subido | Abre la ficha para subir el PDF |
| **Ver DM** | Cuando hay PDF subido | Abre el PDF en una nueva pestaña |
| **Reemplazar** | Cuando hay PDF subido | Borra el PDF y todos los datos extraídos para empezar de nuevo |
| **Confirmar** | Cuando hay PDF y no está confirmado | Valida los datos y marca la DM como confirmada |

---

## Proceso paso a paso: subir y confirmar una DM

### Paso 1 — Subir el PDF

1. En la fila de la OC correspondiente (ej. P00011), hacer clic en **Subir DM**
2. Se abre la ficha de revisión del documento
3. En la sección "Subir / reemplazar archivo" seleccionar el PDF de la DM
4. Esperar — la IA comenzará a analizar el documento automáticamente
5. El estado cambiará a **Validando** mientras la IA procesa
6. Cuando termine, el estado mostrará **Pasado** o **Duda**

### Paso 2 — Revisar los datos extraídos

Volver al formulario del proceso (botón Atrás o migas de pan).
En la pestaña **Declaración de Mercancía (DM)**, la fila de esa OC ahora mostrará
los campos completados automáticamente:

- Nº DM
- CIF (USD)
- Aranceles (MN)
- Servicio Aduana (MN)

**Revisar cada campo.** Si algún valor es incorrecto o no se extrajo bien:
1. Hacer clic en la celda del campo a corregir
2. Escribir el valor correcto
3. Guardar

> La columna "Extracción" mostrará **Extraído por IA** si el sistema obtuvo los datos,
> o **Sin DM** si el PDF no pudo ser procesado (en ese caso ingresar todo manualmente).

> **Servicio de Aduana:** en PDFs de baja calidad (fotografías) el OCR puede no
> capturar este valor — si aparece en 0,00, ingréselo manualmente consultando el PDF.

### Paso 3 — Agregar notas arancelarias (opcional)

En la sección **Notas arancelarias** al final de la pestaña, puede escribir
observaciones sobre los aranceles de cada OC en texto libre.

### Paso 4 — Confirmar la DM

Cuando los datos son correctos, hacer clic en el botón **Confirmar** de esa fila.

El sistema realiza automáticamente una **validación cruzada** entre el contenido del
PDF y los datos registrados en la importación. Si detecta discrepancias, aparece un
aviso amarillo en la esquina superior derecha con el detalle:

| Alerta posible | Qué significa |
|---------------|---------------|
| "Cliente X no encontrado en la DM" | El nombre del cliente no aparece en el texto del PDF |
| "Proveedor X no encontrado en la DM" | El nombre del proveedor no aparece en el PDF |
| "Apoderado X no encontrado en la DM" | Su nombre no aparece en el PDF de la DM |
| "BL/referencia X no encontrado en la DM" | El número de BL no aparece en el PDF |
| "No hay número de BL/referencia registrado" | El proceso no tiene BL registrado |
| "Ningún contenedor (X) encontrado en la DM" | Los números de contenedor no aparecen en el PDF |
| "No hay contenedores registrados" | El proceso no tiene contenedores registrados |
| "No existe línea de costo Arancel" | Falta añadir el Arancel en los gastos de la importación |
| "No existe línea de costo Servicio de Aduana" | Falta añadir el Servicio de Aduana en los gastos |

> Las alertas son **informativas** — la DM se confirma igual aunque haya avisos.
> El objetivo es que el apoderado detecte cualquier discrepancia antes de cerrar.
> Las alertas también quedan registradas en el **historial del proceso** para
> trazabilidad.

**Si los datos son correctos y las alertas son esperadas** (por ejemplo, el nombre
del cliente está abreviado en la DM), puede ignorar el aviso y continuar.

**Si detecta un error real** (número de Arancel incorrecto, contenedor diferente):
1. No hacer caso al aviso por ahora
2. Corregir el dato erróneo en el proceso o en los campos de la tabla
3. Usar el botón **Reemplazar** si el PDF es incorrecto (ver sección de casos especiales)
4. Volver a hacer clic en **Confirmar**

Una vez confirmada, la fila muestra el campo "Confirmado" activo y el botón
Confirmar desaparece. La DM está cerrada.

Repetir el proceso para cada OC del proceso.

### Paso 5 — Proceso completado

Cuando **todas las OC** tienen su DM confirmada:
- El campo **DM completadas** se activa automáticamente
- El proceso **desaparece de la lista** de Trámites de aduana
- El trabajo del apoderado en este proceso ha terminado

---

## Casos especiales

### El proceso no aparece en la lista

**Causa posible 1:** Ninguna OC del proceso tiene sus documentos de entrada aprobados.
- Contactar al área comercial para que apruebe BL/AWB, Factura y Lista de empaque
  de al menos una OC (si el envío tiene varios clientes, basta con que la de uno
  de ellos quede aprobada).

**Causa posible 2:** El proceso todavía no llegó a la etapa "EN TRÁNSITO A PUERTO DE DESTINO".
- El proceso debe avanzar al menos hasta esa etapa (lo hace el área de operaciones).
  Una vez alcanzada, el proceso queda visible para el apoderado en esa etapa y en
  todas las posteriores (TRÁMITES EN DESTINO, LISTO PARA EXTRAER, etc.) — ya no
  hace falta que esté clavado exactamente en TRÁMITES EN DESTINO.

**Causa posible 3:** Todas las DM ya están confirmadas.
- El proceso está completo y fue retirado de la lista automáticamente.
- Para verlo: en la lista usar el filtro y quitar la restricción "DM lista = No".

### El sistema no extrajo los datos del PDF

Si la columna "Extracción" muestra **Sin DM** después de subir el PDF:
1. Verificar que el PDF es legible y no está escaneado de forma deficiente
2. Ingresar los valores manualmente en las celdas de la tabla (Nº DM, CIF, Aranceles, Servicio Aduana)
3. Confirmar normalmente

### El Servicio de Aduana quedó en 0,00

Esto ocurre con PDFs fotografiados donde la columna de importes es ilegible para el OCR.
El Nº DM, CIF y Aranceles suelen extraerse bien. Solo el Servicio de Aduana requiere
entrada manual en estos casos:
1. Abrir el PDF con **Ver DM** y localizar la fila "Servicio" en la tabla de liquidación
2. Hacer clic en la celda **Servicio Aduana (MN)** de esa fila en la tabla
3. Ingresar el valor manualmente
4. Guardar y confirmar

### Necesito reemplazar un PDF de DM ya subido

1. En la fila de la OC, hacer clic en **Reemplazar**
2. El sistema borrará el PDF actual y reiniciará todos los campos (Nº DM, CIF, Aranceles,
   Servicio de Aduana, Confirmado y los estados de validación)
3. La fila vuelve al estado inicial — como si no se hubiera subido ningún PDF
4. Hacer clic en **Subir DM** y seleccionar el nuevo PDF
5. El sistema volverá a extraer los datos automáticamente
6. Revisar y confirmar de nuevo

> El botón **Reemplazar** está siempre disponible mientras haya un PDF subido,
> incluso si la DM ya estaba confirmada. Úselo solo si el PDF es incorrecto —
> reemplazar una DM confirmada requiere volver a confirmarla.

### Hay dos apoderados para el mismo proceso

Si dos apoderados necesitan trabajar el mismo proceso (múltiples OC):
- Solo uno puede estar asignado en el campo "Apoderado asignado"
- El apoderado asignado es el responsable principal
- Ambos pueden subir DM de distintas OC desde el mismo formulario
- La confirmación es por OC, por lo que pueden trabajar en paralelo sin conflicto

---

## Preguntas frecuentes

**¿Puedo cambiar el apoderado asignado?**
Sí. Cualquier usuario con acceso puede modificar el campo "Apoderado asignado".

**¿Qué pasa si confirmo una DM con datos incorrectos?**
Use el botón **Reemplazar** para volver al estado inicial y subir el PDF correcto,
o edite directamente los campos numéricos si solo hay un valor equivocado.
Si la DM ya está confirmada y necesita reabrirla, contacte al administrador del sistema.

**¿El proceso vuelve a aparecer si se desconfirma una DM?**
Sí. Si `en_customs_dm_done` vuelve a ser False, el proceso reaparece en la lista.

**¿Puedo ver los procesos ya completados?**
Sí. En la lista de Trámites de aduana, usar los filtros para buscar procesos
con "DM lista = Sí" o buscar por referencia directamente.

**¿El apoderado puede aprobar o rechazar documentos de los proveedores?**
No. La pestaña "Documentos de entrada" es solo lectura para el apoderado.
La aprobación de documentos la hace exclusivamente el área comercial.

**El proceso tiene varios clientes y solo uno tiene los documentos completos, ¿qué pasa?**
El proceso aparece igual en la lista de Trámites de aduana en cuanto una OC
(un cliente) está lista. El apoderado puede subir y confirmar la DM de esa OC
mientras las demás siguen su revisión comercial en paralelo — no hay que esperar
a que todos los clientes del envío estén listos a la vez.

---

## Resumen visual del flujo

```
Etapa del proceso ≥ EN TRÁNSITO A PUERTO DE DESTINO
(en_customs_stage_reached = True)
        │
        ▼
Por cada OC (cliente) del proceso:
  BL/AWB      ✓ Aprobado
  Factura     ✓ Aprobado     ──►  ¿AL MENOS UNA OC con las 3? ──► en_ready_for_customs = True
  Lista emp.  ✓ Aprobado                                                    │
                                                                             ▼
en_customs_stage_reached = True  Y  en_ready_for_customs = True
        │
        ▼
      PROCESO VISIBLE EN "TRÁMITES DE ADUANA"          APODERADO trabaja DM
      ────────────────────────────────────────         ──────────────────────────────────────
                                                    1. Ver proceso en "Trámites de aduana"
                                                    2. Asignarse el proceso
                                                    3. Consultar docs de entrada (readonly)
                                                    4. Subir PDF de DM por cada OC que ya esté lista
                                                    5. OCR extrae: Nº DM, CIF, Aranceles MN,
                                                       Servicio Aduana MN automáticamente
                                                    6. Revisar campos — corregir si hace falta
                                                       (Servicio Aduana en 0 = ingresar manual)
                                                    7. Confirmar → sistema valida cliente,
                                                       proveedor, apoderado, BL, contenedores
                                                       y líneas de costo; muestra alertas
                                                    8. Revisar alertas y corregir si procede
                                                       (o ignorar si son esperadas)
                                                    9. Repetir por cada OC del proceso (las OC de
                                                       otros clientes que aún no estén listas se
                                                       habilitan solas cuando comercial las apruebe)
                                                   10. Proceso desaparece de la lista cuando TODAS
                                                       las OC tienen su DM confirmada ✓

Si el PDF es incorrecto en cualquier momento:
    → Reemplazar → sube nuevo PDF → vuelve al paso 5
```

---

*Manual generado para ODIN 2.0 · ENETEC S.A. · Versión julio 2026 — actualizado
con el requisito multi-cliente por OC y la visibilidad desde EN TRÁNSITO A
PUERTO DE DESTINO.*
