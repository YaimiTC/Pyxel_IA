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

> Solo aparecen los procesos que están en etapa **TRÁMITES EN DESTINO** y que tienen
> los documentos de entrada aprobados. Si un proceso no aparece, significa que el
> área comercial aún no ha terminado de revisar los documentos.

---

## Pantalla principal — Lista de trámites

Al entrar verá una lista con todos los procesos listos para trabajar:

| Columna | Descripción |
|---------|-------------|
| Referencia | Código del proceso (ej. IMP00003) |
| Proveedor | Empresa que envía la mercancía |
| Cliente | Empresa receptora |
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

En la parte superior verá la información general del proceso:

| Campo | Descripción |
|-------|-------------|
| Referencia | Código único del proceso |
| Proveedor | Empresa exportadora |
| Cliente | Empresa importadora |
| Tipo de importación | Modalidad (Ocean Freight, Air, etc.) |
| Etapa del proceso | Debe decir TRÁMITES EN DESTINO |
| Lista para despacho aduanero | Indicador verde cuando los docs de entrada están OK |
| **Apoderado asignado** | Aquí se asigna usted mismo |
| DM completadas | Se activa automáticamente cuando confirma todas las DM |

### Asignarse el proceso

1. En el campo **Apoderado asignado** hacer clic
2. Buscar su nombre de usuario y seleccionarlo
3. Guardar con el botón **Guardar** o simplemente navegando a otra pestaña

Una vez asignado, su foto de perfil aparecerá en la lista principal para que
otros apoderados sepan que ese proceso ya está siendo trabajado.

---

## Pestaña 1 — Documentos de entrada

Esta pestaña es **solo de consulta**. El apoderado no puede modificar nada aquí.
Los documentos los sube el proveedor y los aprueba el área comercial.

### Sección BL / AWB

Muestra el conocimiento de embarque (Bill of Lading) o guía aérea (Air Waybill):

| Columna | Descripción |
|---------|-------------|
| Documento | Nombre del documento |
| Archivo | Nombre del PDF subido |
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

Muestra los documentos de cada orden de compra vinculada al proceso.
Las órdenes aparecen como **encabezados en negrita** (P00010, P00011, etc.)
con sus documentos debajo:

- Oferta firmada
- Factura comercial
- Lista de empaque
- Declaración de Mercancía (DM)
- Permisos por entidades regulatorias

> Para que el proceso esté disponible para el apoderado, la **Factura comercial**
> y la **Lista de empaque** de al menos una OC deben estar aprobadas.

---

## Pestaña 2 — Declaración de Mercancía (DM)

Aquí se realiza el trabajo principal del apoderado.

> Si ve un **aviso amarillo** que dice "Los documentos de entrada aún no están
> aprobados", significa que el comercial no ha terminado su revisión. En ese caso
> no puede gestionar la DM todavía.

### Tabla de DM por Orden de Compra

Hay una fila por cada orden de compra del proceso. Cada fila muestra:

| Columna | Descripción |
|---------|-------------|
| OC | Código de la orden de compra |
| PDF DM | Archivo de la DM subido |
| IA | Resultado del análisis automático del PDF |
| Extracción | Estado de extracción de datos (Sin DM / Extraído por IA / Datos manuales) |
| Nº DM | Número de la declaración |
| Contenedor | Número de contenedor |
| CIF (USD) | Valor CIF en dólares |
| Aranceles (USD) | Total de aranceles en dólares |
| Imp. Circulación (USD) | Impuesto de circulación |
| Confirmado | Indica si el apoderado ya confirmó los datos |

### Botones de acción por fila

| Botón | Cuándo aparece | Qué hace |
|-------|---------------|----------|
| **Subir DM** | Cuando no hay PDF subido | Abre la ficha para subir el PDF |
| **Ver DM** | Cuando hay PDF subido | Abre el PDF en una nueva pestaña |
| **Confirmar** | Cuando hay PDF y no está confirmado | Marca la DM como confirmada |

---

## Proceso paso a paso: subir y confirmar una DM

### Paso 1 — Subir el PDF

1. En la fila de la OC correspondiente (ej. P00011), hacer clic en **Subir DM**
2. Se abre la ficha de revisión del documento
3. En la sección "Subir / reemplazar archivo" seleccionar el PDF de la DM
4. Esperar — la IA comenzará a analizar el documento automáticamente
5. El estado cambiará a **Validando** mientras la IA procesa
6. Cuando termine, el estado mostrará **Pasado** o **Duda**

