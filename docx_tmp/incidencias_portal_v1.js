const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, BorderStyle, ShadingType, WidthType, Table, TableRow, TableCell } = require('docx');
const fs = require('fs');

const AZUL = '1F3864';
const AZUL_CLARO = 'D6E4F0';
const GRIS = 'F5F5F5';
const ROJO = 'C0392B';
const VERDE = '1A5276';

function titulo(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 0, after: 200 },
    children: [new TextRun({ text, bold: true, size: 28, color: AZUL, font: 'Arial' })]
  });
}

function seccion(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 120 },
    children: [new TextRun({ text, bold: true, size: 24, color: VERDE, font: 'Arial' })]
  });
}

function incidenciaTitulo(text) {
  return new Paragraph({
    spacing: { before: 240, after: 80 },
    children: [new TextRun({ text, bold: true, size: 22, color: ROJO, font: 'Arial' })]
  });
}

function parrafo(text) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    alignment: AlignmentType.JUSTIFIED,
    children: [new TextRun({ text, size: 20, font: 'Arial' })]
  });
}

function separador() {
  return new Paragraph({
    spacing: { before: 100, after: 100 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' } },
    children: [new TextRun('')]
  });
}

function notaImpacto(text) {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    alignment: AlignmentType.JUSTIFIED,
    border: {
      top: { style: BorderStyle.SINGLE, size: 6, color: 'C0392B' },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: 'C0392B' },
      left: { style: BorderStyle.SINGLE, size: 12, color: 'C0392B' },
      right: { style: BorderStyle.SINGLE, size: 6, color: 'C0392B' },
    },
    shading: { fill: 'FDEDEC', type: ShadingType.CLEAR },
    children: [
      new TextRun({ text: '⚠ IMPACTO EN EL FLUJO: ', bold: true, size: 20, color: 'C0392B', font: 'Arial' }),
      new TextRun({ text, size: 20, font: 'Arial', color: '2C2C2C' }),
    ]
  });
}

function celdaHeader(text, color) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: 'AAAAAA' };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new TableCell({
    borders,
    width: { size: 3120, type: WidthType.DXA },
    shading: { fill: color || AZUL_CLARO, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      children: [new TextRun({ text, bold: true, size: 18, font: 'Arial', color: '000000' })]
    })]
  });
}

function celda(text, shade) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new TableCell({
    borders,
    width: { size: 3120, type: WidthType.DXA },
    shading: { fill: shade || 'FFFFFF', type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      children: [new TextRun({ text, size: 18, font: 'Arial' })]
    })]
  });
}