### Paso 2 — Revisar los datos extraídos por la IA

Volver al formulario del proceso (botón Atrás o migas de pan).
En la pestaña **Declaración de Mercancía (DM)**, la fila de esa OC ahora mostrará
los campos completados automáticamente por la IA:

- Nº DM
- Contenedor
- CIF (USD)
- Aranceles (USD)
- Imp. Circulación (USD)

**Revisar cada campo.** Si algún valor es incorrecto o no se extrajo bien:
1. Hacer clic en la celda del campo a corregir
2. Escribir el valor correcto
3. Guardar

> La columna "Extracción" mostrará **Extraído por IA** si la IA obtuvo los datos,
> o **Sin DM** si el PDF no pudo ser procesado (en ese caso ingresar todo manual).

### Paso 3 — Agregar notas arancelarias (opcional)

En la sección **Notas arancelarias** al final de la pestaña, puede escribir
observaciones sobre los aranceles de cada OC en texto libre.

### Paso 4 — Confirmar la DM

Cuando los datos son correctos:
1. Hacer clic en el botón **Confirmar** (verde) de esa fila
2. La fila cambiará a color verde y el campo "Confirmado" se activará
3. El botón Confirmar desaparece — la DM está cerrada

Repetir el proceso para cada OC del proceso.

### Paso 5 — Proceso completado

Cuando **todas las OC** tienen su DM confirmada:
- El campo **DM completadas** se activa automáticamente
- El proceso **desaparece de la lista** de Trámites de aduana
- El trabajo del apoderado en este proceso ha terminado

---

## Casos especiales

### El proceso no aparece en la lista

**Causa posible 1:** Los documentos de entrada aún no están aprobados.
- Contactar al área comercial para que apruebe BL/AWB, Factura y Lista de empaque.

**Causa posible 2:** El proceso no está en etapa "TRÁMITES EN DESTINO".
- El proceso debe avanzar a esa etapa primero (lo hace el área de operaciones).

**Causa posible 3:** Todas las DM ya están confirmadas.
- El proceso está completo y fue retirado de la lista automáticamente.
- Para verlo: en la lista usar el filtro y quitar la restricción "DM lista = No".

### La IA no extrajo los datos del PDF

Si la columna "Extracción" muestra **Sin DM** después de subir el PDF:
1. Verificar que el PDF es legible y no está escaneado de forma deficiente
2. Ingresar los datos manualmente en los campos de la tabla
3. Confirmar normalmente

### Necesito reemplazar un PDF de DM ya subido

1. Hacer clic en **Ver DM** para verificar el archivo actual
2. Abrir la ficha del documento (botón "Revisar" desde el expediente principal)
3. En la sección "Subir / reemplazar archivo" subir el nuevo PDF
4. La IA volverá a procesar el nuevo archivo
5. Revisar y volver a confirmar los datos

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
La confirmación no es definitiva a nivel de sistema — un administrador puede
desmarcar `dm_confirmed` directamente. Contactar al administrador del sistema.

**¿El proceso vuelve a aparecer si se desconfirma una DM?**
Sí. Si `en_customs_dm_done` vuelve a ser False, el proceso reaparece en la lista.

**¿Puedo ver los procesos ya completados?**
Sí. En la lista de Trámites de aduana, usar los filtros para buscar procesos
con "DM lista = Sí" o buscar por referencia directamente.

**¿El apoderado puede aprobar o rechazar documentos de los proveedores?**
No. La pestaña "Documentos de entrada" es solo lectura para el apoderado.
La aprobación de documentos la hace exclusivamente el área comercial.

---

## Resumen visual del flujo

```
COMERCIAL aprueba docs          APODERADO trabaja DM
─────────────────────           ──────────────────────────────────────
BL/AWB      ✓ Aprobado    →    1. Ver proceso en "Trámites de aduana"
Factura     ✓ Aprobado    →    2. Asignarse el proceso
Lista emp.  ✓ Aprobado    →    3. Consultar docs de entrada (readonly)
                               4. Subir PDF de DM por cada OC
en_ready_for_customs = True    5. IA extrae campos automáticamente
                               6. Revisar y corregir si es necesario
                               7. Confirmar DM por cada OC
                               8. Proceso desaparece de la lista ✓
```

---

*Manual generado para ODIN 2.0 · ENETEC S.A. · Versión junio 2026*