const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [

      // TÍTULO PRINCIPAL
      new Paragraph({
        spacing: { before: 0, after: 400 },
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: 'Análisis de Incidencias', bold: true, size: 36, color: AZUL, font: 'Arial' }),
          new TextRun({ text: '\nPortal de Importaciones — ERP ODIN', bold: false, size: 22, color: '555555', font: 'Arial', break: 1 }),
          new TextRun({ text: '\nFecha: 14 de junio de 2026', bold: false, size: 18, color: '888888', font: 'Arial', break: 1 }),
        ]
      }),

      separador(),

      // SECCIÓN 1: FLUJO ENTENDIDO
      titulo('1. Flujo entendido — Portal de importaciones'),

      parrafo('El proceso comienza cuando un cliente acreditado envía una solicitud de importación desde el sitio web. Esa solicitud queda visible en su portal bajo el widget "Solicitudes". El comercial interno atiende la solicitud desde el backend, evalúa proveedores y les envía una solicitud de presupuesto (orden de compra). En ese momento el proveedor evaluado debería ver reflejada esa solicitud en su portal bajo el widget "Solicitudes". Una vez que el comercial confirma el proveedor e inicia la importación, tanto el cliente como el proveedor deberían ver la importación activa en su portal bajo el widget "Importaciones".'),

      separador(),

      // SECCIÓN 2: INCIDENCIAS
      titulo('2. Incidencias identificadas'),

      incidenciaTitulo('Incidencia 1 — Cliente: contador de solicitudes no coincide con la lista'),
      parrafo('El widget "Solicitudes" muestra el número 1 en el portal del cliente, pero al hacer clic la página aparece vacía con el mensaje "Actualmente no hay pedidos de venta para su cuenta." El cliente no puede ver ni dar seguimiento a su solicitud desde el portal.'),

      incidenciaTitulo('Incidencia 2 — Proveedor: solicitudes no aparecen ni en el contador ni en la lista'),
      parrafo('Cuando el comercial evalúa un proveedor y le envía la solicitud de presupuesto, el proveedor no ve nada en su portal. El contador permanece en cero y la lista aparece vacía. El proveedor no puede ver desde su portal ninguna solicitud de presupuesto pendiente de responder.'),

      incidenciaTitulo('Incidencia 3 — Cliente y Proveedor: lista de importaciones vacía'),
      parrafo('El widget "Importaciones" muestra el número 1 en el portal de ambos usuarios cuando la importación está en la primera etapa, pero al hacer clic la lista aparece vacía. Ni el cliente ni el proveedor pueden ver ni dar seguimiento al proceso de importación activo desde su portal.'),

      incidenciaTitulo('Incidencia 4 — Cliente y Proveedor: contador de importaciones cae a cero al avanzar la etapa'),
      parrafo('En el momento en que el comercial mueve la importación a una etapa posterior (ej. "Trámite en Destino"), el contador del widget "Importaciones" vuelve a cero para ambos usuarios, aunque la importación sigue activa. Esto provoca que el portal deje de reflejar cualquier actividad de importación una vez que deja la primera etapa.'),

      notaImpacto('Las incidencias 3 y 4 combinadas producen un bloqueo funcional en el flujo de importación. El proveedor no puede ver la importación activa desde el portal y por tanto no puede cargar directamente la información de embarque. El cliente tampoco puede consultarla desde su portal. Como consecuencia, la única vía disponible es el flujo tradicional: el proveedor envía la información de embarque por correo electrónico y la comercial la ingresa manualmente al sistema. Esto significa que la carga de trabajo recae sobre la comercial y se deja de usar una facilidad que debiera dar el portal.'),

      incidenciaTitulo('Incidencia 5 — Cliente: ventas del backend inflan el contador de solicitudes'),
      parrafo('Si el comercial crea órdenes de venta desde el backend para la empresa del cliente (ej. S00073 draft $0, S00075 draft $3,730), el widget "Solicitudes" las cuenta junto con las solicitudes de importación reales. El cliente ve "2 Solicitudes" cuando solo envió una solicitud de importación, lo que genera confusión. Los drafts del backend no son solicitudes de importación y no deben aparecer en ese contador.'),

      incidenciaTitulo('Incidencia 6 — Cliente: orden de venta confirmada no aparece en /my/orders'),
      parrafo('La orden de venta S00074 (estado confirmada, $231,230) existe y el ORM la devuelve correctamente al usuario portal cuando se consulta directamente. Sin embargo, la página /my/orders — a la que enlaza el widget "Solicitudes" — muestra "Actualmente no hay pedidos de venta para su cuenta." El cliente no puede acceder a ninguna de sus órdenes desde el portal aunque estas existan y sean accesibles por reglas de acceso.'),

      incidenciaTitulo('Incidencia 7 — Cliente: contador de facturas muestra cero aunque existe una factura en borrador'),
      parrafo('Se generaron dos facturas para el cliente: una en estado borrador (sin número asignado) y una confirmada y pagada (INV/2026/00010). El widget "Facturas" en /my/home muestra cero para ambas. El contador en portal_controller.py busca facturas en state="draft" con partner_id igual a la empresa del cliente, condición que la factura en borrador cumple, pero el widget no refleja ningún valor.'),

      incidenciaTitulo('Incidencia 8 — Cliente: factura confirmada y pagada no aparece en /my/invoices'),
      parrafo('La factura INV/2026/00010 (estado confirmada, pagada) es accesible para el usuario portal cuando se consulta directamente vía ORM — el sistema la devuelve correctamente. Sin embargo, la página /my/invoices muestra "Actualmente no hay facturas para su cuenta." El mismo patrón se repite para ventas (Incidencia 6): el ORM devuelve el registro pero la página renderizada por el servidor aparece vacía.'),

      separador(),

      // SECCIÓN 3: CAUSA TÉCNICA
      titulo('3. Causa técnica'),

      seccion('Incidencia 1 — Cliente: Solicitudes'),
      parrafo('La solicitud de importación crea una orden de venta en estado borrador (draft). El contador del portal usa sudo() y cuenta correctamente esas órdenes en borrador. Sin embargo, la página /my/orders a la que enlaza el widget es la ruta estándar de Odoo que solo muestra órdenes confirmadas (state = sale o done), por lo que la solicitud existe pero nunca aparece en la lista.'),

      seccion('Incidencia 2 — Proveedor: Solicitudes'),
      parrafo('El contador solo busca órdenes de compra en estado borrador (draft). En el momento en que el comercial envía la solicitud al proveedor por correo, la orden pasa automáticamente al estado sent (enviada), por lo que el contador queda en cero. Por otro lado, la lista a la que enlaza el widget muestra órdenes de venta (sale.order), no órdenes de compra, por lo que aunque existieran registros en el estado correcto nunca aparecerían en esa página.'),

      seccion('Incidencia 3 — Cliente y Proveedor: Importaciones (lista vacía)'),
      parrafo('El contador del portal calcula los registros usando sudo(), que omite las reglas de acceso. El componente que renderiza la lista en la página de importaciones hace las consultas directamente con el usuario portal, sin sudo(). Si el modelo importation.process no tiene una regla de acceso (ir.rule) que permita a los usuarios portal leer sus propios registros, la consulta devuelve vacío sin mostrar ningún error visible, mientras el contador sigue marcando 1.'),

      seccion('Incidencia 4 — Cliente y Proveedor: contador cae a 0 al avanzar etapa'),
      parrafo('El contador de importaciones en portal_controller.py aplica un filtro adicional: solo cuenta registros cuyo stage_id es igual a la primera etapa (sequence asc, limit=1). En cuanto el comercial mueve la importación a una etapa posterior, el registro ya no cumple ese filtro y el contador vuelve a cero. El contador no refleja todas las importaciones activas del usuario, solo las que están en la etapa inicial.'),

      seccion('Incidencia 5 — Cliente: ventas del backend inflan el contador'),
      parrafo('El contador de "Solicitudes" en portal_controller.py usa la condición state="draft" AND partner_id=business_partner_id sin distinguir el origen del draft. Cualquier orden de venta en borrador creada desde el backend para la empresa del cliente suma al contador, aunque no sea una solicitud de importación enviada desde el portal.'),

      seccion('Incidencia 6 — Cliente: orden confirmada no aparece en /my/orders'),
      parrafo('La ruta /my/orders usa el dominio estándar de Odoo: message_partner_ids child_of [commercial_partner_id] AND state="sale". La orden S00074 cumple ambas condiciones — el ORM la devuelve correctamente al usuario portal cuando se consulta vía RPC con ese mismo dominio. Sin embargo, la página renderizada por el servidor muestra la lista vacía. La causa exacta está pendiente de confirmar; puede estar relacionada con el contexto de request.website que activa filtros adicionales durante el renderizado del controlador HTTP.'),

      seccion('Incidencia 7 — Cliente: contador de facturas en cero'),
      parrafo('El contador new_invoices_count en portal_controller.py busca account.move con state="draft", move_type="out_invoice" y partner_id=business_partner_id usando sudo(). La factura en borrador para Probando (id=80) cumple esas condiciones pero el widget muestra 0. Posible causa: la factura draft no tiene aún partner_id asignado en el momento de creación, o el campo partner_id apunta a un contacto (id=77) en lugar de a la empresa (id=80), haciendo que el filtro no la encuentre.'),

      seccion('Incidencia 8 — Cliente: factura confirmada no aparece en /my/invoices'),
      parrafo('La ir.rule "Portal Personal Account Invoices" requiere state NOT IN ("cancel","draft"), move_type de factura y message_partner_ids child_of [commercial_partner_id]. INV/2026/00010 cumple todo y el ORM la devuelve al portal user. Sin embargo /my/invoices renderiza vacío, repitiendo el mismo patrón sin resolver de la Incidencia 6 con /my/orders.'),

      separador(),

      // SECCIÓN 4: TABLA COMPARATIVA DE ENLACES
      titulo('4. Comparativa de enlaces por estado'),

      new Paragraph({
        spacing: { before: 60, after: 120 },
        children: [new TextRun({ text: 'La tabla muestra cómo responde cada enlace clave según el estado del usuario: sin solicitud (GANADO), con solicitud enviada, con importación iniciada y en etapas posteriores. Las ventas creadas desde el backend (Incidencias 5 y 6) se documentan por separado al final de esta sección.', size: 20, font: 'Arial', italics: true })]
      }),

      new Paragraph({ spacing: { before: 0, after: 120 }, children: [] }),

      // Tabla CLIENTE
      new Paragraph({
        spacing: { before: 120, after: 80 },
        children: [new TextRun({ text: 'CLIENTE (yaimitccc@gmail.com)', bold: true, size: 22, color: AZUL, font: 'Arial' })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2500, 1490, 1790, 1790, 1790],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('Enlace', AZUL_CLARO),
              celdaHeader('Sin solicitud (GANADO)', AZUL_CLARO),
              celdaHeader('Con solicitud enviada', AZUL_CLARO),
              celdaHeader('Con importación iniciada', AZUL_CLARO),
              celdaHeader('Etapas posteriores (*)', AZUL_CLARO),
            ]
          }),
          new TableRow({ children: [
            celda('/my/home — widget Solicitudes', GRIS), celda('0 Solicitudes', GRIS), celda('1 Solicitudes ⚠', GRIS), celda('1 Solicitudes ⚠', GRIS), celda('1 Solicitudes ⚠', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/my/home — widget Importaciones'), celda('0 Importaciones'), celda('0 Importaciones'), celda('1 Importaciones ⚠'), celda('0 Importaciones ⚠')
          ]}),
          new TableRow({ children: [
            celda('/my/orders (lista Solicitudes)', GRIS), celda('200 — lista vacía', GRIS), celda('200 — lista vacía ⚠', GRIS), celda('200 — lista vacía ⚠', GRIS), celda('200 — lista vacía ⚠', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/model/imports (lista Importaciones)'), celda('200 — OWL vacío'), celda('200 — OWL vacío'), celda('200 — OWL vacío ⚠'), celda('200 — OWL vacío ⚠')
          ]}),
          new TableRow({ children: [
            celda('/business-register?type=accreditation', GRIS), celda('303 → thanks', GRIS), celda('200 → /my/home', GRIS), celda('200 → /my/home', GRIS), celda('200 → /my/home', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/business-register?type=import'), celda('200 formulario'), celda('200 formulario'), celda('200 formulario'), celda('200 formulario')
          ]}),
          new TableRow({ children: [
            celda('/nomenclador?from=import_registration', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/descargar/load_products'), celda('200'), celda('200'), celda('200'), celda('200')
          ]}),
          new TableRow({ children: [
            celda('/descargar/solicitud', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/my/notifications'), celda('404 ⚠'), celda('404 ⚠'), celda('404 ⚠'), celda('404 ⚠')
          ]}),
          new TableRow({ children: [
            celda('Resto de enlaces (28)', GRIS), celda('200', GRIS), celda('200 sin cambio', GRIS), celda('200 sin cambio', GRIS), celda('200 sin cambio', GRIS)
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 120, after: 80 }, children: [] }),

      // Tabla PROVEEDOR
      new Paragraph({
        spacing: { before: 200, after: 80 },
        children: [new TextRun({ text: 'PROVEEDOR (yaimitpp@gmail.com)', bold: true, size: 22, color: '6A0572', font: 'Arial' })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2500, 1490, 1790, 1790, 1790],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('Enlace', 'E8DAEF'),
              celdaHeader('Sin solicitud (GANADO)', 'E8DAEF'),
              celdaHeader('Solicitud enviada por comercial', 'E8DAEF'),
              celdaHeader('Con importación iniciada', 'E8DAEF'),
              celdaHeader('Etapas posteriores (*)', 'E8DAEF'),
            ]
          }),
          new TableRow({ children: [
            celda('/my/home — widget Solicitudes', GRIS), celda('0 Solicitudes', GRIS), celda('0 Solicitudes ⚠', GRIS), celda('0 Solicitudes ⚠', GRIS), celda('0 Solicitudes ⚠', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/my/home — widget Importaciones'), celda('0 Importaciones'), celda('0 Importaciones'), celda('1 Importaciones ⚠'), celda('0 Importaciones ⚠')
          ]}),
          new TableRow({ children: [
            celda('/my/orders (lista Solicitudes)', GRIS), celda('200 — lista vacía', GRIS), celda('200 — lista vacía ⚠', GRIS), celda('200 — lista vacía ⚠', GRIS), celda('200 — lista vacía ⚠', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/model/imports (lista Importaciones)'), celda('200 — OWL vacío'), celda('200 — OWL vacío'), celda('200 — OWL vacío ⚠'), celda('200 — OWL vacío ⚠')
          ]}),
          new TableRow({ children: [
            celda('/business-register?type=accreditation', GRIS), celda('303 → thanks', GRIS), celda('200 → /my/home', GRIS), celda('200 → /my/home', GRIS), celda('200 → /my/home', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/business-register?type=import'), celda('200 bloqueado'), celda('200 bloqueado'), celda('200 bloqueado'), celda('200 bloqueado')
          ]}),
          new TableRow({ children: [
            celda('/my/notifications', GRIS), celda('404 ⚠', GRIS), celda('404 ⚠', GRIS), celda('404 ⚠', GRIS), celda('404 ⚠', GRIS)
          ]}),
          new TableRow({ children: [
            celda('Resto de enlaces (28)'), celda('200'), celda('200 sin cambio'), celda('200 sin cambio'), celda('200 sin cambio')
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 120, after: 40 }, children: [
        new TextRun({ text: '⚠ = incidencia detectada    |    bloqueado = página accesible pero con mensaje de acceso denegado', size: 16, font: 'Arial', italics: true, color: '777777' })
      ]}),
      new Paragraph({ spacing: { before: 0, after: 80 }, children: [
        new TextRun({ text: '(*) "Etapas posteriores" cubre Trámite en Destino, Listo para Extraer, En Almacén Cliente y Devolución del Contenedor (todas verificadas). El comportamiento es idéntico: el contador de Importaciones permanece en 0 porque el portal solo cuenta registros en la primera etapa.', size: 16, font: 'Arial', italics: true, color: '777777' })
      ]}),

      // Sub-sección ventas del backend
      new Paragraph({
        spacing: { before: 200, after: 80 },
        children: [new TextRun({ text: 'Efecto de ventas creadas desde el backend (Incidencias 5 y 6)', bold: true, size: 22, color: AZUL, font: 'Arial' })]
      }),
      new Paragraph({
        spacing: { before: 0, after: 80 },
        children: [new TextRun({ text: 'El comercial creó órdenes de venta en el backend para la empresa del cliente (Probando): S00073 (draft, $0), S00074 (confirmada, $231,230) y S00075 (draft, $3,730).', size: 20, font: 'Arial' })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3000, 2000, 2180, 2180],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('Elemento', AZUL_CLARO),
              celdaHeader('Sin ventas backend', AZUL_CLARO),
              celdaHeader('Con ventas backend', AZUL_CLARO),
              celdaHeader('Esperado correcto', AZUL_CLARO),
            ]
          }),
          new TableRow({ children: [
            celda('Widget Solicitudes (CLIENTE)', GRIS),
            celda('1 Solicitudes', GRIS),
            celda('2 Solicitudes ⚠ (Incid. 5)', GRIS),
            celda('1 Solicitudes', GRIS),
          ]}),
          new TableRow({ children: [
            celda('/my/orders — OV confirmada S00074'),
            celda('—'),
            celda('Invisible en la página ⚠ (Incid. 6)'),
            celda('Visible en lista'),
          ]}),
          new TableRow({ children: [
            celda('ORM (RPC directo) S00074', GRIS),
            celda('—', GRIS),
            celda('Devuelve S00074 correctamente', GRIS),
            celda('Devuelve S00074', GRIS),
          ]}),
          new TableRow({ children: [
            celda('Widget Importaciones'),
            celda('0'),
            celda('0 (sin cambio)'),
            celda('—'),
          ]}),
        ]
      }),

      separador(),

      // TABLA RESUMEN
      titulo('5. Resumen de las 8 incidencias'),

      new Paragraph({ spacing: { before: 0, after: 120 }, children: [] }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [600, 2000, 2200, 2200, 2360],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('#', AZUL_CLARO),
              celdaHeader('Usuario', AZUL_CLARO),
              celdaHeader('Widget', AZUL_CLARO),
              celdaHeader('Síntoma', AZUL_CLARO),
              celdaHeader('Causa raíz', AZUL_CLARO),
            ]
          }),
          new TableRow({
            children: [
              celda('1', GRIS),
              celda('Cliente', GRIS),
              celda('Solicitudes', GRIS),
              celda('Contador = 1, lista vacía', GRIS),
              celda('Link apunta a órdenes confirmadas, la solicitud está en draft', GRIS),
            ]
          }),
          new TableRow({
            children: [
              celda('2'),
              celda('Proveedor'),
              celda('Solicitudes'),
              celda('Contador = 0, lista vacía'),
              celda('Contador solo cuenta draft; al enviar OC pasa a sent. Lista muestra sale.order, no purchase.order'),
            ]
          }),
          new TableRow({
            children: [
              celda('3', GRIS),
              celda('Cliente y Proveedor', GRIS),
              celda('Importaciones', GRIS),
              celda('Contador = 1, lista vacía', GRIS),
              celda('Contador usa sudo(), la lista consulta sin sudo(). Sin ir.rule para portal, la lista devuelve vacío', GRIS),
            ]
          }),
          new TableRow({
            children: [
              celda('4'),
              celda('Cliente y Proveedor'),
              celda('Importaciones'),
              celda('Contador cae a 0 al avanzar etapa'),
              celda('Contador filtra stage_id = primera etapa; al mover la importación la pierde del conteo aunque siga activa'),
            ]
          }),
          new TableRow({
            children: [
              celda('5', GRIS),
              celda('Cliente', GRIS),
              celda('Solicitudes', GRIS),
              celda('Contador inflado por drafts del backend', GRIS),
              celda('El contador no distingue origen; cualquier sale.order draft para la empresa del cliente suma al widget', GRIS),
            ]
          }),
          new TableRow({
            children: [
              celda('6'),
              celda('Cliente'),
              celda('Solicitudes — /my/orders'),
              celda('OV confirmada accesible por ORM pero invisible en la página'),
              celda('Orden cumple ir.rule y dominio del controlador pero /my/orders renderiza lista vacía. Causa pendiente de confirmar'),
            ]
          }),
          new TableRow({
            children: [
              celda('7', GRIS),
              celda('Cliente', GRIS),
              celda('Facturas — widget contador', GRIS),
              celda('Contador de facturas muestra 0 aunque existe una factura en borrador para el cliente', GRIS),
              celda('El contador filtra por partner_id = empresa (80), pero la factura puede apuntar al contacto (77); o el seguidor no está configurado', GRIS),
            ]
          }),
          new TableRow({
            children: [
              celda('8'),
              celda('Cliente'),
              celda('Facturas — /my/invoices'),
              celda('Factura confirmada y pagada no aparece en la lista /my/invoices'),
              celda('Mismo patrón que incidencia 6: ORM devuelve la factura correctamente pero la página renderiza lista vacía. Causa pendiente de confirmar'),
            ]
          }),
        ]
      }),

    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('D:\\trabajo\\Pyxel\\IA\\incidencias_portal.docx', buffer);
  console.log('Documento creado: D:\\trabajo\\Pyxel\\IA\\incidencias_portal.docx');
});
